"""S5: 公式提取 Stage。

数学公式检测与 LaTeX 转换。

委托关系：
- ``pdf.math_formula.FormulaReconstructor`` — PyMuPDF 字体分析降级路径
- ``pdf.math_formula.DoclingFormulaEnricher`` — Docling CodeFormula 高保真路径
- ``pdf.mineru_engine.MinerUEngine`` — MinerU 公式提取
- ``pdf.docling_engine.DoclingEngine`` — Docling 全文转换中的公式
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List

from ..base import Stage, StageResult
from ..models import (
    ExtractedFormulaV2,
    FormulaExtractionOutput,
    PreprocessingOutput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具适配器
# ---------------------------------------------------------------------------


class MinerUFormulaExtractor:
    """基于 MinerU 的公式提取工具。"""

    @property
    def name(self) -> str:
        return "mineru"

    def is_available(self) -> bool:
        try:
            from ...pdf.mineru_engine import MinerUEngine

            return MinerUEngine.is_available()
        except ImportError:
            return False

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[FormulaExtractionOutput]:
        """使用 MinerU 提取数学公式。"""
        start = time.monotonic()
        try:
            import asyncio

            from ...pdf.mineru_engine import MinerUEngine

            engine = MinerUEngine()
            result = await asyncio.to_thread(
                engine.convert,
                str(input_data.local_path),
                input_data.page_range,
            )
            if result is None:
                return StageResult(success=False, error="MinerU 转换返回空结果")

            formulas: List[ExtractedFormulaV2] = []
            for idx, f in enumerate(result.formulas):
                formulas.append(
                    ExtractedFormulaV2(
                        formula_id=f"formula_{idx}",
                        latex=f.latex,
                        formula_type=f.formula_type,
                        page_number=f.page_number or 0,
                        original_text=f.original_text,
                    )
                )

            inline_count = sum(1 for f in formulas if f.formula_type == "inline")
            block_count = sum(1 for f in formulas if f.formula_type == "block")

            output = FormulaExtractionOutput(
                formulas=formulas,
                inline_count=inline_count,
                block_count=block_count,
                metadata={"engine": "mineru"},
            )

            elapsed = (time.monotonic() - start) * 1000
            return StageResult(
                success=True,
                output=output,
                engine_used="mineru",
                elapsed_ms=elapsed,
            )

        except Exception as e:
            logger.warning("MinerU 公式提取失败: %s", e)
            return StageResult(success=False, error=f"MinerU 公式提取失败: {e}")


class DoclingFormulaExtractor:
    """基于 Docling 的公式提取工具。"""

    @property
    def name(self) -> str:
        return "docling"

    def is_available(self) -> bool:
        try:
            from ...pdf.docling_engine import DoclingEngine

            return DoclingEngine.is_available()
        except ImportError:
            return False

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[FormulaExtractionOutput]:
        """使用 Docling 提取公式。"""
        start = time.monotonic()
        try:
            from ...pdf.docling_engine import DoclingEngine

            engine = DoclingEngine(enable_formula_enrichment=True)
            result = engine.convert(
                str(input_data.local_path),
                page_range=input_data.page_range,
            )
            if result is None:
                return StageResult(success=False, error="Docling 转换返回空结果")

            formulas: List[ExtractedFormulaV2] = []
            for idx, f in enumerate(result.formulas):
                formulas.append(
                    ExtractedFormulaV2(
                        formula_id=f"formula_{idx}",
                        latex=f.latex,
                        formula_type=f.formula_type,
                        page_number=f.page_number or 0,
                        original_text=f.original_text,
                    )
                )

            inline_count = sum(1 for f in formulas if f.formula_type == "inline")
            block_count = sum(1 for f in formulas if f.formula_type == "block")

            output = FormulaExtractionOutput(
                formulas=formulas,
                inline_count=inline_count,
                block_count=block_count,
                metadata={"engine": "docling"},
            )

            elapsed = (time.monotonic() - start) * 1000
            return StageResult(
                success=True,
                output=output,
                engine_used="docling",
                elapsed_ms=elapsed,
            )

        except Exception as e:
            logger.warning("Docling 公式提取失败: %s", e)
            return StageResult(success=False, error=f"Docling 公式提取失败: {e}")


class PyMuPDFHeuristicFormulaExtractor:
    """基于 PyMuPDF 字体分析的启发式公式提取工具。

    委托给 ``FormulaReconstructor``，通过字体检测与 Unicode 映射重建 LaTeX。
    """

    @property
    def name(self) -> str:
        return "pymupdf_heuristic"

    def is_available(self) -> bool:
        try:
            from ...pdf._imports import import_fitz

            import_fitz()
            return True
        except ImportError:
            return False

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[FormulaExtractionOutput]:
        """使用 PyMuPDF 字体分析提取公式。"""
        start = time.monotonic()
        try:
            from ...pdf._imports import import_fitz
            from ...pdf.math_formula import FormulaReconstructor

            fitz = import_fitz()
            reconstructor = FormulaReconstructor()

            doc = fitz.open(str(input_data.local_path))
            start_page = 0
            end_page = doc.page_count
            if input_data.page_range:
                start_page = max(0, input_data.page_range[0])
                end_page = min(doc.page_count, input_data.page_range[1])

            formulas: List[ExtractedFormulaV2] = []
            formula_idx = 0

            for page_idx in range(start_page, end_page):
                page = doc[page_idx]
                _, math_regions = reconstructor.extract_formulas_from_page(
                    page, page_idx
                )
                for region in math_regions:
                    bbox = None
                    if region.bbox:
                        bbox = (
                            region.bbox.get("x0", 0),
                            region.bbox.get("y0", 0),
                            region.bbox.get("x1", 0),
                            region.bbox.get("y1", 0),
                        )
                    formulas.append(
                        ExtractedFormulaV2(
                            formula_id=f"formula_{formula_idx}",
                            latex=region.latex,
                            formula_type=region.formula_type,
                            page_number=page_idx,
                            bbox=bbox,
                            original_text=region.original_text,
                        )
                    )
                    formula_idx += 1

            doc.close()

            inline_count = sum(1 for f in formulas if f.formula_type == "inline")
            block_count = sum(1 for f in formulas if f.formula_type == "block")

            output = FormulaExtractionOutput(
                formulas=formulas,
                inline_count=inline_count,
                block_count=block_count,
                metadata={"engine": "pymupdf_heuristic"},
            )

            elapsed = (time.monotonic() - start) * 1000
            return StageResult(
                success=True,
                output=output,
                engine_used="pymupdf_heuristic",
                elapsed_ms=elapsed,
            )

        except Exception as e:
            logger.warning("PyMuPDF 启发式公式提取失败: %s", e)
            return StageResult(
                success=False,
                error=f"PyMuPDF 启发式公式提取失败: {e}",
            )


# ---------------------------------------------------------------------------
# Stage 本地工具映射
# ---------------------------------------------------------------------------

_TOOLS: Dict[str, type] = {
    "mineru": MinerUFormulaExtractor,
    "docling": DoclingFormulaExtractor,
    "pymupdf_heuristic": PyMuPDFHeuristicFormulaExtractor,
}


# ---------------------------------------------------------------------------
# Stage 类
# ---------------------------------------------------------------------------


class FormulaExtractionStage(Stage[PreprocessingOutput, FormulaExtractionOutput]):
    """S5: 公式提取 Stage。"""

    STAGE_ID = "formula_extraction"
    STAGE_NAME = "数学公式提取"
    TOOLS = _TOOLS

    @property
    def stage_id(self) -> str:
        return self.STAGE_ID

    @property
    def stage_name(self) -> str:
        return self.STAGE_NAME

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[FormulaExtractionOutput]:
        """按降级顺序执行公式提取。"""
        for tool_cls in _TOOLS.values():
            tool = tool_cls()
            if tool.is_available():
                result = await tool.execute(input_data)
                if result.success:
                    return result
        return StageResult(success=False, error="无可用的公式提取工具")
