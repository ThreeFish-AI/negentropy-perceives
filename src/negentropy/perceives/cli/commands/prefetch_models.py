"""CLI command: prefetch-models — 预下载 PDF 引擎所需模型。

避免用户首次 MCP 请求被 ~1.35GB Marker Layout 模型下载阻塞触发超时。
对未安装的引擎优雅跳过，对已下载模型幂等（HuggingFace 缓存自动去重）。

触发下载的最小动作（零推理）：
- docling : ``DocumentConverter(format_options={...})`` — 参考 ``engines/docling.py``
- marker  : ``from marker.models import create_model_dict; create_model_dict()``
- mineru  : ``subprocess.run(["mineru-models-download", "-s", "huggingface", "-m", "all"])``
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from typing import List, Optional, Tuple

from .._progress import console

try:
    import typer
except ImportError:
    raise ImportError("CLI dependencies not installed. Install with: uv add typer rich")


logger = logging.getLogger(__name__)

ALL_ENGINES = ("docling", "marker", "mineru")


def run(
    engines: str = typer.Option(
        "all",
        "--engines",
        "-e",
        help=("逗号分隔的引擎列表，可选 docling/marker/mineru 或 all（默认 all）"),
    ),
    hf_home: Optional[str] = typer.Option(
        None,
        "--hf-home",
        help="自定义 HuggingFace 缓存目录（将设置 HF_HOME 环境变量）",
    ),
) -> None:
    """一次性预下载 PDF 引擎模型到本地缓存。

    幂等操作：重复执行不会重新下载已缓存的模型。对未安装的引擎打印
    ``skipped`` 并给出 extras 安装提示，不会抛异常、不会中断后续引擎。

    退出码：全部成功（含 skipped）→ 0；任一引擎 error → 1。
    """
    if hf_home:
        os.environ["HF_HOME"] = hf_home
        console.print(f"[dim]已设置 HF_HOME={hf_home}[/dim]")

    selected = _parse_engines(engines)
    console.print(f"[bold cyan]预热 PDF 模型[/bold cyan] engines={','.join(selected)}")

    results: List[Tuple[str, str, float, str]] = []
    for engine in selected:
        status, elapsed, note = _dispatch(engine)
        results.append((engine, status, elapsed, note))
        _print_line(engine, status, elapsed, note)

    has_error = any(status == "error" for _, status, _, _ in results)
    console.print("")
    console.print("[bold]汇总：[/bold]")
    for engine, status, elapsed, note in results:
        _print_line(engine, status, elapsed, note, indent=True)

    raise typer.Exit(code=1 if has_error else 0)


def _parse_engines(raw: str) -> List[str]:
    raw = (raw or "").strip().lower()
    if not raw or raw == "all":
        return list(ALL_ENGINES)
    names = [n.strip() for n in raw.split(",") if n.strip()]
    unknown = [n for n in names if n not in ALL_ENGINES]
    if unknown:
        raise typer.BadParameter(
            f"未知引擎: {unknown}（可选 {list(ALL_ENGINES)} 或 all）"
        )
    # 保持声明顺序去重
    seen: set[str] = set()
    ordered: List[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


def _dispatch(engine: str) -> Tuple[str, float, str]:
    """分派到具体引擎的预热函数。返回 ``(status, elapsed_sec, note)``。

    status 取值：``ok`` / ``skipped`` / ``error``。
    """
    start = time.monotonic()
    try:
        if engine == "docling":
            note = _prefetch_docling()
        elif engine == "marker":
            note = _prefetch_marker()
        elif engine == "mineru":
            note = _prefetch_mineru()
        else:
            return ("error", 0.0, f"未知引擎: {engine}")
    except _SkipEngine as skip:
        return ("skipped", time.monotonic() - start, str(skip))
    except Exception as exc:  # noqa: BLE001 — CLI 层汇总异常，不向上抛
        logger.debug("引擎 %s 预热失败: %s", engine, exc, exc_info=True)
        return ("error", time.monotonic() - start, f"{type(exc).__name__}: {exc}")
    return ("ok", time.monotonic() - start, note)


class _SkipEngine(Exception):
    """引擎未安装或不可用时使用的信号异常。"""


# ---------------------------------------------------------------------------
# 引擎预热实现
# ---------------------------------------------------------------------------


def _prefetch_docling() -> str:
    """触发 Docling 布局/表格模型下载（不跑推理）。

    仅实例化 ``DocumentConverter``：首次构造会拉取所需模型到 HF 缓存。
    """
    try:
        from docling.datamodel.base_models import InputFormat  # type: ignore[import-untyped]
        from docling.datamodel.pipeline_options import (  # type: ignore[import-untyped]
            PdfPipelineOptions,
        )
        from docling.document_converter import (  # type: ignore[import-untyped]
            DocumentConverter,
            PdfFormatOption,
        )
    except ImportError as exc:
        raise _SkipEngine(
            f"docling 未安装（{exc}）；安装：uv sync --extra docling"
        ) from exc

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_table_structure = True
    # 构造即触发首次模型下载（已缓存则直接命中）
    DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    return "layout + table-structure 模型已就绪"


def _prefetch_marker() -> str:
    """触发 Marker 模型下载（layout + OCR 等 ~1.35GB）。"""
    # 强制 CPU 避免预热时占用 GPU；镜像运行时逻辑
    try:
        from ...pdf.engines.marker import MarkerEngine

        MarkerEngine._ensure_cpu_device()
    except Exception:  # noqa: BLE001 — 预热阶段此步失败不致命
        pass

    try:
        from marker.models import create_model_dict  # type: ignore[import-untyped]
    except ImportError as exc:
        raise _SkipEngine(
            f"marker 未安装（{exc}）；安装：uv sync --extra marker"
        ) from exc

    create_model_dict()
    return "模型字典已加载至 $HF_HOME / datalab 缓存"


def _prefetch_mineru() -> str:
    """触发 MinerU 模型下载（调用 ``mineru-models-download`` CLI）。"""
    # 先看 import 是否可用，做"是否安装"的快速判断
    try:
        import mineru  # type: ignore[import-untyped]  # noqa: F401
    except ImportError as exc:
        raise _SkipEngine(
            f"mineru 未安装（{exc}）；安装：uv sync --extra mineru"
        ) from exc

    binary = shutil.which("mineru-models-download")
    if binary is None:
        raise _SkipEngine(
            "未找到 mineru-models-download 可执行；请 uv sync --extra mineru 后重试"
        )

    cmd = [binary, "-s", "huggingface", "-m", "all"]
    console.print(f"[dim]执行：{' '.join(cmd)}[/dim]")
    proc = subprocess.run(  # noqa: S603 — binary 已由 shutil.which 校验
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
        raise RuntimeError(
            f"mineru-models-download 退出码 {proc.returncode}; 末尾日志:\n"
            + "\n".join(tail)
        )
    return "pipeline + vlm 模型已就绪"


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------


def _print_line(
    engine: str, status: str, elapsed: float, note: str, *, indent: bool = False
) -> None:
    prefix = "  " if indent else "[prefetch] "
    color = {"ok": "green", "skipped": "yellow", "error": "red"}.get(status, "white")
    elapsed_part = f"{elapsed:.1f}s" if elapsed else "-"
    console.print(
        f"{prefix}{engine:<8} ... [bold {color}]{status}[/bold {color}] "
        f"({elapsed_part}) {note}"
    )
