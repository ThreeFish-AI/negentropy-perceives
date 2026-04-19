"""S4: 表格提取 Stage。

结构化表格识别与 Markdown 表格生成。

委托关系：
- ``pdf.docling_engine.DoclingEngine`` — Docling TableFormer 表格识别
- ``pdf.enhanced.EnhancedPDFProcessor`` — PyMuPDF 启发式表格提取
"""

from __future__ import annotations

import logging
from typing import Dict, List

from ...base import Stage, StageResult
from ...models import (
    ExtractedTable,
    PreprocessingOutput,
    TableExtractionOutput,
)
from .._base import PDFToolBase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具适配器
# ---------------------------------------------------------------------------


class DoclingTableExtractor(PDFToolBase):
    """基于 Docling TableFormer 的表格提取工具。"""

    tool_name = "docling"

    def is_available(self) -> bool:
        try:
            from ....pdf.engines.docling import DoclingEngine

            return DoclingEngine.is_available()
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TableExtractionOutput]:
        """使用 Docling 提取结构化表格。"""
        try:
            from ....core.cancellation import current_cancel_scope
            from ....infra import get_engine_pool

            _scope = current_cancel_scope()
            result = await get_engine_pool().run(
                "docling",
                kwargs={
                    "pdf_path": str(input_data.local_path),
                    "page_range": input_data.page_range,
                },
                init_kwargs={"enable_table_structure": True},
                deadline_monotonic=_scope.deadline_monotonic if _scope else None,
            )
            if result is None:
                return StageResult(success=False, error="Docling 转换返回空结果")

            tables: List[ExtractedTable] = []
            for idx, table in enumerate(result.tables):
                tables.append(
                    ExtractedTable(
                        table_id=f"tbl_{idx}",
                        markdown=table.markdown,
                        rows=table.rows,
                        columns=table.columns,
                        page_number=table.page_number or 0,
                        bbox=table.bbox,
                        caption=table.caption,
                    )
                )

            output = TableExtractionOutput(
                tables=tables,
                total_count=len(tables),
                metadata={"engine": "docling"},
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("Docling 表格提取失败: %s", e)
            return StageResult(success=False, error=f"Docling 表格提取失败: {e}")


class FitzTableExtractor(PDFToolBase):
    """基于 PyMuPDF 的启发式表格提取工具。

    委托给 ``EnhancedPDFProcessor.extract_tables_with_geometry()``。
    """

    tool_name = "pymupdf"

    def is_available(self) -> bool:
        try:
            from ....pdf._imports import import_fitz

            import_fitz()
            return True
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TableExtractionOutput]:
        """使用 PyMuPDF 启发式提取表格。"""
        try:
            from ....pdf._imports import import_fitz
            from ....pdf.enhanced import EnhancedPDFProcessor

            fitz = import_fitz()
            processor = EnhancedPDFProcessor()

            doc = fitz.open(str(input_data.local_path))
            start_page = 0
            end_page = doc.page_count
            if input_data.page_range:
                start_page = max(0, input_data.page_range[0])
                end_page = min(doc.page_count, input_data.page_range[1])

            tables: List[ExtractedTable] = []
            table_idx = 0

            for page_idx in range(start_page, end_page):
                page = doc[page_idx]
                # 使用 EnhancedPDFProcessor 的表格提取能力
                page_tables = processor.extract_tables_with_geometry(page, page_idx)  # type: ignore[call-arg]
                for extracted_table in page_tables:  # type: ignore[union-attr]
                    tables.append(
                        ExtractedTable(
                            table_id=f"tbl_{table_idx}",
                            markdown=extracted_table.markdown,  # type: ignore[union-attr]
                            rows=extracted_table.rows,  # type: ignore[union-attr]
                            columns=extracted_table.columns,  # type: ignore[union-attr]
                            page_number=page_idx,
                            bbox=extracted_table.bbox,  # type: ignore[union-attr]
                            caption=extracted_table.caption,  # type: ignore[union-attr]
                            headers=extracted_table.headers,  # type: ignore[union-attr]
                        )
                    )
                    table_idx += 1

            doc.close()

            output = TableExtractionOutput(
                tables=tables,
                total_count=len(tables),
                metadata={"engine": "pymupdf"},
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("PyMuPDF 表格提取失败: %s", e)
            return StageResult(success=False, error=f"PyMuPDF 表格提取失败: {e}")


class CamelotTableExtractor(PDFToolBase):
    """基于 Camelot 的表格提取工具。"""

    tool_name = "camelot"

    def is_available(self) -> bool:
        try:
            import camelot  # noqa: F401

            return True
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TableExtractionOutput]:
        """使用 Camelot 提取表格。"""
        try:
            import camelot

            pages = "all"
            if input_data.page_range:
                # Camelot 页码从 1 开始
                start_p = input_data.page_range[0] + 1
                end_p = input_data.page_range[1]
                pages = f"{start_p}-{end_p}"

            raw_tables = camelot.read_pdf(str(input_data.local_path), pages=pages)

            tables: List[ExtractedTable] = []
            for idx, table in enumerate(raw_tables):
                md = table.df.to_markdown(index=False)
                rows, cols = table.df.shape
                tables.append(
                    ExtractedTable(
                        table_id=f"tbl_{idx}",
                        markdown=md,
                        rows=rows,
                        columns=cols,
                        page_number=table.page - 1,  # 转为 0-based
                    )
                )

            output = TableExtractionOutput(
                tables=tables,
                total_count=len(tables),
                metadata={"engine": "camelot"},
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("Camelot 表格提取失败: %s", e)
            return StageResult(success=False, error=f"Camelot 表格提取失败: {e}")


class PDFPlumberTableExtractor(PDFToolBase):
    """基于 pdfplumber 的表格提取工具。"""

    tool_name = "pdfplumber"

    def is_available(self) -> bool:
        try:
            import pdfplumber  # noqa: F401

            return True
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TableExtractionOutput]:
        """使用 pdfplumber 提取表格。"""
        try:
            import pdfplumber

            pdf = pdfplumber.open(str(input_data.local_path))
            start_page = 0
            end_page = len(pdf.pages)
            if input_data.page_range:
                start_page = max(0, input_data.page_range[0])
                end_page = min(len(pdf.pages), input_data.page_range[1])

            tables: List[ExtractedTable] = []
            table_idx = 0

            for page_idx in range(start_page, end_page):
                page = pdf.pages[page_idx]
                page_tables = page.extract_tables()
                for raw_table in page_tables:
                    if not raw_table:
                        continue
                    # 构建 Markdown 表格
                    headers = raw_table[0] if raw_table else []
                    md_lines = []
                    if headers:
                        md_lines.append(
                            "| " + " | ".join(str(h or "") for h in headers) + " |"
                        )
                        md_lines.append(
                            "| " + " | ".join("---" for _ in headers) + " |"
                        )
                    for row in raw_table[1:]:
                        md_lines.append(
                            "| " + " | ".join(str(c or "") for c in row) + " |"
                        )

                    md = "\n".join(md_lines)
                    tables.append(
                        ExtractedTable(
                            table_id=f"tbl_{table_idx}",
                            markdown=md,
                            rows=len(raw_table) - 1,
                            columns=len(headers),
                            page_number=page_idx,
                            headers=[str(h or "") for h in headers],
                        )
                    )
                    table_idx += 1

            pdf.close()

            output = TableExtractionOutput(
                tables=tables,
                total_count=len(tables),
                metadata={"engine": "pdfplumber"},
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("pdfplumber 表格提取失败: %s", e)
            return StageResult(success=False, error=f"pdfplumber 表格提取失败: {e}")


# ---------------------------------------------------------------------------
# Stage 本地工具映射
# ---------------------------------------------------------------------------

_TOOLS: Dict[str, type] = {
    "docling": DoclingTableExtractor,
    "camelot": CamelotTableExtractor,
    "pdfplumber": PDFPlumberTableExtractor,
    "pymupdf": FitzTableExtractor,
}


# ---------------------------------------------------------------------------
# Stage 类
# ---------------------------------------------------------------------------


class TableExtractionStage(Stage[PreprocessingOutput, TableExtractionOutput]):
    """S4: 表格提取 Stage。"""

    STAGE_ID = "table_extraction"
    STAGE_NAME = "表格识别与提取"
    TOOLS = _TOOLS

    @property
    def stage_id(self) -> str:
        return self.STAGE_ID

    @property
    def stage_name(self) -> str:
        return self.STAGE_NAME

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TableExtractionOutput]:
        """按降级顺序执行表格提取。"""
        for tool_cls in _TOOLS.values():
            tool = tool_cls()
            if tool.is_available():
                result = await tool.execute(input_data)
                if result.success:
                    return result
        return StageResult(success=False, error="无可用的表格提取工具")
