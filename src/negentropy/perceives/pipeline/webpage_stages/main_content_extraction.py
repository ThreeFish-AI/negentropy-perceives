"""S4: 主内容区域识别 — 从完整 HTML 中提取文章正文区域（竞争模式）。

三个工具互为竞争：
1. ``trafilatura`` — 调用 ``trafilatura.extract()``（可选依赖）
2. ``readability`` — 调用 ``readability.Document().summary()``（可选依赖）
3. ``beautifulsoup_heuristic`` — 使用现有 ``html_preprocessor.extract_content_area()``

从 ``ctx.raw_html`` 中提取主内容区域，设置 ``ctx.metadata["main_content_html"]``。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..base import StageResult
from ..models import StageContext
from ..registry import register_tool

logger = logging.getLogger(__name__)


@register_tool("trafilatura")
class TrafilaturaTool:
    """基于 trafilatura 的主内容提取工具。

    trafilatura 是一个专门用于网页正文提取的库，在学术网页和新闻站点
    上具备优异的提取精度。
    """

    @property
    def name(self) -> str:
        return "trafilatura"

    def is_available(self) -> bool:
        try:
            import trafilatura  # noqa: F401
            return True
        except ImportError:
            return False

    async def execute(self, ctx: StageContext) -> StageResult[StageContext]:
        """使用 trafilatura 提取主内容。"""
        try:
            import trafilatura
        except ImportError:
            return StageResult(
                success=False,
                error="trafilatura 未安装",
                engine_used=self.name,
            )

        raw_html = ctx.raw_html
        if not raw_html:
            return StageResult(
                success=False,
                error="raw_html 为空，无法提取主内容",
                engine_used=self.name,
            )

        try:
            # trafilatura 支持直接返回 HTML 格式的主内容
            main_html = trafilatura.extract(
                raw_html,
                output_format="html",
                include_tables=True,
                include_images=True,
                include_links=True,
                include_formatting=True,
                url=ctx.url,
            )

            if not main_html:
                return StageResult(
                    success=False,
                    error="trafilatura 未能提取到主内容",
                    engine_used=self.name,
                )

            ctx.metadata["main_content_html"] = main_html

            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"content_length": len(main_html)},
            )
        except Exception as e:
            logger.warning("trafilatura 提取失败: %s", e)
            return StageResult(
                success=False,
                error=f"trafilatura 提取失败: {e}",
                engine_used=self.name,
            )


@register_tool("readability")
class ReadabilityTool:
    """基于 readability-lxml 的主内容提取工具。

    readability-lxml 是 Mozilla Readability 算法的 Python 实现，
    适用于标准文章类页面。
    """

    @property
    def name(self) -> str:
        return "readability"

    def is_available(self) -> bool:
        try:
            from readability import Document  # noqa: F401
            return True
        except ImportError:
            return False

    async def execute(self, ctx: StageContext) -> StageResult[StageContext]:
        """使用 readability-lxml 提取主内容。"""
        try:
            from readability import Document
        except ImportError:
            return StageResult(
                success=False,
                error="readability-lxml 未安装",
                engine_used=self.name,
            )

        raw_html = ctx.raw_html
        if not raw_html:
            return StageResult(
                success=False,
                error="raw_html 为空，无法提取主内容",
                engine_used=self.name,
            )

        try:
            doc = Document(raw_html, url=ctx.url)
            main_html = doc.summary()
            short_title = doc.short_title()

            if not main_html:
                return StageResult(
                    success=False,
                    error="readability 未能提取到主内容",
                    engine_used=self.name,
                )

            ctx.metadata["main_content_html"] = main_html
            # readability 的标题提取通常更精确
            if short_title and not ctx.title:
                ctx.title = short_title

            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"content_length": len(main_html)},
            )
        except Exception as e:
            logger.warning("readability 提取失败: %s", e)
            return StageResult(
                success=False,
                error=f"readability 提取失败: {e}",
                engine_used=self.name,
            )


@register_tool("beautifulsoup_heuristic")
class BeautifulSoupHeuristicTool:
    """基于 BeautifulSoup 启发式规则的主内容提取工具。

    委托给现有 ``html_preprocessor.extract_content_area()``。
    """

    @property
    def name(self) -> str:
        return "beautifulsoup_heuristic"

    def is_available(self) -> bool:
        try:
            from bs4 import BeautifulSoup  # noqa: F401
            return True
        except ImportError:
            return False

    async def execute(self, ctx: StageContext) -> StageResult[StageContext]:
        """使用 BeautifulSoup 启发式规则提取主内容区域。"""
        from ...markdown.html_preprocessor import extract_content_area

        raw_html = ctx.raw_html
        if not raw_html:
            return StageResult(
                success=False,
                error="raw_html 为空，无法提取主内容",
                engine_used=self.name,
            )

        try:
            main_html = extract_content_area(raw_html)

            if not main_html or len(main_html.strip()) < 50:
                return StageResult(
                    success=False,
                    error="BeautifulSoup 启发式未提取到有效主内容",
                    engine_used=self.name,
                )

            ctx.metadata["main_content_html"] = main_html

            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"content_length": len(main_html)},
            )
        except Exception as e:
            logger.warning("BeautifulSoup 启发式提取失败: %s", e)
            return StageResult(
                success=False,
                error=f"BeautifulSoup 启发式提取失败: {e}",
                engine_used=self.name,
            )


# Stage 本地工具映射
TOOLS: Dict[str, type] = {
    "trafilatura": TrafilaturaTool,
    "readability": ReadabilityTool,
    "beautifulsoup_heuristic": BeautifulSoupHeuristicTool,
}

STAGE_ID = "main_content_extraction"
STAGE_NAME = "主内容区域识别"
