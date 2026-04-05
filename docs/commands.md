---
id: commands
sidebar_position: 5
title: 常用 Commands
description: 开发者快速参考卡片：独有运维命令与权威文档索引
last_update:
  author: Aurelius
  date: 2025-11-22
tags:
  - Commands
  - Quick Reference
---

> 本文档定位为**开发者快速参考卡片**，收录其他文档未覆盖的独有命令。各领域的完整指南请通过下方链接跳转至对应权威文档。

## 环境设置与安装

→ 完整环境配置指南见 [开发指南 · 环境配置](./development.md#环境配置)

## 服务器启动

### 基本启动

```bash
# 启动 MCP 服务器（主要启动命令）
uv run negentropy-perceives

# 以 Python 模块方式运行服务器
uv run python -m negentropy.perceives
```

命令入口统一为 `negentropy-perceives`。

### 开发模式启动

```bash
# 启用调试级别日志输出
uv run --env NEGENTROPY_PERCEIVES_LOG_LEVEL=DEBUG negentropy-perceives

# 启用完整功能特性的开发配置
uv run --env NEGENTROPY_PERCEIVES_ENABLE_JAVASCRIPT=true \
          --env NEGENTROPY_PERCEIVES_USE_RANDOM_USER_AGENT=true \
          negentropy-perceives
```

> 全部环境变量配置项见 [配置系统](./configuration.md)

## 代码质量检查

→ 基础 Ruff / MyPy / Pre-commit 命令见 [开发指南 · 代码质量保障](./development.md#代码质量保障)

### 高级用法

```bash
# 查看 Ruff 所有可用的检查规则
uv run ruff rule --all

# MyPy 显示详细的错误代码信息
uv run mypy src/negentropy/perceives/ --show-error-codes

# MyPy 生成 HTML 格式的类型检查报告
uv run mypy src/negentropy/perceives/ --html-report mypy-report
```

## 测试执行

→ 完整测试脚本与 pytest 命令见 [测试指南 · 测试执行](./testing.md#-测试执行)

## 项目依赖管理

### 依赖包操作

```bash
# 添加生产环境依赖包
uv add <package-name>

# 添加开发环境依赖包
uv add --dev <package-name>

# 移除不需要的依赖包
uv remove <package-name>

# 更新所有依赖到最新版本
uv lock --upgrade

# 检查项目中过时的依赖
uv tree --outdated
```

### 依赖信息查询

```bash
# 显示完整的依赖关系树
uv tree

# 列出当前虚拟环境中安装的所有包
uv list

# 显示特定包的详细信息
uv pip show <package-name>
```

## 项目维护

### 版本号查询

```bash
# 版本号在 pyproject.toml 中维护，运行时由 src/negentropy/perceives/__init__.py 动态读取
# 查看当前项目版本号
uv run python -c "from negentropy.perceives import __version__; print(__version__)"
```

### 缓存清理

```bash
# 清理 uv 包管理器的缓存
uv cache clean

# 清理 pip 包管理器的缓存
uv pip cache purge

# 清理 Python 编译产生的字节码文件
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
```

### 构建与发布

→ 完整构建发布流程见 [开发指南 · 发布流程](./development.md#发布流程)

## 系统调试与诊断

```bash
# 检查 Negentropy Perceives 相关的环境变量
printenv | grep DATA_EXTRACTOR

# 验证配置文件的正确性
uv run python -c "from negentropy.perceives.config import settings; print(settings.model_dump())"

# 测试项目模块导入是否正常
uv run python -c "import negentropy.perceives; print('Import successful')"

# 检查 MCP 服务器可用的工具列表
uv run python -c "from negentropy.perceives.tools import app; print([tool.name for tool in app.tools])"
```
