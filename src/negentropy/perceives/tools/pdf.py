"""PDF conversion MCP tools."""

import logging
import time
from typing import Annotated, Any, Dict, List, Optional

from pydantic import Field

from ..infra import rate_limiter
from ..schemas import BatchPDFResponse, PDFResponse
from ._registry import (
    PDFMethod,
    PDFOutputFormat,
    app,
    create_pdf_processor,
    elapsed_ms,
    validate_page_range,
)
from ._support import try_pipeline

logger = logging.getLogger(__name__)


@app.tool()
async def convert_pdf_to_markdown(
    pdf_source: Annotated[
        str,
        Field(
            ...,
            description="""PDF 源路径，支持 HTTP/HTTPS URL 或本地文件绝对路径。
                URL 将自动下载处理，本地路径需确保文件存在。
                URL示例："https://example.com/document.pdf"
                本地路径示例："/path/to/document.pdf""",
        ),
    ],
    method: Annotated[
        PDFMethod,
        Field(
            default="auto",
            description="""PDF 提取方法：
                "auto"（自动选择最佳引擎，优先 Docling）、
                "smart"（LLM 编排多引擎并行处理 + 择优融合，最高质量，需配置 LLM API Key）、
                "docling"（Docling 引擎，AI 布局分析 + TableFormer 表格 + 代码检测，适合复杂文档）、
                "mineru"（MinerU 引擎，基于深度学习的文档结构分析，擅长学术论文与多栏排版，支持公式与表格提取）、
                "marker"（Marker 引擎，基于 Nougat 模型，擅长学术文档转换，保留公式与结构化排版）、
                "pymupdf"（PyMuPDF引擎，快速处理）、
                "pypdf"（PyPDF引擎，适合简单文本）""",
        ),
    ],
    include_metadata: Annotated[
        bool,
        Field(
            default=True,
            description="是否在结果中包含 PDF 元数据（标题、作者、创建日期、页数等）和处理统计信息",
        ),
    ],
    page_range: Annotated[
        Optional[List[int]],
        Field(
            default=None,
            description="""页面范围 [start, end] 用于部分提取，两个整数表示起始页和结束页。
                示例：[1, 10]提取第 1-10页。页码从 0 开始计数""",
        ),
    ],
    output_format: Annotated[
        PDFOutputFormat,
        Field(
            default="markdown",
            description="""输出格式选择：
                "markdown"（结构化Markdown文档，保留格式信息）、
                "text"（纯文本内容，去除所有格式）""",
        ),
    ],
    extract_images: bool = True,
    extract_tables: bool = True,
    extract_formulas: bool = True,
    embed_images: bool = False,
    enhanced_options: Optional[Dict[str, Any]] = None,
) -> PDFResponse:
    """
    Convert a PDF document to Markdown format with enhanced content extraction.

    This tool can process PDF files from URLs or local file paths:
    - auto: Automatically choose the best extraction method
    - smart: LLM-orchestrated multi-engine parallel processing with quality fusion
    - docling: Docling engine with AI layout analysis and TableFormer tables
    - mineru: MinerU engine with deep learning-based document structure analysis
    - marker: Marker engine based on Nougat model for academic document conversion
    - pymupdf: Use PyMuPDF (fitz) library for extraction
    - pypdf: Use pypdf library for extraction

    Enhanced Features:
    - Image Extraction: Extract images from PDF and save as local files or embed as base64
    - Table Extraction: Identify and convert tables to standard Markdown table format
    - Formula Extraction: Extract mathematical formulas and preserve LaTeX formatting
    - Content Organization: Automatically organize extracted content in structured sections

    Standard Features:
    - Support for PDF URLs and local file paths
    - Partial page extraction with page range
    - Metadata extraction (title, author, etc.)
    - Text cleaning and Markdown formatting
    - Multiple extraction methods for reliability

    Returns:
        PDFResponse object containing success status, extracted content, metadata, processing method used,
        enhanced assets summary, and page/word count statistics.
    """
    _start = time.time()
    try:
        # Validate page range using shared helper
        page_range_tuple, page_range_error = validate_page_range(page_range)
        if page_range_error:
            return PDFResponse(
                success=False,
                pdf_source=pdf_source,
                method=method,
                output_format=output_format,
                error=page_range_error,
                conversion_time=0,
            )

        logger.info(
            f"Converting PDF to {output_format}: {pdf_source} with method: {method}"
        )

        # Apply rate limiting
        await rate_limiter.wait()

        # Determine output directory for enhanced assets
        output_dir = None
        if enhanced_options and "output_dir" in enhanced_options:
            output_dir = enhanced_options["output_dir"]

        # ── Pipeline 路径（method="auto" 且 Pipeline 配置可用时） ──
        if method == "auto":
            from ..pipeline import run_pdf_pipeline

            pipeline_result = await try_pipeline(
                run_pdf_pipeline,
                success_check=lambda r: getattr(r, "success", False),
                source=pdf_source,
                page_range=page_range_tuple,
                extract_images=extract_images,
                extract_tables=extract_tables,
                extract_formulas=extract_formulas,
                embed_images=embed_images,
                output_dir=output_dir,
            )
            if pipeline_result is not None:
                enhanced_assets = None
                if (
                    pipeline_result.images_count > 0
                    or pipeline_result.tables_count > 0
                ):
                    enhanced_assets = {
                        "images_extracted": pipeline_result.images_count,
                        "tables_extracted": pipeline_result.tables_count,
                        "formulas_extracted": pipeline_result.formulas_count,
                        "code_blocks_detected": pipeline_result.code_blocks_count,
                        "engines_used": pipeline_result.engines_used,
                    }
                return PDFResponse(
                    success=True,
                    pdf_source=pdf_source,
                    method="pipeline_auto",
                    output_format=output_format,
                    content=pipeline_result.markdown,
                    metadata=pipeline_result.metadata,
                    page_count=getattr(pipeline_result, "page_count", 0),
                    word_count=pipeline_result.word_count,
                    conversion_time=elapsed_ms(_start) / 1000.0,
                    enhanced_assets=enhanced_assets,
                )

        # ── 传统路径（直接调用 PDFProcessor） ──

        # Determine if enhanced features should be enabled
        enable_enhanced = extract_images or extract_tables or extract_formulas

        # Process PDF with enhanced features
        pdf_processor = create_pdf_processor(
            enable_enhanced_features=enable_enhanced, output_dir=output_dir
        )
        result = await pdf_processor.process_pdf(
            pdf_source=pdf_source,
            method=method,
            include_metadata=include_metadata,
            page_range=page_range_tuple,
            output_format=output_format,
            extract_images=extract_images,
            extract_tables=extract_tables,
            extract_formulas=extract_formulas,
            embed_images=embed_images,
            enhanced_options=enhanced_options,
        )

        if result.get("success"):
            return PDFResponse(
                success=True,
                pdf_source=pdf_source,
                method=method,
                output_format=output_format,
                content=result.get("content", result.get("markdown", "")),
                metadata=result.get("metadata", {}),
                page_count=result.get(
                    "page_count", result.get("pages_processed", result.get("pages", 0))
                ),
                word_count=result.get("word_count", 0),
                conversion_time=elapsed_ms(_start) / 1000.0,
                enhanced_assets=result.get("enhanced_assets"),
                orchestration_info=result.get("orchestration_info"),
            )
        else:
            return PDFResponse(
                success=False,
                pdf_source=pdf_source,
                method=method,
                output_format=output_format,
                error=result.get("error", "PDF conversion failed"),
                conversion_time=elapsed_ms(_start) / 1000.0,
            )

    except Exception as e:
        logger.error(f"Error converting PDF {pdf_source}: {str(e)}")
        return PDFResponse(
            success=False,
            pdf_source=pdf_source,
            method=method,
            output_format=output_format,
            error=str(e),
            conversion_time=elapsed_ms(_start) / 1000.0,
        )


