"""Pipeline 工具基类，消除各 Stage 工具实现中的重复样板代码。

提供两个基类：
- ``PDFToolBase``: PDF Pipeline 工具基类
- ``WebToolBase``: WebPage Pipeline 工具基类

子类只需实现 ``_run()`` 方法和（可选的） ``is_available()`` 方法。
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from ..base import StageResult

if TYPE_CHECKING:
    from ..models import StageContext

logger = logging.getLogger(__name__)


class PDFToolBase:
    """PDF Pipeline 工具基类。

    子类需设置 ``tool_name`` 类属性并实现 ``_run()`` 方法。
    如需自定义可用性检查，覆写 ``is_available()``。
    """

    tool_name: str = ""

    @property
    def name(self) -> str:
        return self.tool_name

    def is_available(self) -> bool:
        return True

    async def execute(self, input_data: Any) -> StageResult:
        start = time.monotonic()
        try:
            result = await self._run(input_data)
        except Exception as e:
            logger.warning("%s 执行失败: %s", self.tool_name, e)
            result = StageResult(
                success=False, error=str(e), engine_used=self.tool_name
            )
        result.elapsed_ms = (time.monotonic() - start) * 1000
        return result

    async def _run(self, input_data: Any) -> StageResult:
        raise NotImplementedError


class WebToolBase:
    """WebPage Pipeline 工具基类。

    子类需设置 ``tool_name`` 类属性并实现 ``_run()`` 方法。
    如需自定义可用性检查，覆写 ``is_available()``。
    """

    tool_name: str = ""

    @property
    def name(self) -> str:
        return self.tool_name

    def is_available(self) -> bool:
        return True

    async def execute(self, ctx: StageContext) -> StageResult:
        try:
            return await self._run(ctx)
        except Exception as e:
            logger.warning("%s 执行失败: %s", self.tool_name, e)
            return StageResult(
                success=False, output=ctx, error=str(e), engine_used=self.tool_name
            )

    async def _run(self, ctx: StageContext) -> StageResult:
        raise NotImplementedError
