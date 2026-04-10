"""Pipeline 高级便捷 API。

提供两个高级函数，供 MCP 工具层直接调用，
屏蔽 PipelineOrchestrator 的配置解析细节。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..config import settings
from .models import (
    AssemblyOutput,
    CodeDetectionOutput,
    FormulaExtractionOutput,
    ImageExtractionOutput,
    LayoutAnalysisOutput,
    PipelineResult,
    PreprocessingInput,
    PreprocessingOutput,
    StageContext,
    TableExtractionOutput,
    TextExtractionOutput,
)
from .orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


def _get_pdf_stages_config() -> list[dict[str, Any]]:
    """从全局配置中获取 PDF Pipeline 的 Stage 配置。"""
    pipeline_cfg = settings.pipeline
    if pipeline_cfg is None or pipeline_cfg.pdf is None:
        return []
    return [s.model_dump() for s in pipeline_cfg.pdf.stages]


def _get_webpage_stages_config() -> list[dict[str, Any]]:
    """从全局配置中获取 WebPage Pipeline 的 Stage 配置。"""
    pipeline_cfg = settings.pipeline
    if pipeline_cfg is None or pipeline_cfg.webpage is None:
        return []
    return [s.model_dump() for s in pipeline_cfg.webpage.stages]


def _get_defaults_config() -> dict[str, Any]:
    """获取 Pipeline 全局默认配置。"""
    pipeline_cfg = settings.pipeline
    if pipeline_cfg is None or pipeline_cfg.defaults is None:
        return {}
    return pipeline_cfg.defaults.model_dump()


def _get_engine_gates() -> dict[str, bool]:
    """根据引擎级 enabled 配置构建门控映射。"""
    return {
        "docling": settings.docling_enabled,
        "mineru": settings.mineru_enabled,
        "marker": settings.marker_enabled,
    }


# PDF Pipeline 中可以并行执行的 Stage 名称
_PDF_PARALLEL_STAGES = [
    "text_extraction",
    "table_extraction",
    "formula_extraction",
    "image_extraction",
    "code_detection",
]

# WebPage Pipeline 中可以并行执行的 Stage 名称
_WEBPAGE_PARALLEL_STAGES = [
    "math_formula_extraction",
    "code_block_detection",
    "table_extraction",
    "image_extraction",
]


async def run_pdf_pipeline(
    source: str,
    page_range: Optional[tuple[int, int]] = None,
    extract_images: bool = True,
    extract_tables: bool = True,
    extract_formulas: bool = True,
    embed_images: bool = False,
    output_dir: Optional[str] = None,
) -> PipelineResult:
    """执行 PDF -> Markdown 完整管线。

    Args:
        source: PDF 文件路径或 URL
        page_range: 可选页码范围
        extract_images: 是否提取图片
        extract_tables: 是否提取表格
        extract_formulas: 是否提取公式
        embed_images: 是否嵌入图片
        output_dir: 输出目录

    Returns:
        PipelineResult 包含 Markdown 内容和统计数据
    """
    stages_config = _get_pdf_stages_config()
    if not stages_config:
        return PipelineResult(
            success=False,
            error="Pipeline 配置未找到（pipeline.pdf.stages 为空）",
        )

    # 确保导入 PDF Stage 工具以触发注册
    from . import pdf_stages as _  # noqa: F401

    orchestrator = PipelineOrchestrator(
        stages_config=stages_config,
        defaults_config=_get_defaults_config(),
        engine_gates=_get_engine_gates(),
    )

    input_data = PreprocessingInput(
        source=source,
        page_range=page_range,
        config={
            "extract_images": extract_images,
            "extract_tables": extract_tables,
            "extract_formulas": extract_formulas,
            "embed_images": embed_images,
            "output_dir": output_dir,
        },
    )

    stage_results = await orchestrator.run(
        initial_input=input_data,
        parallel_stages=_PDF_PARALLEL_STAGES,
    )

    # 检查关键 Stage 是否成功
    preprocessing_result = stage_results.get("preprocessing")
    if not preprocessing_result or not preprocessing_result.success:
        return PipelineResult(
            success=False,
            error=preprocessing_result.error if preprocessing_result else "预处理 Stage 未执行",
        )

    # 从各 Stage 结果中构建 PipelineResult
    preprocessing_output = preprocessing_result.output

    # 收集各 Stage 输出
    layout_output = _unwrap(stage_results.get("layout_analysis"))
    text_output = _unwrap(stage_results.get("text_extraction"))
    table_output = _unwrap(stage_results.get("table_extraction"))
    formula_output = _unwrap(stage_results.get("formula_extraction"))
    image_output = _unwrap(stage_results.get("image_extraction"))
    code_output = _unwrap(stage_results.get("code_detection"))
    assembly_output = _unwrap(stage_results.get("assembly"))

    # 如果有 assembly 输出，直接使用
    if assembly_output and isinstance(assembly_output, AssemblyOutput):
        return PipelineResult(
            success=True,
            markdown=assembly_output.markdown,
            word_count=assembly_output.word_count,
            characteristics=(
                preprocessing_output.characteristics
                if isinstance(preprocessing_output, PreprocessingOutput)
                else None
            ),
            tables_count=len(table_output.tables) if isinstance(table_output, TableExtractionOutput) else 0,
            formulas_count=(
                len(formula_output.formulas)
                if isinstance(formula_output, FormulaExtractionOutput)
                else 0
            ),
            images_count=len(image_output.images) if isinstance(image_output, ImageExtractionOutput) else 0,
            code_blocks_count=len(code_output.code_blocks) if isinstance(code_output, CodeDetectionOutput) else 0,
            engines_used=[
                r.engine_used
                for r in stage_results.values()
                if hasattr(r, "engine_used") and r.engine_used
            ],
            stage_results={k: {"success": v.success, "engine": v.engine_used} for k, v in stage_results.items()},
            metadata=assembly_output.metadata,
        )

    # 降级：如果没有 assembly 输出，尝试从 text_output 构建
    if isinstance(text_output, TextExtractionOutput):
        return PipelineResult(
            success=True,
            markdown=text_output.full_text,
            word_count=text_output.word_count,
            characteristics=(
                preprocessing_output.characteristics
                if isinstance(preprocessing_output, PreprocessingOutput)
                else None
            ),
            engines_used=[
                r.engine_used
                for r in stage_results.values()
                if hasattr(r, "engine_used") and r.engine_used
            ],
            stage_results={k: {"success": v.success, "engine": v.engine_used} for k, v in stage_results.items()},
        )

    return PipelineResult(
        success=False,
        error="Pipeline 未能生成有效输出",
        stage_results={k: {"success": v.success, "error": v.error} for k, v in stage_results.items()},
    )


async def run_webpage_pipeline(
    url: str,
    method: str = "auto",
    extract_main_content: bool = True,
    include_metadata: bool = True,
    embed_images: bool = False,
    custom_options: Optional[Dict[str, Any]] = None,
    formatting_options: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """执行 WebPage -> Markdown 完整管线。

    Args:
        url: 目标网页 URL
        method: 抓取方法
        extract_main_content: 是否提取主内容
        include_metadata: 是否包含元数据
        embed_images: 是否嵌入图片
        custom_options: 自定义转换选项
        formatting_options: 格式化选项

    Returns:
        字典包含 markdown, metadata, word_count 等字段
    """
    stages_config = _get_webpage_stages_config()
    if not stages_config:
        return {"success": False, "error": "Pipeline 配置未找到（pipeline.webpage.stages 为空）"}

    # 确保导入 WebPage Stage 工具以触发注册
    from . import webpage_stages as _  # noqa: F401

    orchestrator = PipelineOrchestrator(
        stages_config=stages_config,
        defaults_config=_get_defaults_config(),
    )

    # 创建初始上下文
    ctx = StageContext(
        url=url,
        config={
            "method": method,
            "extract_main_content": extract_main_content,
            "include_metadata": include_metadata,
            "embed_images": embed_images,
            "custom_options": custom_options or {},
            "formatting_options": formatting_options or {},
        },
    )

    stage_results = await orchestrator.run(
        initial_input=ctx,
        parallel_stages=_WEBPAGE_PARALLEL_STAGES,
    )

    # 检查结果
    failed_stages = {k: v for k, v in stage_results.items() if not v.success}
    if failed_stages:
        logger.warning(
            "WebPage Pipeline 中 %d 个 Stage 失败: %s",
            len(failed_stages),
            list(failed_stages.keys()),
        )

    # 从最终上下文构建结果
    final_ctx = ctx  # StageContext 是可变对象，被各 Stage 直接修改
    return {
        "success": bool(final_ctx.markdown),
        "markdown_content": final_ctx.markdown,
        "metadata": final_ctx.metadata,
        "word_count": len(final_ctx.markdown.split()) if final_ctx.markdown else 0,
        "url": url,
        "title": final_ctx.title,
        "errors": final_ctx.errors,
        "stage_results": {
            k: {"success": v.success, "engine": v.engine_used}
            for k, v in stage_results.items()
        },
    }


def _unwrap(stage_result: Any) -> Any:
    """从 StageResult 中提取 output 字段。"""
    if stage_result is None:
        return None
    if hasattr(stage_result, "output"):
        return stage_result.output
    return None
