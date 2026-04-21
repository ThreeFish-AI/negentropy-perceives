"""Pipeline 编排器：串联多个 Stage 执行完整管线。

根据 ``config.default.yaml`` 中的 pipeline 配置，串联执行多个 Stage，
支持并行组和竞争模式。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from ..core.task_context import method_var, stage_var, timing_var
from .base import StageResult
from .scheduler import StageScheduler

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Pipeline 编排器。

    根据 ``config.default.yaml`` 中的 pipeline 配置，
    串联执行多个 Stage，支持并行组和竞争模式。
    """

    def __init__(
        self,
        stages_config: List[Dict[str, Any]],
        defaults_config: Optional[Dict[str, Any]] = None,
        engine_gates: Optional[Dict[str, bool]] = None,
        pipeline_name: str = "",
    ):
        """
        Args:
            stages_config: Stage 配置列表
                （来自 ``pipeline.pdf.stages`` 或 ``pipeline.webpage.stages``）
            defaults_config: 全局默认竞争配置（来自 ``pipeline.defaults``）
            engine_gates: 引擎级门控（如 ``{"docling": True, "mineru": False}``）
            pipeline_name: Pipeline 名称，用于工具限定名查找隔离
        """
        self._stages_config = stages_config
        self._defaults = defaults_config or {}
        self._engine_gates = engine_gates or {}
        self._pipeline_name = pipeline_name
        self._scheduler = StageScheduler()

    async def run(
        self,
        initial_input: Any,
        parallel_stages: Optional[List[str]] = None,
    ) -> Dict[str, StageResult]:
        """执行完整管线。

        Args:
            initial_input: 初始输入数据
            parallel_stages: 可并行执行的 Stage 名称列表。
                这些 Stage 将通过 ``asyncio.gather`` 并行执行。

        Returns:
            ``{stage_name: StageResult}`` 字典
        """
        parallel_set = set(parallel_stages or [])
        results: Dict[str, StageResult] = {}
        current_input = initial_input
        pipeline_start = time.monotonic()

        # 分组：连续的并行 Stage 合并为一组
        groups = self._group_stages(self._stages_config, parallel_set)

        for group in groups:
            if group["type"] == "sequential":
                for stage_cfg in group["stages"]:
                    name = stage_cfg["name"]
                    result = await self._execute_stage(stage_cfg, current_input)
                    results[name] = result
                    if not result.success:
                        logger.error(
                            "Stage '%s' 失败，管线终止: %s",
                            name,
                            result.error,
                        )
                        return results
                    # 更新 current_input（Stage 间传递数据）
                    if result.output is not None:
                        current_input = result.output
            elif group["type"] == "parallel":
                parallel_results = await self._execute_parallel(
                    group["stages"], current_input
                )
                results.update(parallel_results)
                # 检查是否有失败
                failed = {k: v for k, v in parallel_results.items() if not v.success}
                if failed:
                    logger.warning(
                        "并行组中 %d 个 Stage 失败: %s",
                        len(failed),
                        list(failed.keys()),
                    )

        elapsed = (time.monotonic() - pipeline_start) * 1000
        logger.info("管线完成，总耗时: %.1fms", elapsed)
        return results

    async def _execute_stage(
        self,
        stage_config: Dict[str, Any],
        input_data: Any,
    ) -> StageResult:
        """执行单个 Stage。

        为当前 Stage 绑定 `stage_var` 与 `method_var`（ContextVar），使日志前缀
        自动携带 `stage=` / `method=` 字段，并在 TaskTiming 中追加一条 Stage 记录。
        `asyncio.gather` 为并行 Stage 自动复制 Context，故并发任务间互不干扰。
        """
        name = stage_config["name"]
        tool_configs = self._apply_engine_gates(stage_config.get("tools", []))
        competition_mode = stage_config.get("competition_mode", False)
        competition_config = stage_config.get(
            "competition",
            self._defaults.get("competition", {}),
        )

        stage_tok = stage_var.set(name)
        method_tok = method_var.set(None)
        start = time.monotonic()
        tool_names = [tc.get("name", "") for tc in tool_configs]
        logger.info(
            "Stage 开始 tools=%s competition=%s",
            tool_names,
            competition_mode,
        )
        try:
            result = await self._scheduler.run_stage(
                stage_name=name,
                tool_configs=tool_configs,
                input_data=input_data,
                competition_mode=competition_mode,
                competition_config=competition_config,
                pipeline_name=self._pipeline_name,
            )
            result.elapsed_ms = (time.monotonic() - start) * 1000
            if result.engine_used:
                method_var.set(result.engine_used)
            logger.info(
                "Stage 完成 success=%s elapsed=%.1fms",
                result.success,
                result.elapsed_ms,
            )
            timing = timing_var.get()
            if timing is not None:
                timing.stage_records.append(
                    (
                        name,
                        result.engine_used or "-",
                        result.elapsed_ms,
                        result.success,
                    )
                )
            return result
        finally:
            method_var.reset(method_tok)
            stage_var.reset(stage_tok)

    async def _execute_parallel(
        self,
        stage_configs: List[Dict[str, Any]],
        input_data: Any,
    ) -> Dict[str, StageResult]:
        """并行执行一组 Stage。"""
        names = [cfg["name"] for cfg in stage_configs]
        logger.info("并行执行 Stage 组: %s", names)

        tasks = [self._execute_stage(cfg, input_data) for cfg in stage_configs]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: Dict[str, StageResult] = {}
        for i, raw in enumerate(raw_results):
            name = names[i]
            if isinstance(raw, StageResult):
                results[name] = raw
            elif isinstance(raw, Exception):
                results[name] = StageResult(
                    success=False,
                    error=f"Stage '{name}' 并行执行异常: {raw}",
                )
        return results

    def _apply_engine_gates(
        self,
        tool_configs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """应用引擎级门控过滤。

        如果 ``engine_gates`` 中某引擎为 ``False``，则从工具列表中移除。
        """
        if not self._engine_gates:
            return tool_configs
        return [
            tc
            for tc in tool_configs
            if self._engine_gates.get(tc.get("name", ""), True)
        ]

    @staticmethod
    def _group_stages(
        stages: List[Dict[str, Any]],
        parallel_set: set,
    ) -> List[Dict[str, Any]]:
        """将 Stage 列表分组为顺序组和并行组。

        连续的并行 Stage 合并为一个并行组。
        """
        groups: List[Dict[str, Any]] = []
        current_parallel: List[Dict[str, Any]] = []

        for stage in stages:
            name = stage.get("name", "")
            if name in parallel_set:
                current_parallel.append(stage)
            else:
                # 先刷出累积的并行组
                if current_parallel:
                    groups.append({"type": "parallel", "stages": current_parallel})
                    current_parallel = []
                # 添加顺序 Stage
                if groups and groups[-1]["type"] == "sequential":
                    groups[-1]["stages"].append(stage)
                else:
                    groups.append({"type": "sequential", "stages": [stage]})

        # 刷出尾部并行组
        if current_parallel:
            groups.append({"type": "parallel", "stages": current_parallel})

        return groups
