"""引擎 worker 子进程入口点。

独立运行于 ``multiprocessing.Process`` 中，接收主进程通过 ``multiprocessing.Pipe``
发来的请求，按需懒加载对应引擎并执行 ``convert()``（或其他方法），将结果回送。

Why 子进程：
- Docling/MinerU/Marker 的原生推理（C++/CUDA）阻塞 Python 事件循环与 GIL，
  Python 线程无法被强制 kill；只有进程级终止（SIGTERM/SIGKILL）能真正释放
  GPU/显存与 CPU 占用。
- 每个引擎一个独立子进程，崩溃与被 kill 都不影响主进程，供 Pool 层按
  Erlang/OTP Supervisor Pattern 重建。

进程内启用懒加载：
- 子进程启动即立刻回送 ``ready``；首个 ``call`` 到达时按 ``init_kwargs`` 懒
  实例化引擎对象，后续调用若 ``init_kwargs`` 哈希发生变化则原地重建（不重
  启进程）。模型权重通常由底层库做全局缓存，原地重建成本远低于进程重启。
- 内置 ``_fake_slow`` / ``_fake_fast`` / ``_fake_crash`` 三个调试引擎，
  用于在集成测试中验证"取消→kill→重建"链路，无需真实 PDF 库依赖。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
import traceback
from multiprocessing.connection import Connection
from typing import Any, Dict, Optional


# ── 调试引擎：供集成测试模拟各种场景，不依赖真实 PDF 引擎 ──────────────────


class _FakeSlowEngine:
    """阻塞 sleep_seconds 后返回成功，用于验证 timeout/cancel kill 路径。"""

    def convert(
        self,
        pdf_path: str,
        *,
        sleep_seconds: float = 30.0,
        **_: Any,
    ) -> dict:
        time.sleep(sleep_seconds)
        return {
            "markdown": f"slept {sleep_seconds}s on {pdf_path}",
            "engine_name": "_fake_slow",
            "page_count": 1,
        }


class _FakeFastEngine:
    """立即返回，用于验证正常路径与 worker 复用。"""

    def convert(self, pdf_path: str, **_: Any) -> dict:
        return {
            "markdown": f"fast output from {pdf_path}",
            "engine_name": "_fake_fast",
            "page_count": 1,
        }


class _FakeCrashEngine:
    """主动抛异常，用于验证子进程异常回传与 worker 存活判定。"""

    def convert(self, pdf_path: str, **_: Any) -> dict:
        raise RuntimeError(f"fake crash on {pdf_path}")


def _load_engine(engine_name: str, init_kwargs: Optional[Dict[str, Any]] = None) -> Any:
    """按需懒加载引擎实例。

    ``init_kwargs`` 透传给对应 Engine 的 ``__init__``；对内置 Fake 引擎忽略。
    未知引擎抛 ``ValueError``。
    """

    kw = init_kwargs or {}

    if engine_name == "docling":
        from ..pdf.engines.docling import DoclingEngine

        return DoclingEngine(**kw)
    if engine_name == "mineru":
        from ..pdf.engines.mineru import MinerUEngine

        return MinerUEngine(**kw)
    if engine_name == "marker":
        from ..pdf.engines.marker import MarkerEngine

        return MarkerEngine(**kw)
    if engine_name == "_fake_slow":
        return _FakeSlowEngine()
    if engine_name == "_fake_fast":
        return _FakeFastEngine()
    if engine_name == "_fake_crash":
        return _FakeCrashEngine()
    raise ValueError(f"未知引擎: {engine_name}")


def _hash_init_kwargs(init_kwargs: Optional[Dict[str, Any]]) -> str:
    """对 init_kwargs 计算稳定哈希，用于判定是否需要重建引擎。"""
    if not init_kwargs:
        return "__empty__"
    try:
        serialized = json.dumps(init_kwargs, sort_keys=True, default=str)
    except Exception:
        serialized = repr(sorted(init_kwargs.items()))
    return hashlib.sha1(serialized.encode("utf-8"), usedforsecurity=False).hexdigest()


def _preinit_torch_device(logger: logging.Logger) -> None:
    """spawn 子进程内完成 torch 设备预热 + MPS first-touch + 诊断日志。

    **永不抛异常**：任何失败都被吞掉并降级到 CPU 路径，确保 worker 能稳定启动。
    副作用：
    - `PYTORCH_ENABLE_MPS_FALLBACK=1`：仅作算子 fallback 兜底，不禁用 MPS；
    - `NEGENTROPY_MPS_READY=1/0`：把 smoke_test 结果暴露给下游引擎（Docling
      `device_config` 可据此决定是否把 `AcceleratorDevice` 设为 MPS）；
    - 打印一行 `子进程 torch 诊断 {...}` 含版本、start_method、built、
      available、smoke_test（ok / skip:... / fail:ExcName:msg）。
    """
    # 默认 MPS 算子 fallback 兜底；真正禁用 MPS 的开关另行设计
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    diag: Dict[str, Any] = {
        "start_method": None,
        "torch_version": None,
        "mps_built": None,
        "mps_available_raw": None,
        "mps_smoke_test": "skip:not_darwin",
    }

    try:
        import multiprocessing as mp

        diag["start_method"] = mp.get_start_method(allow_none=True)
    except Exception:  # nosec B110
        pass

    try:
        import torch
    except Exception as e:  # torch 缺失或导入失败，直接回退 CPU
        diag["mps_smoke_test"] = f"fail:torch_import:{type(e).__name__}"
        os.environ["NEGENTROPY_MPS_READY"] = "0"
        # 使用 warning 级别确保在默认 WARNING 日志阈值下也可见；单进程只调用一次
        logger.warning("子进程 torch 诊断 %s", diag)
        return

    diag["torch_version"] = getattr(torch, "__version__", "unknown")

    try:
        diag["mps_built"] = bool(torch.backends.mps.is_built())
    except Exception as e:
        diag["mps_built"] = f"err:{type(e).__name__}:{e}"
    try:
        diag["mps_available_raw"] = bool(torch.backends.mps.is_available())
    except Exception as e:
        diag["mps_available_raw"] = f"err:{type(e).__name__}:{e}"

    # 仅在 darwin 上尝试 first-touch（其他平台无 MPS）
    mps_ready = False
    if sys.platform == "darwin" and diag["mps_built"] is True:
        try:
            _ = torch.zeros(1, device="mps")
            # first-touch 成功后 is_available 可能会从 False 变为 True
            try:
                if torch.backends.mps.is_available():
                    diag["mps_available_raw"] = True
            except Exception:  # nosec B110
                pass
            diag["mps_smoke_test"] = "ok"
            mps_ready = True
        except Exception as e:
            diag["mps_smoke_test"] = f"fail:{type(e).__name__}:{str(e)[:120]}"
    elif sys.platform == "darwin":
        diag["mps_smoke_test"] = "skip:mps_not_built"

    os.environ["NEGENTROPY_MPS_READY"] = "1" if mps_ready else "0"
    # 使用 warning 级别确保在默认 WARNING 日志阈值下也可见；单进程只调用一次
    logger.warning("子进程 torch 诊断 %s", diag)


def worker_main(conn: Connection, engine_name: str) -> None:
    """子进程主循环：ready → 等请求 → 懒加载/执行 → 回写。

    协议：
    - 启动成功：``{"type": "ready"}``（立即发送，无预实例化）
    - 请求：``{"type": "call", "id": str, "method": str,
               "kwargs": dict, "init_kwargs": dict | None,
               "deadline_monotonic": float | None}``
    - 关闭：``{"type": "shutdown"}``
    - 响应：``{"type": "result", "id": str, "ok": bool,
               "result"|"error": ..., "exc_class": str}``
    """

    logging.basicConfig(
        level=logging.WARNING,
        stream=sys.stderr,
        format="%(asctime)s [%(levelname)s] engine_worker.%(name)s: %(message)s",
    )
    logger = logging.getLogger(f"{engine_name}.pid{os.getpid()}")

    # 立即回送 ready，不做预实例化（懒加载）
    try:
        conn.send({"type": "ready"})
    except Exception:
        return

    # MPS 环境预初始化（仅限 torch 相关引擎，避免 fake/test worker 的导入开销）
    #
    # 动机：spawn 子进程首次 `import torch` 后，`torch.backends.mps.is_available()`
    # 在 Apple Silicon 某些组合下会稳定返回 False；根因是 MPS 的统一内存
    # allocator 依赖懒初始化，`is_available()` 自身并不触发 first-touch。
    # 解决：在子进程启动时显式分配一次 MPS tensor（first-touch），之后 allocator
    # 就绪，`is_available()` 与 `AcceleratorDevice.MPS` 均可正常使用。
    #
    # 同时把诊断信息（torch 版本、start_method、built/available/smoke_test 结果）
    # 打到日志，便于远端 MPS 故障的线上排查。
    if engine_name in ("docling", "mineru", "marker"):
        _preinit_torch_device(logger)

    cached_engine: Optional[Any] = None
    cached_hash: Optional[str] = None

    while True:
        try:
            request = conn.recv()
        except EOFError:
            break
        except Exception as e:
            logger.warning("recv 异常: %s", e)
            break

        if not isinstance(request, dict):
            continue

        msg_type = request.get("type")
        if msg_type == "shutdown":
            break
        if msg_type != "call":
            try:
                conn.send(
                    {
                        "type": "result",
                        "id": request.get("id"),
                        "ok": False,
                        "error": f"未知请求类型: {msg_type}",
                        "exc_class": "RuntimeError",
                    }
                )
            except Exception:
                break
            continue

        req_id = request.get("id")
        method = request.get("method", "convert")
        kwargs = request.get("kwargs", {}) or {}
        init_kwargs = request.get("init_kwargs") or {}
        deadline_monotonic = request.get("deadline_monotonic")

        # Deadline pre-check：若在请求到达时 deadline 已过，直接 fail-fast
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            try:
                conn.send(
                    {
                        "type": "result",
                        "id": req_id,
                        "ok": False,
                        "error": "deadline 已过 (pre-check)",
                        "exc_class": "TimeoutError",
                    }
                )
            except Exception:
                break
            continue

        # 按需懒加载 / 原地重建引擎
        new_hash = _hash_init_kwargs(init_kwargs)
        if cached_engine is None or cached_hash != new_hash:
            try:
                cached_engine = _load_engine(engine_name, init_kwargs)
                cached_hash = new_hash
            except Exception as e:
                try:
                    conn.send(
                        {
                            "type": "result",
                            "id": req_id,
                            "ok": False,
                            "error": f"初始化失败: {e}",
                            "exc_class": type(e).__name__,
                            "traceback": traceback.format_exc(),
                        }
                    )
                except Exception:
                    break
                continue

        try:
            func = getattr(cached_engine, method)
            result = func(**kwargs)
            conn.send(
                {
                    "type": "result",
                    "id": req_id,
                    "ok": True,
                    "result": result,
                }
            )
        except Exception as e:
            try:
                conn.send(
                    {
                        "type": "result",
                        "id": req_id,
                        "ok": False,
                        "error": str(e),
                        "exc_class": type(e).__name__,
                        "traceback": traceback.format_exc(),
                    }
                )
            except Exception:
                break

    try:
        conn.close()
    except Exception:  # nosec B110
        # 子进程退出阶段连接可能已在对端关闭；静默即可
        pass
