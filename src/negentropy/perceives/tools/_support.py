"""工具层共享类型别名与输入校验。"""

from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse


ScrapeMethod = Literal[
    "auto", "simple", "selenium", "stealth_selenium", "stealth_playwright"
]
PDFMethod = Literal["auto", "pymupdf", "pypdf", "docling", "smart", "mineru", "marker"]
PDFOutputFormat = Literal["markdown", "text"]


def validate_url(url: str) -> Optional[str]:
    """校验 URL 格式。"""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return "Invalid URL format"
    return None


def validate_page_range(
    page_range: Optional[List[int]],
) -> tuple[Optional[tuple], Optional[str]]:
    """校验并转换 page_range。"""
    if not page_range:
        return None, None
    if len(page_range) != 2:
        return None, "Page range must contain exactly 2 elements: [start, end]"
    if page_range[0] < 0 or page_range[1] < 0:
        return None, "Page numbers must be non-negative"
    if page_range[0] >= page_range[1]:
        return None, "Start page must be less than end page"
    return tuple(page_range), None


def normalize_extract_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """规范化提取配置字典。"""
    if not isinstance(config, dict):
        raise ValueError("Extract config must be a dictionary")

    normalized: Dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str):
            normalized[key] = {"selector": value, "multiple": True}
            continue

        if not isinstance(value, dict):
            raise ValueError(f"Invalid config value for key '{key}'")
        if "selector" not in value:
            raise ValueError(f"Missing 'selector' for key '{key}'")

        normalized[key] = {
            "selector": value["selector"],
            "attr": value.get("attr", "text"),
            "multiple": value.get("multiple", False),
            "type": value.get("type", "css"),
        }

    return normalized
