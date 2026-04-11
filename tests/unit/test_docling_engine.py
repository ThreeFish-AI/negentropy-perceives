"""Docling 引擎封装模块的单元测试。

测试策略：
- 当 Docling 未安装时：验证 is_available() 返回 False，convert() 返回 None
- 当 Docling 已安装时：使用 mock 验证 pipeline 配置和转换流程
- 数据类完整性验证
- 图片保存到磁盘验证
- Caption 提取多层降级验证
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from negentropy.perceives.pdf.docling_engine import (
    DoclingCodeBlock,
    DoclingConversionResult,
    DoclingEngine,
    DoclingFormula,
    DoclingImage,
    DoclingTable,
)


# ============================================================
# 数据类完整性
# ============================================================
class TestDoclingDataClasses:
    """验证标准化数据类的字段与默认值。"""

    def test_conversion_result_defaults(self) -> None:
        result = DoclingConversionResult(markdown="# Test")
        assert result.markdown == "# Test"
        assert result.tables == []
        assert result.images == []
        assert result.formulas == []
        assert result.code_blocks == []
        assert result.metadata == {}
        assert result.page_count == 0

    def test_conversion_result_full(self) -> None:
        result = DoclingConversionResult(
            markdown="# Full",
            tables=[DoclingTable(markdown="| A |", rows=1, columns=1)],
            images=[DoclingImage(page_number=0, caption="Fig 1")],
            formulas=[DoclingFormula(latex=r"\alpha", formula_type="inline")],
            code_blocks=[DoclingCodeBlock(code="print(1)", language="python")],
            metadata={"title": "Test Doc"},
            page_count=5,
        )
        assert result.page_count == 5
        assert len(result.tables) == 1
        assert len(result.images) == 1
        assert len(result.formulas) == 1
        assert len(result.code_blocks) == 1

    def test_docling_table_defaults(self) -> None:
        table = DoclingTable(markdown="| A | B |")
        assert table.rows == 0
        assert table.columns == 0
        assert table.page_number is None
        assert table.caption is None

    def test_docling_image_defaults(self) -> None:
        img = DoclingImage()
        assert img.page_number is None
        assert img.caption is None
        assert img.classification is None

    def test_docling_image_extended_fields_defaults(self) -> None:
        """验证 DoclingImage 新增字段的默认值。"""
        img = DoclingImage()
        assert img.filename is None
        assert img.local_path is None
        assert img.width is None
        assert img.height is None
        assert img.mime_type == "image/png"
        assert img.base64_data is None

    def test_docling_image_with_extended_fields(self) -> None:
        """验证 DoclingImage 新增字段可正常赋值。"""
        img = DoclingImage(
            page_number=1,
            caption="Figure 1",
            filename="img_p1_0.png",
            local_path="/tmp/img_p1_0.png",
            width=800,
            height=600,
            base64_data="abc123",
        )
        assert img.filename == "img_p1_0.png"
        assert img.local_path == "/tmp/img_p1_0.png"
        assert img.width == 800
        assert img.height == 600
        assert img.base64_data == "abc123"

    def test_docling_formula_defaults(self) -> None:
        formula = DoclingFormula(latex=r"\sum")
        assert formula.formula_type == "block"
        assert formula.page_number is None

    def test_docling_code_block_defaults(self) -> None:
        cb = DoclingCodeBlock(code="x = 1")
        assert cb.language is None
        assert cb.page_number is None


# ============================================================
# 可用性检测
# ============================================================
class TestDoclingEngineAvailability:
    """测试 Docling 可用性检测。"""

    def test_is_available_returns_bool(self) -> None:
        """返回值应为布尔类型。"""
        result = DoclingEngine.is_available()
        assert isinstance(result, bool)

    def test_convert_returns_none_when_unavailable(self) -> None:
        """Docling 不可用时 convert() 应安全返回 None。"""
        engine = DoclingEngine()
        with patch.object(DoclingEngine, "is_available", return_value=False):
            result = engine.convert("/fake/path.pdf")
            assert result is None


# ============================================================
# 配置签名
# ============================================================
class TestDoclingEngineConfigKey:
    """验证配置签名生成。"""

    @patch("negentropy.perceives.pdf.device_config.get_device_for_docling", return_value="cpu")
    def test_default_config_key(self, _mock: object) -> None:
        engine = DoclingEngine(device="cpu")
        key = engine._config_key()
        assert "tbl=True:accurate" in key
        assert "code=True" in key
        assert "formula=True" in key
        assert "dev=cpu" in key

    @patch("negentropy.perceives.pdf.device_config.get_device_for_docling", return_value="cpu")
    def test_custom_config_key(self, _mock: object) -> None:
        engine = DoclingEngine(
            enable_table_structure=False,
            table_mode="fast",
            enable_code_enrichment=False,
            device="cpu",
        )
        key = engine._config_key()
        assert "tbl=False:fast" in key
        assert "code=False" in key

    @patch("negentropy.perceives.pdf.device_config.get_device_for_docling", return_value="cpu")
    def test_different_configs_produce_different_keys(self, _mock: object) -> None:
        e1 = DoclingEngine(table_mode="accurate", device="cpu")
        e2 = DoclingEngine(table_mode="fast", device="cpu")
        assert e1._config_key() != e2._config_key()

    @patch("negentropy.perceives.pdf.device_config.get_device_for_docling", return_value="cpu")
    def test_config_key_includes_device(self, _mock: object) -> None:
        """配置签名应包含设备信息。"""
        engine = DoclingEngine(device="cpu")
        key = engine._config_key()
        assert "dev=cpu" in key
        assert "threads=" in key

    @patch("negentropy.perceives.pdf.device_config.get_device_for_docling", side_effect=lambda d: d if d and d != "auto" else "cpu")
    def test_different_devices_produce_different_cache_keys(self, _mock: object) -> None:
        """不同设备的引擎应产生不同缓存键。"""
        e_cpu = DoclingEngine(device="cpu")
        e_mps = DoclingEngine(device="mps")
        assert e_cpu._config_key() != e_mps._config_key()


# ============================================================
# Caption 提取
# ============================================================
class TestSafeCaption:
    """测试 _safe_caption 多层降级逻辑。"""

    def test_caption_text_preferred(self) -> None:
        """应优先使用 caption_text(doc)。"""
        mock_item = MagicMock()
        mock_item.caption_text.return_value = "Figure 1: Architecture"
        mock_doc = MagicMock()

        result = DoclingEngine._safe_caption(mock_item, mock_doc)
        assert result == "Figure 1: Architecture"
        mock_item.caption_text.assert_called_once_with(mock_doc)

    def test_caption_text_empty_falls_through(self) -> None:
        """caption_text 返回空字符串时应降级到 captions 列表。"""
        mock_caption = MagicMock()
        mock_caption.text = "Table 1"

        mock_item = MagicMock()
        mock_item.caption_text.return_value = ""
        mock_item.captions = [mock_caption]
        mock_doc = MagicMock()

        result = DoclingEngine._safe_caption(mock_item, mock_doc)
        assert result == "Table 1"

    def test_fallback_to_captions_text(self) -> None:
        """caption_text 不可用时应降级为 captions[0].text。"""
        mock_caption = MagicMock()
        mock_caption.text = "Table 1: Results"

        mock_item = MagicMock(spec=[])
        mock_item.captions = [mock_caption]

        result = DoclingEngine._safe_caption(mock_item, None)
        assert result == "Table 1: Results"

    def test_fallback_to_ref_resolve(self) -> None:
        """captions[0] 为 RefItem 时应通过 resolve(doc) 解析。"""
        mock_resolved = MagicMock()
        mock_resolved.text = "Resolved caption"

        mock_ref = MagicMock(spec=[])
        mock_ref.text = None  # RefItem 没有 .text
        mock_ref.resolve = MagicMock(return_value=mock_resolved)

        mock_item = MagicMock(spec=[])
        mock_item.captions = [mock_ref]
        mock_doc = MagicMock()

        result = DoclingEngine._safe_caption(mock_item, mock_doc)
        assert result == "Resolved caption"

    def test_empty_captions_returns_empty(self) -> None:
        """captions 为空列表时应返回空字符串。"""
        mock_item = MagicMock(spec=[])
        mock_item.captions = []

        result = DoclingEngine._safe_caption(mock_item, None)
        assert result == ""

    def test_no_doc_skips_caption_text(self) -> None:
        """doc 为 None 时不应调用 caption_text。"""
        mock_caption = MagicMock()
        mock_caption.text = "Direct text"

        mock_item = MagicMock()
        mock_item.captions = [mock_caption]

        result = DoclingEngine._safe_caption(mock_item, None)
        assert result == "Direct text"
        # caption_text 不应被调用
        mock_item.caption_text.assert_not_called()


# ============================================================
# 结构化数据提取（使用 mock）
# ============================================================
class TestDoclingResultExtraction:
    """测试从 mock DoclingDocument 中提取结构化数据。"""

    def test_extract_tables(self) -> None:
        """应从 DoclingDocument.tables 中提取表格。"""
        mock_table = MagicMock()
        mock_table.export_to_markdown.return_value = "| A | B |\n|---|---|\n| 1 | 2 |"
        mock_table.data.num_rows = 1
        mock_table.data.num_cols = 2
        mock_table.captions = []
        mock_table.prov = []

        engine = DoclingEngine()
        mock_doc = MagicMock()
        mock_doc.tables = [mock_table]

        tables = engine._extract_tables(mock_doc)
        assert len(tables) == 1
        assert tables[0].rows == 1
        assert tables[0].columns == 2
        assert "|" in tables[0].markdown

    def test_extract_tables_with_caption(self) -> None:
        """应通过 caption_text(doc) 提取表格标题。"""
        mock_table = MagicMock()
        mock_table.export_to_markdown.return_value = "| X |"
        mock_table.data.num_rows = 1
        mock_table.data.num_cols = 1
        mock_table.caption_text.return_value = "Table 1: Results"
        mock_table.prov = []

        engine = DoclingEngine()
        mock_doc = MagicMock()
        mock_doc.tables = [mock_table]

        tables = engine._extract_tables(mock_doc)
        assert tables[0].caption == "Table 1: Results"

    def test_extract_tables_no_tables_attr(self) -> None:
        """DoclingDocument 无 tables 属性时应返回空列表。"""
        engine = DoclingEngine()
        mock_doc = MagicMock(spec=[])  # 无任何属性
        tables = engine._extract_tables(mock_doc)
        assert tables == []

    def test_extract_images_saves_to_disk(self, tmp_path: Path) -> None:
        """应从 DoclingDocument.pictures 中提取图片并保存到磁盘。"""
        from PIL import Image

        mock_pil_image = Image.new("RGB", (100, 50), "red")

        mock_pic = MagicMock()
        mock_pic.captions = []
        mock_pic.classification = "chart"
        mock_pic.prov = []
        mock_pic.image = None
        mock_pic.get_image.return_value = mock_pil_image

        engine = DoclingEngine(output_dir=str(tmp_path))
        mock_doc = MagicMock()
        mock_doc.pictures = [mock_pic]

        images = engine._extract_images(mock_doc)
        assert len(images) == 1
        assert images[0].classification == "chart"
        assert images[0].width == 100
        assert images[0].height == 50
        assert images[0].filename is not None
        assert images[0].local_path is not None
        assert Path(images[0].local_path).exists()
        assert images[0].base64_data is not None

    def test_extract_images_get_image_failure_graceful(self, tmp_path: Path) -> None:
        """get_image 失败时应降级为仅记录元数据。"""
        mock_pic = MagicMock()
        mock_pic.captions = []
        mock_pic.classification = "photo"
        mock_pic.prov = []
        mock_pic.image = None
        mock_pic.get_image.side_effect = RuntimeError("No image data")

        engine = DoclingEngine(output_dir=str(tmp_path))
        mock_doc = MagicMock()
        mock_doc.pictures = [mock_pic]

        images = engine._extract_images(mock_doc)
        assert len(images) == 1
        assert images[0].classification == "photo"
        assert images[0].filename is None
        assert images[0].local_path is None
        assert images[0].width is None

    def test_extract_images_no_pictures_attr(self) -> None:
        """DoclingDocument 无 pictures 属性时应返回空列表。"""
        engine = DoclingEngine()
        mock_doc = MagicMock(spec=[])
        images = engine._extract_images(mock_doc)
        assert images == []

    def test_extract_images_creates_output_dir(self) -> None:
        """output_dir 为 None 时应自动创建临时目录。"""
        mock_pic = MagicMock()
        mock_pic.captions = []
        mock_pic.classification = None
        mock_pic.prov = []
        mock_pic.image = None
        mock_pic.get_image.return_value = None  # 无图片数据

        engine = DoclingEngine(output_dir=None)
        mock_doc = MagicMock()
        mock_doc.pictures = [mock_pic]

        images = engine._extract_images(mock_doc)
        assert len(images) == 1
        # output_dir 应已被设置
        assert engine._output_dir is not None

    def test_extract_formulas_from_markdown(self) -> None:
        """应从 Markdown 文本中提取公式。"""
        engine = DoclingEngine()
        md = r"Given $\alpha + \beta$ and $$E = mc^2$$ done."

        formulas = engine._extract_formulas(MagicMock(), md)
        block = [f for f in formulas if f.formula_type == "block"]
        inline = [f for f in formulas if f.formula_type == "inline"]

        assert len(block) == 1
        assert "mc^2" in block[0].latex
        assert len(inline) == 1
        assert r"\alpha" in inline[0].latex

    def test_extract_code_blocks(self) -> None:
        """应从 DoclingDocument 中提取代码块。"""
        mock_item = MagicMock()
        mock_item.label = "code"
        mock_item.text = "def hello():\n    print('world')"
        mock_item.code_language = "python"
        mock_item.prov = []

        engine = DoclingEngine()
        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(mock_item, 0)]

        code_blocks = engine._extract_code_blocks(mock_doc)
        assert len(code_blocks) == 1
        assert code_blocks[0].language == "python"
        assert "def hello" in code_blocks[0].code

    def test_extract_code_blocks_no_iterate(self) -> None:
        """DoclingDocument 无 iterate_items 时应返回空列表。"""
        engine = DoclingEngine()
        mock_doc = MagicMock(spec=[])
        code_blocks = engine._extract_code_blocks(mock_doc)
        assert code_blocks == []

    def test_extract_metadata(self) -> None:
        """应提取文档元数据。"""
        engine = DoclingEngine()
        mock_doc = MagicMock()
        mock_doc.name = "Test Document"
        mock_doc.origin.filename = "test.pdf"
        mock_doc.origin.mimetype = "application/pdf"

        metadata = engine._extract_metadata(mock_doc)
        assert metadata["title"] == "Test Document"
        assert metadata["filename"] == "test.pdf"

    def test_get_page_number_with_prov(self) -> None:
        """应从 prov 中获取页码。"""
        mock_prov = MagicMock()
        mock_prov.page_no = 3
        mock_item = MagicMock()
        mock_item.prov = [mock_prov]

        assert DoclingEngine._get_page_number(mock_item) == 3

    def test_get_page_number_no_prov(self) -> None:
        """无 prov 时应返回 None。"""
        mock_item = MagicMock()
        mock_item.prov = []
        assert DoclingEngine._get_page_number(mock_item) is None


# ============================================================
# page_range 透传
# ============================================================
class TestDoclingEnginePageRange:
    """验证 page_range 正确透传至 Docling DocumentConverter。"""

    def _make_mock_converter(self) -> MagicMock:
        """构造 mock converter，其 convert() 返回有效的 ConversionResult。"""
        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Mock"
        mock_doc.tables = []
        mock_doc.pictures = []
        mock_doc.pages = []
        mock_doc.name = "mock"
        mock_doc.origin = None

        mock_result = MagicMock()
        mock_result.document = mock_doc
        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result
        return mock_converter

    @patch("negentropy.perceives.pdf.device_config.get_device_for_docling", return_value="cpu")
    def test_page_range_passed_to_converter(self, _mock_device: object) -> None:
        """page_range=(80, 82) 应转换为 Docling 1-based (81, 82) 并传递。"""
        engine = DoclingEngine(device="cpu")
        mock_converter = self._make_mock_converter()

        with patch.object(engine, "_get_converter", return_value=mock_converter):
            engine.convert("/fake.pdf", page_range=(80, 82))

        mock_converter.convert.assert_called_once()
        call_kwargs = mock_converter.convert.call_args
        assert call_kwargs.kwargs["page_range"] == (81, 82)

    @patch("negentropy.perceives.pdf.device_config.get_device_for_docling", return_value="cpu")
    def test_no_page_range_omits_kwarg(self, _mock_device: object) -> None:
        """page_range=None 时不应传递 page_range 给 converter。"""
        engine = DoclingEngine(device="cpu")
        mock_converter = self._make_mock_converter()

        with patch.object(engine, "_get_converter", return_value=mock_converter):
            engine.convert("/fake.pdf")

        call_kwargs = mock_converter.convert.call_args
        assert "page_range" not in call_kwargs.kwargs

    @patch("negentropy.perceives.pdf.device_config.get_device_for_docling", return_value="cpu")
    def test_single_page_range(self, _mock_device: object) -> None:
        """page_range=(0, 1) 应转换为 Docling (1, 1)（单页）。"""
        engine = DoclingEngine(device="cpu")
        mock_converter = self._make_mock_converter()

        with patch.object(engine, "_get_converter", return_value=mock_converter):
            engine.convert("/fake.pdf", page_range=(0, 1))

        call_kwargs = mock_converter.convert.call_args
        assert call_kwargs.kwargs["page_range"] == (1, 1)


# ============================================================
# 缓存管理
# ============================================================
class TestDoclingEngineCacheManagement:
    """测试 converter 缓存管理。"""

    def test_reset_cache(self) -> None:
        """reset_cache() 应清空 _converters 字典。"""
        DoclingEngine._converters["test_key"] = "dummy"
        DoclingEngine.reset_cache()
        assert len(DoclingEngine._converters) == 0


# ============================================================
# PDFProcessor Docling 集成（单元层面）
# ============================================================
class TestPDFProcessorDoclingIntegration:
    """验证 PDFProcessor 的 Docling 集成逻辑。"""

    def test_prefer_docling_default(self) -> None:
        """prefer_docling 默认为 True。"""
        from negentropy.perceives.pdf.processor import PDFProcessor

        proc = PDFProcessor(enable_enhanced_features=False)
        assert proc.prefer_docling is True
        proc.cleanup()

    def test_prefer_docling_false(self) -> None:
        """prefer_docling=False 时不初始化 Docling 引擎。"""
        from negentropy.perceives.pdf.processor import PDFProcessor

        proc = PDFProcessor(enable_enhanced_features=False, prefer_docling=False)
        assert proc._docling_engine is None
        proc.cleanup()

    def test_supported_methods_includes_docling(self) -> None:
        """supported_methods 应包含 'docling'。"""
        from negentropy.perceives.pdf.processor import PDFProcessor

        proc = PDFProcessor(enable_enhanced_features=False)
        assert "docling" in proc.supported_methods
        proc.cleanup()

    def test_build_result_from_docling(self) -> None:
        """_build_result_from_docling 应生成标准输出格式。"""
        from negentropy.perceives.pdf.processor import PDFProcessor

        proc = PDFProcessor(enable_enhanced_features=False, prefer_docling=False)
        try:
            docling_result = DoclingConversionResult(
                markdown="# Test\n\nContent here.",
                tables=[DoclingTable(markdown="| A |", rows=1, columns=1)],
                images=[DoclingImage(page_number=0, caption="Fig 1")],
                formulas=[DoclingFormula(latex=r"\alpha", formula_type="inline")],
                code_blocks=[
                    DoclingCodeBlock(code="x=1", language="python")
                ],
                metadata={"title": "Test"},
                page_count=3,
            )

            result = proc._build_result_from_docling(
                docling_result,
                pdf_source="/tmp/test.pdf",
                include_metadata=True,
                output_format="markdown",
            )

            assert result["success"] is True
            assert result["method_used"] == "docling"
            assert result["pages_processed"] == 3
            assert result["word_count"] > 0
            assert "markdown" in result
            assert result["enhanced_assets"]["tables"]["count"] == 1
            assert result["enhanced_assets"]["images"]["count"] == 1
            assert result["enhanced_assets"]["formulas"]["count"] == 1
            assert result["enhanced_assets"]["code_blocks"]["count"] == 1
            assert "python" in result["enhanced_assets"]["code_blocks"]["languages"]
            assert result["metadata"]["title"] == "Test"
        finally:
            proc.cleanup()

    def test_build_result_includes_image_details(self) -> None:
        """enhanced_assets.images 应包含文件路径和尺寸信息。"""
        from negentropy.perceives.pdf.processor import PDFProcessor

        proc = PDFProcessor(enable_enhanced_features=False, prefer_docling=False)
        try:
            docling_result = DoclingConversionResult(
                markdown="# Test",
                images=[
                    DoclingImage(
                        page_number=0,
                        caption="Fig 1",
                        filename="img_p0_0.png",
                        local_path="/tmp/img_p0_0.png",
                        width=800,
                        height=600,
                    )
                ],
                page_count=1,
            )
            result = proc._build_result_from_docling(
                docling_result,
                pdf_source="/tmp/test.pdf",
                include_metadata=True,
                output_format="markdown",
            )
            img_item = result["enhanced_assets"]["images"]["items"][0]
            assert img_item["filename"] == "img_p0_0.png"
            assert img_item["local_path"] == "/tmp/img_p0_0.png"
            assert img_item["width"] == 800
            assert img_item["height"] == 600
            assert img_item["mime_type"] == "image/png"
            # files 列表
            assert "img_p0_0.png" in result["enhanced_assets"]["images"]["files"]
        finally:
            proc.cleanup()

    def test_build_result_includes_table_markdown(self) -> None:
        """enhanced_assets.tables items 应包含 markdown 内容。"""
        from negentropy.perceives.pdf.processor import PDFProcessor

        proc = PDFProcessor(enable_enhanced_features=False, prefer_docling=False)
        try:
            docling_result = DoclingConversionResult(
                markdown="# Test",
                tables=[
                    DoclingTable(
                        markdown="| A | B |\n|---|---|\n| 1 | 2 |",
                        rows=1,
                        columns=2,
                        caption="Table 1",
                    )
                ],
                page_count=1,
            )
            result = proc._build_result_from_docling(
                docling_result,
                pdf_source="/tmp/test.pdf",
                include_metadata=True,
                output_format="markdown",
            )
            table_item = result["enhanced_assets"]["tables"]["items"][0]
            assert "markdown" in table_item
            assert "| A | B |" in table_item["markdown"]
            assert table_item["caption"] == "Table 1"
        finally:
            proc.cleanup()

    def test_build_result_text_format(self) -> None:
        """output_format='text' 时不应包含 markdown 键。"""
        from negentropy.perceives.pdf.processor import PDFProcessor

        proc = PDFProcessor(enable_enhanced_features=False, prefer_docling=False)
        try:
            docling_result = DoclingConversionResult(
                markdown="Content",
                page_count=1,
            )
            result = proc._build_result_from_docling(
                docling_result,
                pdf_source="/tmp/test.pdf",
                include_metadata=False,
                output_format="text",
            )
            assert "markdown" not in result
            assert "metadata" not in result
            assert result["text"] == "Content"
        finally:
            proc.cleanup()
