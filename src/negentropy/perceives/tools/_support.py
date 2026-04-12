"""工具层共享类型别名、输入校验与计时工具。"""

import logging
import time
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar

from ..infra.parsing import validate_url as validate_url  # noqa: F401 – re-exported

logger = logging.getLogger(__name__)

T = TypeVar("T")


def elapsed_ms(start_time: float) -> int:
    """计算开始时间到当前的毫秒耗时。"""
    return int((time.time() - start_time) * 1000)


ScrapeMethod = Literal[
    "auto", "simple", "selenium", "stealth_selenium", "stealth_playwright"
]
PDFMethod = Literal["auto", "pymupdf", "pypdf", "docling", "smart", "mineru", "marker"]
PDFOutputFormat = Literal["markdown", "text"]


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


async def try_pipeline(
    pipeline_fn: Callable[..., Any],
    *,
    success_check: Callable[[Any], bool],
    **kwargs: Any,
) -> Optional[Any]:
    """尝试 Pipeline 路径，失败时返回 None（降级到传统路径）。

    封装 "尝试 Pipeline → 失败则降级" 的通用模式，
    供 MCP 工具层的 PDF 和 Markdown 转换工具共用。

    Args:
        pipeline_fn: Pipeline 执行函数（如 ``run_pdf_pipeline``）
        success_check: 判断 Pipeline 结果是否成功的回调
        **kwargs: 传递给 pipeline_fn 的参数

    Returns:
        Pipeline 成功时返回结果，失败时返回 None
    """
    try:
        result = await pipeline_fn(**kwargs)
        if success_check(result):
            return result
        error_msg = getattr(result, "error", None) or result.get("error", "")
        logger.info("Pipeline 路径失败，降级到传统路径: %s", error_msg)
    except Exception as exc:
        logger.info("Pipeline 路径异常，降级到传统路径: %s", exc)
    return None
