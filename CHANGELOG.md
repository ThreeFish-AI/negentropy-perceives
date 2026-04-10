# Changelog

All notable changes to the Negentropy Perceives project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.2.0 - MVP

### ✨ 核心亮点

- **PDF 智能处理**: 5 引擎降级链，LLM 三阶段编排（分析→调度→融合）
- **反检测抓取**: Selenium + Playwright 隐身引擎，人类行为模拟绕过反爬
- **Markdown 转换**: Web Page → Markdown 管线，含 9 阶段格式化器
- **工程架构**: 5 层架构，12 个 MCP 工具覆盖 6 大领域

### 🔧 更多特性

- **结构化提取**: CSS 选择器映射 + 6 种数据模板，robots.txt 合规检查
- **PDF 深度内容**: 表格识别、LaTeX 公式保持、图像嵌入，支持增强模式
- **4 层配置体系**: 内置默认 → 用户 YAML → 环境变量 → CLI（pydantic-settings）
- **弹性基础设施**: 指数退避重试、频率限速、内存缓存（TTL 24h）
- **多传输模式**: STDIO / StreamableHTTP / SSE，默认 StreamableHTTP
- **Python SDK**: 异步 NegentropyPerceivesClient，类型安全的便捷方法
- **批量并发**: 网页批量抓取、PDF 批量转换均支持 asyncio 并发处理
