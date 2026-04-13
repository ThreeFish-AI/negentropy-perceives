"""Docling 引擎向后兼容层。

原始实现已迁至 ``engines/docling.py``，
本文件保留重导出以保持向后兼容。
"""

from __future__ import annotations

from .engines.docling import (
    DoclingCodeBlock,
    DoclingConversionResult,
    DoclingEngine,
    DoclingFormula,
    DoclingImage,
    DoclingTable,
)

__all__ = [
    "DoclingEngine",
    "DoclingConversionResult",
    "DoclingTable",
    "DoclingImage",
    "DoclingFormula",
    "DoclingCodeBlock",
]
