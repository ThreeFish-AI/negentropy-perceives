"""Pipeline 编排器：串联多个 Stage 执行完整管线。

根据 ``config.default.yaml`` 中的 pipeline 配置，串联执行多个 Stage，
支持并行组和竞争模式。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from ..core.task_context import method_var, stage_var, timing_var
from .base import StageResult
from .scheduler import StageScheduler

logger = logging.getLogger(__name__)


InputBuilder = Callable[[Dict[str, StageResult], Any], Any]


class PipelineOrchestrator:
    """Pipeline 编排器。

    根据 ``config.default.yaml`` 中的 pipeline 配置，
    串联执行多个 Stage，支持并行组和竞争模式。

    输入路由（YAML 声明式）：
        - Stage 配置中的 ``input_builder`` 优先，在 ``input_builders`` 中查注册的构造器；
        - 否则 ``input_from`` 取指定前序 Stage 的 ``StageResult.output``；
        - 否则沿用链式语义（上一 Stage 输出即下一 Stage 输入）。
    """

    def __init__(
        self,
        stages_config: List[Dict[str, Any]],
        defaults_config: Optional[Dict[str, Any]] = None,
        engine_gates: Optional[Dict[str, bool]] = None,
        pipeline_name: str = "",
        input_builders: Optional[Mapping[str, InputBuilder]] = None,
    ):
        """
        Args:
            stages_config: Stage 配置列表
                （来自 ``pipeline.pdf.stages`` 或 ``pipeline.webpage.stages``）
            defaults_config: 全局默认竞争配置（来自 ``pipeline.defaults``）
            engine_gates: 引擎级门控（如 ``{"docling": True, "mineru": False}``）
            pipeline_name: Pipeline 名称，用于工具限定名查找隔离
            input_builders: 复合输入构造器字典（``{key: builder}``），
                ``builder(stage_results, initial_input) -> Any``。
        """
        self._stages_config = stages_config
        self._defaults = defaults_config or {}
        self._engine_gates = engine_gates or {}
        self._pipeline_name = pipeline_name
        self._input_builders: Mapping[str, InputBuilder] = input_builders or {}
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
                    resolved, err = self._resolve_input(
                        stage_cfg, results, initial_input, current_input
                    )
                    if err is not None:
                        logger.error("Stage '%s' 输入解析失败，管线终止: %s", name, err)
                        results[name] = StageResult(success=False, error=err)
                        return results
                    result = await self._execute_stage(stage_cfg, resolved)
                    results[name] = result
                    if not result.success:
                        logger.error(
                            "Stage '%s' 失败，管线终止: %s",
                            name,
                            result.error,
                        )
                        return results
                    # 更新 current_input（保留链式语义，供未声明 input_from 的后续 Stage 使用）
                    if result.output is not None:
                        current_input = result.output
            elif group["type"] == "parallel":
                resolved_pairs: List[Tuple[Dict[str, Any], Any]] = []
                parallel_results: Dict[str, StageResult] = {}
                for cfg in group["stages"]:
                    name = cfg["name"]
                    resolved, err = self._resolve_input(
                        cfg, results, initial_input, current_input
                    )
                    if err is not None:
                        logger.error("Stage '%s' 输入解析失败: %s", name, err)
                        parallel_results[name] = StageResult(success=False, error=err)
                    else:
                        resolved_pairs.append((cfg, resolved))

                if resolved_pairs:
                    exec_results = await self._execute_parallel(resolved_pairs)
                    parallel_results.update(exec_results)

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
        stage_pairs: List[Tuple[Dict[str, Any], Any]],
    ) -> Dict[str, StageResult]:
        """并行执行一组已解析好输入的 Stage。

        Args:
            stage_pairs: ``[(stage_config, resolved_input), ...]``，
                由 ``run()`` 按各 Stage 的 ``input_from`` / ``input_builder``
                预先解析得到，避免多 Stage 共用同一 ``current_input`` 产生污染。
        """
        names = [cfg["name"] for cfg, _ in stage_pairs]
        logger.info("并行执行 Stage 组: %s", names)

        tasks = [self._execute_stage(cfg, data) for cfg, data in stage_pairs]
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

    def _resolve_input(
        self,
        stage_cfg: Dict[str, Any],
        results: Dict[str, StageResult],
        initial_input: Any,
        chain_input: Any,
    ) -> Tuple[Any, Optional[str]]:
        """解析 Stage 的输入来源。

        优先级：
            1. ``input_builder``：查注册的复合输入构造器（用于 ``AssemblyInput``
               等需要汇聚多个前序 Stage 结果的场景）。
            2. ``input_from``：取指定前序 Stage 的 ``StageResult.output``。
            3. 否则使用 ``chain_input``（链式语义，向后兼容）。

        Returns:
            ``(resolved_input, error_message)``。错误信息非空时，
            调用方应生成 ``StageResult(success=False, error=...)`` 而非抛异常，
            以便并行组内其它 Stage 继续执行。
        """
        builder_key = stage_cfg.get("input_builder")
        if builder_key:
            builder = self._input_builders.get(builder_key)
            if builder is None:
                return None, (
                    f"未注册的 input_builder: '{builder_key}'（"
                    f"可用: {sorted(self._input_builders.keys())}）"
                )
            try:
                return builder(results, initial_input), None
            except Exception as exc:  # noqa: BLE001 — 转为结构化错误上报
                return None, f"input_builder '{builder_key}' 执行异常: {exc}"

        from_name = stage_cfg.get("input_from")
        if from_name:
            prev = results.get(from_name)
            if prev is None:
                return None, (f"input_from 引用的 Stage '{from_name}' 不存在或尚未执行")
            if not prev.success:
                return None, (
                    f"input_from 依赖的 Stage '{from_name}' 已失败: {prev.error}"
                )
            if prev.output is None:
                return None, (f"input_from 依赖的 Stage '{from_name}' 未产出 output")
            return prev.output, None

        return chain_input, None

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
