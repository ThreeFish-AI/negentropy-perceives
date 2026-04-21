"""Stage 调度器：负责按配置选择和执行工具。

根据 Stage 配置决定执行模式：

- **降级模式** (``competition_mode=false``)：按 rank 顺序，首个可用即用
- **竞争模式** (``competition_mode=true``)：并行执行多个工具，择优
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .base import Stage, StageResult, StageTool
from .registry import get_tool

logger = logging.getLogger(__name__)

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class StageScheduler:
    """Stage 调度器。

    根据 Stage 配置决定：

    - 降级模式（``competition_mode=false``）：按 rank 顺序，首个可用即用
    - 竞争模式（``competition_mode=true``）：并行执行多个工具，择优
    """

    async def run_stage(
        self,
        stage_name: str,
        tool_configs: List[Dict[str, Any]],
        input_data: Any,
        competition_mode: bool = False,
        competition_config: Optional[Dict[str, Any]] = None,
        selector: Optional[Callable] = None,
        pipeline_name: str = "",
    ) -> StageResult:
        """执行单个 Stage。

        Args:
            stage_name: Stage 标识名
            tool_configs: 工具配置列表（已按 rank 排序）
            input_data: Stage 输入数据
            competition_mode: 是否启用竞争模式
            competition_config: 竞争模式配置（max_concurrent, timeout 等）
            selector: 自定义结果选择器
            pipeline_name: Pipeline 名称，用于限定名查找

        Returns:
            Stage 执行结果
        """
        # 解析可用工具
        tools = self._resolve_tools(
            tool_configs, stage_name=stage_name, pipeline_name=pipeline_name
        )
        if not tools:
            return StageResult(
                success=False,
                error=(
                    f"Stage '{stage_name}' 无可用工具（配置中所有工具均不可用或未安装）"
                ),
            )

        if not competition_mode:
            return await self._run_fallback(stage_name, tools, input_data)
        else:
            comp = competition_config or {}
            return await self._run_competition(
                stage_name,
                tools,
                input_data,
                max_concurrent=comp.get("max_concurrent", 2),
                timeout=comp.get("timeout", 120),
                selector=selector,
            )

    async def _run_fallback(
        self,
        stage_name: str,
        tools: List[StageTool],
        input_data: Any,
    ) -> StageResult:
        """降级模式：按 rank 顺序逐个尝试。"""
        for tool in tools:
            try:
                logger.info(
                    "Stage '%s' 降级模式：尝试工具 '%s'",
                    stage_name,
                    tool.name,
                )
                result = await tool.execute(input_data)
                if result.success:
                    result.engine_used = tool.name
                    logger.info(
                        "Stage '%s' 工具 '%s' 成功",
                        stage_name,
                        tool.name,
                    )
                    return result
                logger.warning(
                    "Stage '%s' 工具 '%s' 返回失败: %s",
                    stage_name,
                    tool.name,
                    result.error,
                )
            except Exception as exc:
                logger.warning(
                    "Stage '%s' 工具 '%s' 异常: %s",
                    stage_name,
                    tool.name,
                    exc,
                )
        return StageResult(
            success=False,
            error=f"Stage '{stage_name}' 所有工具均不可用或执行失败",
        )

    async def _run_competition(
        self,
        stage_name: str,
        tools: List[StageTool],
        input_data: Any,
        max_concurrent: int = 2,
        timeout: float = 120.0,
        selector: Optional[Callable] = None,
    ) -> StageResult:
        """竞争模式：并行执行多个工具，择优。"""
        candidates = tools[:max_concurrent]
        logger.info(
            "Stage '%s' 竞争模式：并行运行 %d 个工具 [%s]",
            stage_name,
            len(candidates),
            ", ".join(t.name for t in candidates),
        )

        tasks = [
            asyncio.wait_for(tool.execute(input_data), timeout=timeout)
            for tool in candidates
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        successful: List[StageResult] = []
        for i, raw in enumerate(raw_results):
            tool_name = candidates[i].name
            if isinstance(raw, StageResult) and raw.success:
                raw.engine_used = tool_name
                successful.append(raw)
            elif isinstance(raw, asyncio.TimeoutError):
                logger.warning(
                    "Stage '%s' 工具 '%s' 超时 (%.0fs)",
                    stage_name,
                    tool_name,
                    timeout,
                )
            elif isinstance(raw, Exception):
                logger.warning(
                    "Stage '%s' 工具 '%s' 异常: %s",
                    stage_name,
                    tool_name,
                    raw,
                )

        if not successful:
            return StageResult(
                success=False,
                error=f"Stage '{stage_name}' 所有竞争工具均失败",
            )

        if len(successful) == 1:
            return successful[0]

        # 多个成功结果 -> 择优
        if selector:
            return selector(successful)
        return successful[0]  # 默认取 rank 最高的

    def _resolve_tools(
        self,
        tool_configs: List[Dict[str, Any]],
        stage_name: str = "",
        pipeline_name: str = "",
    ) -> List[StageTool]:
        """根据配置解析并排序工具实例。

        Args:
            tool_configs: ``[{name: str, rank: int, enabled: bool}, ...]``
            stage_name: Stage 名称，用于限定名查找（如 ``preprocessing.pymupdf``）
            pipeline_name: Pipeline 名称，用于跨 Pipeline 隔离

        Returns:
            按 rank 排序的可用工具实例列表
        """
        sorted_configs = sorted(
            [tc for tc in tool_configs if tc.get("enabled", True)],
            key=lambda tc: tc.get("rank", 999),
        )
        tools = []
        for tc in sorted_configs:
            name = tc.get("name", "")
            tool = None
            # 1. 尝试 pipeline 感知限定名（如 "pdf.preprocessing.pymupdf"）
            if pipeline_name and stage_name:
                try:
                    tool = get_tool(f"{pipeline_name}.{stage_name}.{name}")
                except ValueError:
                    pass
            # 2. 兼容旧格式 stage 限定名（如 "preprocessing.pymupdf"）
            if tool is None and stage_name:
                try:
                    tool = get_tool(f"{stage_name}.{name}")
                except ValueError:
                    pass
            # 3. 通用名回退（如 "aiohttp"）
            if tool is None:
                try:
                    tool = get_tool(name)
                except ValueError:
                    logger.debug("工具 '%s' 未注册，跳过", name)
                    continue
            if tool.is_available():
                tools.append(tool)
            else:
                logger.debug("工具 '%s' 未安装或不可用，跳过", name)
        if not tools and sorted_configs:
            names_tried = [tc.get("name", "") for tc in sorted_configs]
            logger.warning(
                "Stage '%s' 无可用工具，已尝试: %s",
                stage_name,
                names_tried,
            )
        elif tools:
            logger.info(
                "Stage '%s' 可用工具: %s",
                stage_name,
                [t.name for t in tools],
            )
        return tools


class CompetitiveStage(Stage[TInput, TOutput]):
    """多工具并行竞争 Stage。

    并行运行多个候选工具，通过选择器择优。
    委托 ``StageScheduler._run_competition`` 执行实际竞争逻辑。
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
        self._selector = selector
        self._max_concurrent = max_concurrent
        self._timeout = timeout
        self._scheduler = StageScheduler()

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

        return await self._scheduler._run_competition(
            stage_name=self._stage_id,
            tools=available,
            input_data=input_data,
            max_concurrent=self._max_concurrent,
            timeout=self._timeout,
            selector=self._selector,
        )
