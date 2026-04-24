"""响应数据模型定义。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LinkItem(BaseModel):
    """单个链接项模型。"""

    url: str = Field(..., description="链接URL")
    text: str = Field(..., description="链接文本")
    is_internal: bool = Field(..., description="是否为内部链接")


class LinksResponse(BaseModel):
    """链接提取的响应模型。"""

    success: bool = Field(..., description="操作是否成功")
    url: str = Field(..., description="源页面URL")
    total_links: int = Field(..., description="总链接数量")
    links: List[LinkItem] = Field(..., description="提取的链接列表")
    internal_links_count: int = Field(..., description="内部链接数量")
    external_links_count: int = Field(..., description="外部链接数量")
    error: Optional[str] = Field(default=None, description="错误信息（如果有）")


class PageInfoResponse(BaseModel):
    """页面信息的响应模型。"""

    success: bool = Field(..., description="操作是否成功")
    url: str = Field(..., description="页面URL")
    title: Optional[str] = Field(default=None, description="页面标题")
    description: Optional[str] = Field(default=None, description="页面描述")
    status_code: int = Field(..., description="HTTP状态码")
    content_type: Optional[str] = Field(default=None, description="内容类型")
    content_length: Optional[int] = Field(default=None, description="内容长度")
    last_modified: Optional[str] = Field(default=None, description="最后修改时间")
    error: Optional[str] = Field(default=None, description="错误信息（如果有）")


class MarkdownResponse(BaseModel):
    """Markdown 转换的响应模型。"""

    success: bool = Field(..., description="操作是否成功")
    url: str = Field(..., description="源页面URL")
    method: str = Field(..., description="使用的转换方法")
    markdown_content: Optional[str] = Field(
        default=None, description="转换后的Markdown内容"
    )
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="页面元数据")
    word_count: int = Field(default=0, description="字数统计")
    images_embedded: int = Field(default=0, description="嵌入的图片数量")
    conversion_time: float = Field(..., description="转换耗时（秒）")
    error: Optional[str] = Field(default=None, description="错误信息（如果有）")


class BatchMarkdownResponse(BaseModel):
    """批量 Markdown 转换的响应模型。"""

    success: bool = Field(..., description="整体操作是否成功")
    total_urls: int = Field(..., description="总URL数量")
    successful_count: int = Field(..., description="成功转换的数量")
    failed_count: int = Field(..., description="失败的数量")
    results: List[MarkdownResponse] = Field(..., description="每个URL的转换结果")
    total_word_count: int = Field(default=0, description="总字数")
    total_conversion_time: float = Field(..., description="总转换时间（秒）")


class ImageAssetModel(BaseModel):
    """PDF 响应中内嵌的图片资产（base64 载荷）。

    与 :class:`negentropy.perceives.pipeline.models.ImageAsset` 配对的
    Pydantic 视图：前者用于内部流水线，后者用于对外 MCP 响应的序列化与校验。
    字段保持一一对应。
    """

    filename: str = Field(..., description="文件名（如 img_p1_0.png）")
    mime_type: str = Field(default="image/png", description="MIME 类型")
    base64_data: str = Field(..., description="Base64 编码后的图片字节")
    width: Optional[int] = Field(default=None, description="图片宽度（像素）")
    height: Optional[int] = Field(default=None, description="图片高度（像素）")
    caption: Optional[str] = Field(default=None, description="图片说明文字")
    page_number: Optional[int] = Field(
        default=None, description="所在页码（从 0 开始）"
    )
    downscaled: bool = Field(
        default=False,
        description="是否经过 JPEG q=75 重压缩（超过单图 base64 阈值时触发）",
    )


class PDFResponse(BaseModel):
    """PDF 增强转换的响应模型。"""

    success: bool = Field(..., description="操作是否成功")
    pdf_source: str = Field(..., description="PDF源路径或URL")
    method: str = Field(..., description="使用的转换方法")
    output_format: str = Field(..., description="输出格式")
    content: Optional[str] = Field(default=None, description="转换后的内容")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="PDF元数据")
    page_count: int = Field(default=0, description="页数")
    word_count: int = Field(default=0, description="字数统计")
    conversion_time: float = Field(..., description="转换耗时（秒）")
    enhanced_assets: Optional[Dict[str, Any]] = Field(
        default=None, description="增强资源提取统计（图像、表格、公式）"
    )
    image_assets: Optional[List[ImageAssetModel]] = Field(
        default=None,
        description=(
            "随响应透出的图片 base64 资产列表。"
            "受配置项 pdf_bundle_images_in_response 门控；关闭或无图时为 None。"
        ),
    )
    orchestration_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="LLM 编排信息（仅 method=smart 时存在）",
    )
    error: Optional[str] = Field(default=None, description="错误信息（如果有）")


class BatchPDFResponse(BaseModel):
    """批量 PDF 转换的响应模型。"""

    success: bool = Field(..., description="整体操作是否成功")
    total_pdfs: int = Field(..., description="总PDF数量")
    successful_count: int = Field(..., description="成功转换的数量")
    failed_count: int = Field(..., description="失败的数量")
    results: List[PDFResponse] = Field(..., description="每个PDF的转换结果")
    total_pages: int = Field(default=0, description="总页数")
    total_word_count: int = Field(default=0, description="总字数")
    total_conversion_time: float = Field(..., description="总转换时间（秒）")
