# Changelog

All notable changes to the Negentropy Perceives project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.2.0 — 隐身的眼睛，睁开了

> 给 AI Agent 装上一双能看懂网页和 PDF 的眼睛，而且这双眼睛会隐身。

### ✨ 核心亮点

- **复杂 PDF，一句话搞定** — 5 引擎自动降级 + LLM 三阶段编排（分析→并行调度→择优融合）
- **反爬墙？穿墙** — Selenium / Playwright 隐身双引擎，鼠标轨迹 + 随机延迟，无感绕过
- **网页→Markdown，9 道工序精炼** — 去噪、表格对齐、代码检测、排版复原，一步到位
- **12 工具 · 6 领域 · 5 层架构** — 退避 + 限速 + 缓存三层弹性护盾，生产级底座

### 🔧 更多特性

- **结构化提取**: CSS 选择器精准映射 + 5 种数据模板，内置 robots.txt 合规检查
- **PDF 深度内容**: 表格识别、LaTeX 公式保持、图像 base64 嵌入，增强模式可选
- **4 层配置体系**: 内置默认 → 用户 YAML → 环境变量 → CLI（pydantic-settings 驱动）
- **多传输模式**: STDIO / StreamableHTTP / SSE，默认 StreamableHTTP，开箱即用
- **异步 SDK**: NegentropyPerceivesClient，类型安全，async/await 原生
- **批量并发**: 网页批抓、PDF 批转均走 asyncio，吞吐拉满