@app.tool()
async def batch_convert_pdfs_to_markdown(
    pdf_sources: Annotated[
        List[str],
        Field(
            ...,
            description="""PDF 源列表，支持混合使用 URL 和本地文件路径。URL 将并发下载，本地文件需确保存在且可读。
                示例：[
                    "https://example.com/doc1.pdf",
                    "/path/to/doc2.pdf",
                    "https://example.com/doc3.pdf"
                ]""",
        ),
    ],
    method: Annotated[
        PDFMethod,
        Field(
            description="""统一的PDF提取方法：
                "auto"（智能选择最佳引擎）、
                "smart"（LLM 编排多引擎并行处理 + 择优融合，需配置 LLM API Key）、
                "docling"（AI 布局分析 + TableFormer 表格，适合复杂文档）、
                "mineru"（基于深度学习的文档结构分析，擅长学术论文与多栏排版）、
                "marker"（基于 Nougat 模型，擅长学术文档转换，保留公式与结构化排版）、
                "pymupdf"（适合复杂排版和图表）、
                "pypdf"（适合简单纯文本文档）""",
        ),
    ] = "auto",
    include_metadata: Annotated[
        bool,
        Field(
            description="是否在每个转换结果中包含PDF元数据和处理统计，包括文件名、大小、页数、处理时间等",
        ),
    ] = True,
    page_range: Annotated[
        Optional[List[int]],
        Field(
            description="""应用于所有PDF的统一页面范围 [start, end]。如未指定则提取全部页面。页码从 0 开始计数。
                示例：[0, 5] 为所有PDF提取前 5 页""",
        ),
    ] = None,
    output_format: Annotated[
        PDFOutputFormat,
        Field(
            description="""统一输出格式：
                "markdown"（保留标题、列表等结构化信息）、
                "text"（纯文本，去除所有格式化）""",
        ),
    ] = "markdown",
    extract_images: Annotated[
        bool,
        Field(
            description="是否从PDF中提取图像并保存为本地文件，在Markdown文档中引用",
        ),
    ] = True,
    extract_tables: Annotated[
        bool,
        Field(
            description="是否从PDF中提取表格并转换为Markdown表格格式",
        ),
    ] = True,
    extract_formulas: Annotated[
        bool,
        Field(
            description="是否从PDF中提取数学公式并保持LaTeX格式",
        ),
    ] = True,
    embed_images: Annotated[
        bool,
        Field(
            description="是否将提取的图像以base64格式嵌入到Markdown文档中（而非引用本地文件）",
        ),
    ] = False,
    enhanced_options: Annotated[
        Optional[Dict[str, Any]],
        Field(
            description="""统一的增强处理选项，应用于所有URL。
                示例：{"image_size": [800, 600]}""",
        ),
    ] = None,
) -> BatchPDFResponse:
    """
    Convert multiple PDF documents to Markdown format concurrently.

    This tool provides batch processing for converting multiple PDFs to Markdown.
    It processes all PDFs concurrently for better performance.

    Features:
    - Concurrent processing of multiple PDFs
    - Support for both URLs and local file paths
    - Consistent extraction settings across all PDFs
    - Detailed summary statistics
    - Error handling for individual failures
    - Same conversion options as single PDF tool

    Returns:
        BatchPDFResponse object containing success status, batch conversion results, comprehensive statistics
        (total PDFs, success/failure counts, total pages, total words), and individual PDF results.
    """
    try:
        # Validate inputs
        if not pdf_sources:
            return BatchPDFResponse(
                success=False,
                total_pdfs=0,
                successful_count=0,
                failed_count=0,
                results=[],
                total_conversion_time=0,
            )

        # Validate page range using shared helper
        page_range_tuple, page_range_error = validate_page_range(page_range)
        if page_range_error:
            return BatchPDFResponse(
                success=False,
                total_pdfs=len(pdf_sources),
                successful_count=0,
                failed_count=len(pdf_sources),
                results=[],
                total_conversion_time=0,
            )

        start_time = time.time()
        logger.info(
            f"Batch converting {len(pdf_sources)} PDFs to {output_format} with method: {method}"
        )

        # Process all PDFs
        pdf_processor = create_pdf_processor()
        result = await pdf_processor.batch_process_pdfs(
            pdf_sources=pdf_sources,
            method=method,
            include_metadata=include_metadata,
            page_range=page_range_tuple,
            output_format=output_format,
            extract_images=extract_images,
            extract_tables=extract_tables,
            extract_formulas=extract_formulas,
            embed_images=embed_images,
            enhanced_options=enhanced_options,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Convert results to PDFResponse objects
        pdf_responses = []
        for i, result_item in enumerate(result.get("results", [])):
            pdf_source_item = pdf_sources[i] if i < len(pdf_sources) else ""
            pdf_responses.append(
                PDFResponse(
                    success=result_item.get("success", False),
                    pdf_source=pdf_source_item,
                    method=method,
                    output_format=output_format,
                    content=result_item.get("content", ""),
                    metadata=result_item.get("metadata", {}),
                    page_count=result_item.get(
                        "page_count", result_item.get("pages_processed", 0)
                    ),
                    word_count=result_item.get("word_count", 0),
                    conversion_time=result_item.get("conversion_time", 0),
                    error=result_item.get("error"),
                )
            )

        successful_count = sum(1 for r in pdf_responses if r.success)
        failed_count = len(pdf_responses) - successful_count
        total_pages = sum(r.page_count for r in pdf_responses)
        total_word_count = sum(r.word_count for r in pdf_responses)

        return BatchPDFResponse(
            success=result.get("success", False),
            total_pdfs=len(pdf_sources),
            successful_count=successful_count,
            failed_count=failed_count,
            results=pdf_responses,
            total_pages=total_pages,
            total_word_count=total_word_count,
            total_conversion_time=duration_ms / 1000.0,
        )

    except Exception as e:
        duration_ms = (
            int((time.time() - start_time) * 1000) if "start_time" in dir() else 0
        )
        logger.error(f"Error in batch PDF conversion: {str(e)}")
        return BatchPDFResponse(
            success=False,
            total_pdfs=len(pdf_sources) if pdf_sources else 0,
            successful_count=0,
            failed_count=len(pdf_sources) if pdf_sources else 0,
            results=[],
            total_pages=0,
            total_word_count=0,
            total_conversion_time=duration_ms / 1000.0,
        )
