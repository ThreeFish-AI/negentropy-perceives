## Released 2026-04-11

Published to PyPI: https://pypi.org/project/negentropy-perceives/0.2.0a1/

# Changelog

All notable changes to the Data Extractor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## **v0.1.6 (2025/11/27)** - PDF 增强功能与内容深度提取

- ✨ **Transport 支持**: 新增 StreamableHTTP、SSE 传输模式支持，默认使用 StreamableHTTP
- ✨ **PDF 增强处理**: 新增增强版 PDF 处理器，支持图像、表格、数学公式的深度提取
  - **🖼️ 图像提取**: 从 PDF 中提取图像并保存为本地文件或 base64 嵌入，支持尺寸调整和质量优化
  - **📊 表格转换**: 智能识别 PDF 表格并转换为标准 Markdown 表格格式，保持数据结构完整性
  - **🧮 公式提取**: 识别并提取 LaTeX 格式的数学公式，支持内联和块级公式格式保持
  - **📝 结构化输出**: 自动生成包含提取资源的结构化 Markdown 文档，提供详细的提取统计信息
  - **⚙️ 高级配置**: 新增 enhanced_options 参数，支持自定义输出目录、图像格式、质量控制等高级配置

## **v0.1.5 (2025/09/12)** - MCP 工具标准化

- **MCP 工具标准化**: 统一使用 Annotated[*, Field(...)] 参数约束模式，提供清晰的参数描述和示例
- **输出模式优化**: 增强响应模型描述，提升 MCP Client 兼容性

## **v0.1.4 (2025/09/06)**

- **测试体系优化**: 219 个测试用例，通过率 98.6%+，包含单元测试和强化集成测试

## v0.1.3 (2025-09-06)

- **Markdown 转换功能**: 新增 2 个 MCP 工具，包含页面转 Markdown 和批量转换功能
- **测试体系优化**: 162 个测试用例 (131 个单元测试 + 31 个集成测试)，通过率 99.4%

## v0.1.2 (2025-09-06)

- **测试体系搭建**: 建立完整的单元测试和集成测试体系，初始化 19 个基础测试

## v0.1.1 (2025-09-05)

- **核心重构**: 包名从 `scrapy_mcp` 重构为 `extractor`，项目入口命令统一为 `data-extractor`，提升项目结构清晰度

## v0.1.0 (2025-08-26)

- **初始发布**: 核心的网页爬取 MCP Server 实现，10 个专业爬取工具
