"""链接发现与页面检查 — 向后兼容层。

原始实现已重命名为 ``discovery.py``，
本文件保留重导出以保持向后兼容。
"""

import warnings

warnings.warn(
    "Importing from 'ops.extraction' is deprecated, use 'ops.discovery' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .discovery import *  # noqa: F401, F403
