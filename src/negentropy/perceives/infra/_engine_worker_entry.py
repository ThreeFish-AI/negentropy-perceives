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
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


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
    except Exception:
        pass
