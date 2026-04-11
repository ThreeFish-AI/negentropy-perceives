"""多工具竞争 Stage：并行运行多个引擎，择优。

本模块实现 ``CompetitiveStage``，支持在单个 Stage 中并行运行多个
候选工具（引擎），并通过可自定义的选择器从多个成功结果中择优返回。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Generic, List, Optional, TypeVar

from .base import Stage, StageResult, StageTool

logger = logging.getLogger(__name__)

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class CompetitiveStage(Stage[TInput, TOutput]):
    """多工具并行竞争 Stage。

    并行运行多个候选工具，通过选择器择优。
    """

    def __init__(
        self,
        stage_id: str,
        stage_name: str,
        candidates: List[StageTool],
        selector: Optional[
            Callable[[List[StageResult[TOutput]]], StageResult[TOutput]]
        ] = None,
        max_concurrent: int = 2,
        timeout: float = 120.0,
    ):
        self._stage_id = stage_id
        self._stage_name = stage_name
        self._candidates = candidates
        self._selector = selector or self._default_select
        self._max_concurrent = max_concurrent
        self._timeout = timeout

    @property
    def stage_id(self) -> str:
        return self._stage_id

    @property
    def stage_name(self) -> str:
        return self._stage_name

    async def execute(self, input_data: TInput) -> StageResult[TOutput]:
        """并行执行候选工具并择优。"""
        available = [c for c in self._candidates if c.is_available()]
        if not available:
            return StageResult(
                success=False,
                error=f"Stage '{self._stage_id}' 无可用候选工具",
            )

        # 取前 N 个可用工具
        selected = available[: self._max_concurrent]
        logger.info(
            "Stage '%s' 竞争模式：并行运行 %d 个工具 [%s]",
            self._stage_id,
            len(selected),
            ", ".join(t.name for t in selected),
        )

        # 并行执行，带超时
        tasks = [
            asyncio.wait_for(tool.execute(input_data), timeout=self._timeout)
            for tool in selected
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        successful: List[StageResult[TOutput]] = []
        for i, raw in enumerate(raw_results):
            tool_name = selected[i].name
            if isinstance(raw, StageResult) and raw.success:
                raw.engine_used = tool_name
                successful.append(raw)
            elif isinstance(raw, asyncio.TimeoutError):
                logger.warning(
                    "Stage '%s' 工具 '%s' 超时 (%.0fs)",
                    self._stage_id,
                    tool_name,
                    self._timeout,
                )
            elif isinstance(raw, Exception):
                logger.warning(
                    "Stage '%s' 工具 '%s' 异常: %s",
                    self._stage_id,
                    tool_name,
                    raw,
                )
            elif isinstance(raw, StageResult):
                logger.warning(
                    "Stage '%s' 工具 '%s' 失败: %s",
                    self._stage_id,
                    tool_name,
                    raw.error,
                )

        if not successful:
            return StageResult(
                success=False,
                error=f"Stage '{self._stage_id}' 所有候选工具均失败",
            )

        if len(successful) == 1:
            return successful[0]

        # 多个成功结果 -> 择优
        return self._selector(successful)

    @staticmethod
    def _default_select(
        results: List[StageResult[TOutput]],
    ) -> StageResult[TOutput]:
        """默认选择策略：返回第一个成功结果（按工具 rank 顺序）。"""
        return results[0]
