"""LLM 客户端向后兼容层。

原始实现已迁至 ``llm/client.py``，
本文件保留重导出以保持向后兼容。
"""

from __future__ import annotations

from .llm.client import LLMClient, LLMResponse

__all__ = [
    "LLMClient",
    "LLMResponse",
]
