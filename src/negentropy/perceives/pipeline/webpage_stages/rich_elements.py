"""S6-S9: 并行富元素提取 — 数学公式 / 代码块 / 表格 / 图片。

将四个相关但独立的子 Stage 合并为一个模块，通过 ``asyncio.gather()``
并行执行，最大化吞吐。各子 Stage 从 ``ctx.cleaned_html``（或
``ctx.raw_html``）中提取对应富元素，写入 ``ctx`` 的相应字段。

子 Stage 一览：
- S6: 数学公式提取（MathJax/KaTeX/MathML → LaTeX）
- S7: 代码块识别（``<pre><code>`` → CodeBlock）
- S8: 表格提取（``<table>`` → TableData）
- S9: 图片提取（``<img>`` → ImageInfo）
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from ..base import StageResult
from ..models import (
    CodeBlock,
    ImageInfo,
    MathFormula,
    StageContext,
    TableData,
)
from ..registry import register_tool

logger = logging.getLogger(__name__)


# =============================================================================
# 工具函数（内部使用，非注册工具）
# =============================================================================


def _get_source_html(ctx: StageContext) -> str:
    """获取用于富元素提取的源 HTML。

    优先使用 ``raw_html``（保留了原始数学/代码元素），
    因为 ``cleaned_html`` 可能已将数学元素替换为 LaTeX 文本。
    """
    return ctx.raw_html or ctx.cleaned_html


# ---------------------------------------------------------------------------
# S6: 数学公式提取
# ---------------------------------------------------------------------------


async def _extract_math_formulas(ctx: StageContext) -> List[MathFormula]:
    """从 HTML 中提取数学公式。

    检测来源：
    - MathJax ``<script type="math/tex">``
    - MathJax 渲染容器 ``.MathJax``
    - KaTeX 容器 ``.katex``
    - MathML ``<math>`` 标签
    - 内联 LaTeX（``$...$`` / ``$$...$$``）
    """
    html = _get_source_html(ctx)
    if not html:
        return []

    formulas: List[MathFormula] = []

    try:
        soup = BeautifulSoup(html, "html.parser")

        # 1. MathJax <script type="math/tex">
        for script in soup.find_all("script", type=re.compile(r"math/tex")):
            latex = (script.string or "").strip()
            if not latex:
                continue
            script_type = script.get("type", "")
            is_display = "display" in script_type
            formulas.append(MathFormula(
                latex=latex,
                formula_type="block" if is_display else "inline",
                original_html=str(script),
                source_format="mathjax",
            ))

        # 2. MathJax 渲染容器
        for container in soup.find_all(class_=re.compile(r"MathJax")):
            latex = _extract_latex_annotation(container)
            if latex:
                classes = container.get("class", [])
                is_display = any("Display" in c or "display" in c for c in classes)
                formulas.append(MathFormula(
                    latex=latex,
                    formula_type="block" if is_display else "inline",
                    original_html=str(container)[:500],
                    source_format="mathjax",
                ))

        # 3. KaTeX 容器
        for container in soup.find_all(class_=re.compile(r"katex")):
            latex = _extract_latex_annotation(container)
            if latex:
                classes = container.get("class", [])
                is_display = any("display" in c for c in classes)
                formulas.append(MathFormula(
                    latex=latex,
                    formula_type="block" if is_display else "inline",
                    original_html=str(container)[:500],
                    source_format="katex",
                ))

        # 4. MathML <math>
        for math_elem in soup.find_all("math"):
            latex = _extract_latex_annotation(math_elem)
            if latex:
                display = math_elem.get("display", "")
                formulas.append(MathFormula(
                    latex=latex,
                    formula_type="block" if display == "block" else "inline",
                    original_html=str(math_elem)[:500],
                    source_format="mathml",
                ))

    except Exception as e:
        logger.warning("数学公式提取失败: %s", e)

    return formulas


def _extract_latex_annotation(element: Tag) -> Optional[str]:
    """从 MathML/MathJax/KaTeX 容器中提取 LaTeX annotation。"""
    if element is None:
        return None
    for annotation in element.find_all("annotation"):
        encoding = annotation.get("encoding", "")
        if "tex" in encoding.lower() or "latex" in encoding.lower():
            latex = annotation.string
            if latex:
                return latex.strip()
    return None


# ---------------------------------------------------------------------------
# S7: 代码块识别
# ---------------------------------------------------------------------------


async def _extract_code_blocks(ctx: StageContext) -> List[CodeBlock]:
    """从 HTML 中提取代码块。

    检测 ``<pre><code>`` 和独立的 ``<pre>`` 标签。
    """
    html = _get_source_html(ctx)
    if not html:
        return []

    blocks: List[CodeBlock] = []

    try:
        soup = BeautifulSoup(html, "html.parser")

        for pre in soup.find_all("pre"):
            code_tag = pre.find("code")
            if code_tag:
                code_text = code_tag.get_text()
                language = _detect_language_from_class(code_tag)
            else:
                code_text = pre.get_text()
                language = None

            code_text = code_text.strip()
            if not code_text:
                continue

            blocks.append(CodeBlock(
                code=code_text,
                language=language,
                original_html=str(pre)[:1000],
            ))

    except Exception as e:
        logger.warning("代码块提取失败: %s", e)

    return blocks


def _detect_language_from_class(element: Tag) -> Optional[str]:
    """从 HTML class 属性中检测编程语言。

    常见模式：``language-python``, ``lang-js``, ``highlight-java``
    """
    classes = element.get("class", [])
    for cls in classes:
        if not isinstance(cls, str):
            continue
        # language-xxx / lang-xxx
        for prefix in ("language-", "lang-", "highlight-"):
            if cls.startswith(prefix):
                return cls[len(prefix):]
        # 直接匹配常见语言名
        lower = cls.lower()
        if lower in (
            "python", "javascript", "typescript", "java", "c", "cpp",
            "csharp", "go", "rust", "ruby", "php", "swift", "kotlin",
            "scala", "html", "css", "sql", "bash", "shell", "json",
            "yaml", "xml", "markdown",
        ):
            return lower
    return None


# ---------------------------------------------------------------------------
# S8: 表格提取
# ---------------------------------------------------------------------------


async def _extract_tables(ctx: StageContext) -> List[TableData]:
    """从 HTML 中提取表格结构。"""
    html = ctx.cleaned_html or ctx.raw_html
    if not html:
        return []

    tables: List[TableData] = []

    try:
        soup = BeautifulSoup(html, "html.parser")

        for table_tag in soup.find_all("table"):
            rows_data: List[List[str]] = []
            for tr in table_tag.find_all("tr"):
                cells = []
                for cell in tr.find_all(["th", "td"]):
                    cell_text = cell.get_text(strip=True).replace("|", "\\|")
                    cells.append(cell_text)
                if cells:
                    rows_data.append(cells)

            if len(rows_data) < 1:
                continue

            # 规范化列数
            max_cols = max(len(row) for row in rows_data) if rows_data else 0
            for row in rows_data:
                while len(row) < max_cols:
                    row.append("")

            # 构建 Markdown 表格
            md_lines = []
            if rows_data:
                md_lines.append("| " + " | ".join(rows_data[0]) + " |")
                md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
                for row in rows_data[1:]:
                    md_lines.append("| " + " | ".join(row) + " |")

            markdown = "\n".join(md_lines)

            # 尝试提取 caption
            caption_tag = table_tag.find("caption")
            caption = caption_tag.get_text(strip=True) if caption_tag else None

            # 表头
            headers = rows_data[0] if rows_data else None

            tables.append(TableData(
                markdown=markdown,
                rows=len(rows_data),
                columns=max_cols,
                headers=headers,
                caption=caption,
                original_html=str(table_tag)[:2000],
            ))

    except Exception as e:
        logger.warning("表格提取失败: %s", e)

    return tables


# ---------------------------------------------------------------------------
# S9: 图片提取
# ---------------------------------------------------------------------------


async def _extract_images(ctx: StageContext) -> List[ImageInfo]:
    """从 HTML 中提取图片信息。"""
    html = ctx.cleaned_html or ctx.raw_html
    if not html:
        return []

    images: List[ImageInfo] = []

    try:
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")

        for img_tag in soup.find_all("img"):
            src = img_tag.get("src", "")
            if not src:
                continue

            # 解析相对路径
            if ctx.url and not src.startswith(("http://", "https://", "data:")):
                src = urljoin(ctx.url, src)

            alt = img_tag.get("alt", "")
            title = img_tag.get("title", "")

            # 尝试获取尺寸
            width = _parse_int(img_tag.get("width"))
            height = _parse_int(img_tag.get("height"))

            images.append(ImageInfo(
                src=src,
                alt=alt,
                title=title,
                width=width,
                height=height,
            ))

    except Exception as e:
        logger.warning("图片提取失败: %s", e)

    return images


def _parse_int(value: Any) -> Optional[int]:
    """安全地将属性值转换为整数。"""
    if value is None:
        return None
    try:
        return int(str(value).replace("px", "").strip())
    except (ValueError, TypeError):
        return None


# =============================================================================
# 注册工具：四个子 Stage 的统一入口
# =============================================================================


@register_tool("beautifulsoup_math")
class MathFormulaTool:
    """S6: 数学公式提取工具。"""

    @property
    def name(self) -> str:
        return "beautifulsoup_math"

    def is_available(self) -> bool:
        try:
            from bs4 import BeautifulSoup  # noqa: F401
            return True
        except ImportError:
            return False

    async def execute(self, ctx: StageContext) -> StageResult[StageContext]:
        """提取数学公式。"""
        try:
            formulas = await _extract_math_formulas(ctx)
            ctx.formulas = formulas
            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"formula_count": len(formulas)},
            )
        except Exception as e:
            ctx.errors.append(f"数学公式提取失败: {e}")
            return StageResult(
                success=True,  # 非致命错误
                output=ctx,
                engine_used=self.name,
                metadata={"formula_count": 0, "error": str(e)},
            )


@register_tool("beautifulsoup_code")
class CodeBlockTool:
    """S7: 代码块识别工具。"""

    @property
    def name(self) -> str:
        return "beautifulsoup_code"

    def is_available(self) -> bool:
        try:
            from bs4 import BeautifulSoup  # noqa: F401
            return True
        except ImportError:
            return False

    async def execute(self, ctx: StageContext) -> StageResult[StageContext]:
        """识别代码块。"""
        try:
            blocks = await _extract_code_blocks(ctx)
            ctx.code_blocks = blocks
            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"code_block_count": len(blocks)},
            )
        except Exception as e:
            ctx.errors.append(f"代码块识别失败: {e}")
            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"code_block_count": 0, "error": str(e)},
            )


@register_tool("beautifulsoup_table")
class TableTool:
    """S8: 表格提取工具。"""

    @property
    def name(self) -> str:
        return "beautifulsoup_table"

    def is_available(self) -> bool:
        try:
            from bs4 import BeautifulSoup  # noqa: F401
            return True
        except ImportError:
            return False

    async def execute(self, ctx: StageContext) -> StageResult[StageContext]:
        """提取表格数据。"""
        try:
            tables = await _extract_tables(ctx)
            ctx.tables = tables
            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"table_count": len(tables)},
            )
        except Exception as e:
            ctx.errors.append(f"表格提取失败: {e}")
            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"table_count": 0, "error": str(e)},
            )


@register_tool("beautifulsoup_image")
class ImageTool:
    """S9: 图片提取工具。"""

    @property
    def name(self) -> str:
        return "beautifulsoup_image"

    def is_available(self) -> bool:
        try:
            from bs4 import BeautifulSoup  # noqa: F401
            return True
        except ImportError:
            return False

    async def execute(self, ctx: StageContext) -> StageResult[StageContext]:
        """提取图片信息。"""
        try:
            images = await _extract_images(ctx)
            ctx.images = images
            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"image_count": len(images)},
            )
        except Exception as e:
            ctx.errors.append(f"图片提取失败: {e}")
            return StageResult(
                success=True,
                output=ctx,
                engine_used=self.name,
                metadata={"image_count": 0, "error": str(e)},
            )


# =============================================================================
# 并行执行入口（供编排器直接调用）
# =============================================================================


async def extract_all_rich_elements(ctx: StageContext) -> Dict[str, Any]:
    """并行提取所有富元素，返回聚合统计。

    此函数通过 ``asyncio.gather()`` 并行执行 S6-S9 四个子任务。
    结果直接写入 ``ctx`` 的对应字段。
    """
    results = await asyncio.gather(
        _extract_math_formulas(ctx),
        _extract_code_blocks(ctx),
        _extract_tables(ctx),
        _extract_images(ctx),
        return_exceptions=True,
    )

    stats: Dict[str, Any] = {}

    # S6: 公式
    if isinstance(results[0], list):
        ctx.formulas = results[0]
        stats["formula_count"] = len(results[0])
    else:
        ctx.errors.append(f"数学公式提取异常: {results[0]}")
        stats["formula_count"] = 0

    # S7: 代码块
    if isinstance(results[1], list):
        ctx.code_blocks = results[1]
        stats["code_block_count"] = len(results[1])
    else:
        ctx.errors.append(f"代码块识别异常: {results[1]}")
        stats["code_block_count"] = 0

    # S8: 表格
    if isinstance(results[2], list):
        ctx.tables = results[2]
        stats["table_count"] = len(results[2])
    else:
        ctx.errors.append(f"表格提取异常: {results[2]}")
        stats["table_count"] = 0

    # S9: 图片
    if isinstance(results[3], list):
        ctx.images = results[3]
        stats["image_count"] = len(results[3])
    else:
        ctx.errors.append(f"图片提取异常: {results[3]}")
        stats["image_count"] = 0

    return stats


# Stage 本地工具映射
TOOLS: Dict[str, type] = {
    "beautifulsoup_math": MathFormulaTool,
    "beautifulsoup_code": CodeBlockTool,
    "beautifulsoup_table": TableTool,
    "beautifulsoup_image": ImageTool,
}

STAGE_ID = "rich_elements"
STAGE_NAME = "并行富元素提取"
