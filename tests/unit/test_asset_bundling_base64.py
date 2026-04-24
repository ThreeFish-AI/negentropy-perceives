"""单元测试：`_build_image_assets` 将 ExtractedImage 打包为响应侧 ImageAsset。

动机：`pipeline/convenience.py` 在构造最终 `PipelineResult` 时调用
`_build_image_assets` 把图片以 base64 内嵌到响应，补齐此前 MCP 响应仅回传
`images_count` 而无像素数据的缺口。测试覆盖四条路径：

1. 配置关闭时输出为空；
2. 单图超 ``pdf_image_max_base64_kb`` → 走 JPEG q=75 重压缩（若 PIL 可用）
   并标记 ``downscaled=True``；无效图/压缩仍超限 → 跳过；
3. 累计超 ``pdf_bundle_total_base64_mb`` → 保序丢弃尾部；
4. 优先使用 ``base64_data`` 字段；否则回退读 ``local_path``。
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

from negentropy.perceives.pipeline.convenience import _build_image_assets
from negentropy.perceives.pipeline.models import (
    ExtractedImage,
    ImageExtractionOutput,
)


# ── 辅助：构造 ExtractedImage ─────────────────────────────────────────────────


def _png_bytes(n: int, byte: int = 0xAB) -> bytes:
    """返回固定字节的伪 PNG 字节串；不需要是合法 PNG，_build_image_assets
    只在超限重压缩路径才会调用 PIL.Image.open。"""
    return bytes([byte]) * n


def _make_img(
    filename: str,
    *,
    raw: bytes | None = None,
    local_path: str | None = None,
    width: int = 64,
    height: int = 48,
    page: int = 0,
    caption: str | None = None,
    mime: str = "image/png",
) -> ExtractedImage:
    b64 = base64.b64encode(raw).decode("ascii") if raw is not None else None
    return ExtractedImage(
        image_id=filename.split(".")[0],
        filename=filename,
        local_path=local_path,
        base64_data=b64,
        mime_type=mime,
        width=width,
        height=height,
        page_number=page,
        bbox=None,
        caption=caption,
    )


def _make_output(images: List[ExtractedImage]) -> ImageExtractionOutput:
    return ImageExtractionOutput(
        images=images,
        total_count=len(images),
        metadata={"engine": "pymupdf", "page_count": len(images)},
    )


# ── 用例 ────────────────────────────────────────────────────────────────────


class TestBuildImageAssetsToggle:
    def test_empty_when_disabled(self) -> None:
        out = _make_output([_make_img("a.png", raw=_png_bytes(100))])
        with patch(
            "negentropy.perceives.pipeline.convenience.settings"
        ) as mock_settings:
            mock_settings.pdf_bundle_images_in_response = False
            mock_settings.pdf_image_max_base64_kb = 2048
            mock_settings.pdf_bundle_total_base64_mb = 32
            assets = _build_image_assets(out)
        assert assets == []

    def test_empty_when_output_none(self) -> None:
        with patch(
            "negentropy.perceives.pipeline.convenience.settings"
        ) as mock_settings:
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2048
            mock_settings.pdf_bundle_total_base64_mb = 32
            assert _build_image_assets(None) == []

    def test_empty_when_output_has_no_images(self) -> None:
        out = ImageExtractionOutput(images=[], total_count=0, metadata={})
        with patch(
            "negentropy.perceives.pipeline.convenience.settings"
        ) as mock_settings:
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2048
            mock_settings.pdf_bundle_total_base64_mb = 32
            assert _build_image_assets(out) == []


class TestBuildImageAssetsHappyPath:
    def test_base64_source_preferred_and_mapped(self) -> None:
        raw = _png_bytes(200, byte=0x11)
        out = _make_output(
            [
                _make_img(
                    "img_p0_0.png",
                    raw=raw,
                    width=640,
                    height=480,
                    page=0,
                    caption="Fig 1",
                )
            ]
        )
        with patch(
            "negentropy.perceives.pipeline.convenience.settings"
        ) as mock_settings:
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2048
            mock_settings.pdf_bundle_total_base64_mb = 32
            assets = _build_image_assets(out)

        assert len(assets) == 1
        a = assets[0]
        assert a.filename == "img_p0_0.png"
        assert a.mime_type == "image/png"
        assert base64.b64decode(a.base64_data) == raw
        assert a.width == 640
        assert a.height == 480
        assert a.page_number == 0
        assert a.caption == "Fig 1"
        assert a.downscaled is False

    def test_local_path_fallback_when_no_base64(self, tmp_path: Path) -> None:
        p = tmp_path / "x.png"
        raw = _png_bytes(128, byte=0x22)
        p.write_bytes(raw)
        out = _make_output([_make_img("x.png", raw=None, local_path=str(p))])
        with patch(
            "negentropy.perceives.pipeline.convenience.settings"
        ) as mock_settings:
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2048
            mock_settings.pdf_bundle_total_base64_mb = 32
            assets = _build_image_assets(out)
        assert len(assets) == 1
        assert base64.b64decode(assets[0].base64_data) == raw

    def test_missing_both_sources_is_skipped(self) -> None:
        out = _make_output([_make_img("ghost.png", raw=None, local_path=None)])
        with patch(
            "negentropy.perceives.pipeline.convenience.settings"
        ) as mock_settings:
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2048
            mock_settings.pdf_bundle_total_base64_mb = 32
            assets = _build_image_assets(out)
        assert assets == []


class TestBuildImageAssetsSizeGuards:
    def test_over_single_limit_compressed_and_kept(self) -> None:
        """单图超限 → 走 JPEG 重压缩；若压缩后过阈值则收录且标记 downscaled。"""
        big_raw = _png_bytes(3 * 1024, byte=0x33)  # 3KB
        out = _make_output([_make_img("big.png", raw=big_raw)])

        # 假装 PIL 重压缩返回一个 1KB 的小结果
        small_jpeg = _png_bytes(1024, byte=0x44)
        with (
            patch(
                "negentropy.perceives.pipeline.convenience.settings"
            ) as mock_settings,
            patch(
                "negentropy.perceives.pipeline.convenience._downscale_to_jpeg",
                return_value=small_jpeg,
            ),
        ):
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2  # 2KB 阈值
            mock_settings.pdf_bundle_total_base64_mb = 32
            assets = _build_image_assets(out)

        assert len(assets) == 1
        a = assets[0]
        assert a.mime_type == "image/jpeg"
        assert a.filename.endswith(".jpg")
        assert a.downscaled is True
        assert base64.b64decode(a.base64_data) == small_jpeg

    def test_over_single_limit_recompress_still_too_large_is_dropped(self) -> None:
        """JPEG 重压缩仍超限 → 跳过该图。"""
        big_raw = _png_bytes(4 * 1024, byte=0x55)
        out = _make_output([_make_img("big.png", raw=big_raw)])

        # PIL 返回 3KB（仍超过 2KB 阈值）
        recompressed = _png_bytes(3 * 1024, byte=0x66)
        with (
            patch(
                "negentropy.perceives.pipeline.convenience.settings"
            ) as mock_settings,
            patch(
                "negentropy.perceives.pipeline.convenience._downscale_to_jpeg",
                return_value=recompressed,
            ),
        ):
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2  # 2KB
            mock_settings.pdf_bundle_total_base64_mb = 32
            assets = _build_image_assets(out)

        assert assets == []

    def test_over_single_limit_compression_unavailable_is_dropped(self) -> None:
        """PIL 缺失或压缩抛错 → _downscale_to_jpeg 返回 None → 跳过。"""
        big_raw = _png_bytes(3 * 1024, byte=0x77)
        out = _make_output([_make_img("big.png", raw=big_raw)])
        with (
            patch(
                "negentropy.perceives.pipeline.convenience.settings"
            ) as mock_settings,
            patch(
                "negentropy.perceives.pipeline.convenience._downscale_to_jpeg",
                return_value=None,
            ),
        ):
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2
            mock_settings.pdf_bundle_total_base64_mb = 32
            assets = _build_image_assets(out)

        assert assets == []

    def test_total_cap_stops_appending(self) -> None:
        """累计字节超过 pdf_bundle_total_base64_mb → 按原顺序停止。"""
        # 三张每张 1MB，总量阈值 2MB → 收录前两张，第三张被丢弃
        one_mb = 1024 * 1024
        raws = [_png_bytes(one_mb, byte=i) for i in (0x01, 0x02, 0x03)]
        out = _make_output([_make_img(f"p{i}.png", raw=r) for i, r in enumerate(raws)])
        with patch(
            "negentropy.perceives.pipeline.convenience.settings"
        ) as mock_settings:
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2048  # 足够单张过关
            mock_settings.pdf_bundle_total_base64_mb = 2  # 总量 2MB
            assets = _build_image_assets(out)

        assert [a.filename for a in assets] == ["p0.png", "p1.png"]


class TestInvalidBase64:
    def test_invalid_base64_is_skipped(self) -> None:
        """ExtractedImage.base64_data 非法 → 吞异常、跳过该图。"""
        img = ExtractedImage(
            image_id="bad",
            filename="bad.png",
            local_path=None,
            base64_data="$$$not-base64$$$",
            mime_type="image/png",
        )
        out = _make_output([img])
        with patch(
            "negentropy.perceives.pipeline.convenience.settings"
        ) as mock_settings:
            mock_settings.pdf_bundle_images_in_response = True
            mock_settings.pdf_image_max_base64_kb = 2048
            mock_settings.pdf_bundle_total_base64_mb = 32
            assets = _build_image_assets(out)
        assert assets == []


class TestDownscaleToJpegReal:
    """集成真实 PIL 的重压缩路径。若 PIL 不可用自动 skip。"""

    def test_real_downscale_produces_jpeg(self) -> None:
        pil = pytest.importorskip("PIL.Image")
        import io

        # 用 PIL 先造一张真正的 PNG
        im = pil.new("RGB", (256, 256), color=(123, 45, 67))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        from negentropy.perceives.pipeline.convenience import _downscale_to_jpeg

        out = _downscale_to_jpeg(png_bytes, quality=75)
        assert out is not None
        assert out[:3] == b"\xff\xd8\xff"  # JPEG SOI 标记
