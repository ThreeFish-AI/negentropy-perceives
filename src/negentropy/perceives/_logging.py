"""日志配置 — 向后兼容层。

原始实现已迁至 ``core/logging.py``，
本文件保留重导出以保持向后兼容。
"""

import warnings

warnings.warn(
    "Importing from '_logging' is deprecated, use 'core.logging' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .core.logging import *  # noqa: F401, F403
