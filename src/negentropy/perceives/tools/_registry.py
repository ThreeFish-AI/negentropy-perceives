"""MCP 工具注册枢纽。"""

import logging
from typing import Optional

from fastmcp import FastMCP

from ..config import settings
from ..markdown.converter import MarkdownConverter
from ..scraping import WebScraper
from ._support import (
    PDFMethod,
    PDFOutputFormat,
    ScrapeMethod,
    elapsed_ms,
    normalize_extract_config as _normalize_extract_config,
    validate_page_range as _validate_page_range,
    validate_url as _validate_url,
)

logger = logging.getLogger(__name__)

__all__ = [
    # 类型别名
    "ScrapeMethod",
    "PDFMethod",
    "PDFOutputFormat",
    # FastMCP 实例
    "app",
    # 共享服务实例
    "web_scraper",
    "markdown_converter",
    # 工厂函数
    "create_pdf_processor",
    # 辅助函数
    "validate_url",
    "validate_page_range",
    "normalize_extract_config",
    "elapsed_ms",
]

# FastMCP application instance
app = FastMCP(settings.server_name, version=settings.server_version)

# Shared service instances
web_scraper = WebScraper()
markdown_converter = MarkdownConverter()


def create_pdf_processor(
    enable_enhanced_features: bool = True, output_dir: Optional[str] = None
):
    """获取 PDF 处理器实例，延迟导入以避免启动警告"""
    from ..pdf import PDFProcessor

    return PDFProcessor(
        enable_enhanced_features=enable_enhanced_features, output_dir=output_dir
    )


# 直接赋值导出（消除纯转发的中间层）
validate_url = _validate_url
validate_page_range = _validate_page_range
normalize_extract_config = _normalize_extract_config
