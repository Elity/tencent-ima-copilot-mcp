# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

腾讯 IMA Copilot MCP 服务器是一个基于 fastmcp v2 的 Model Context Protocol 应用，**使用环境变量配置**，将腾讯 IMA Copilot 的 Web 版本功能封装为 MCP 服务，提供通用知识库问答功能。

## 技术架构

### 核心框架
- **fastmcp v2.11+**: 使用最新版本的 fastmcp 框架
- **环境变量配置**: 通过 .env 文件管理所有配置
- **Tenacity**: 强大的重试机制，处理网络波动和 Token 刷新
- **Loguru**: 现代化的日志记录库，提供结构化和轮转日志
- **SSE (Server-Sent Events)**: 实现实时响应流

### 架构图

```
┌─────────────────────────────────────┐
│        IMA Copilot MCP 服务器        │
│                                     │
│  ┌─────────────────────────────┐    │
│  │      FastMCP 实例           │    │
│  │  - ask 工具                 │    │
│  │  - config 资源              │    │
│  │  - help 资源                │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │     配置管理 (环境变量)      │    │
│  │  - .env 文件读取            │    │
│  │  - 自动生成缺失参数         │    │
│  │  - 配置验证                 │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │      IMA API 客户端         │    │
│  │  - 认证管理 (自动刷新)       │    │
│  │  - 请求重试 (Tenacity)      │    │
│  │  - 响应流处理 (Loguru)      │    │
│  └─────────────────────────────┘    │
│                                     │
│  端口: 8081/mcp                      │
└─────────────────────────────────────┘
```

## 项目结构

```
tencent-ima-copilot-mcp/
├── .env.example                # 环境变量配置模板
├── src/                        # 核心源代码
│   ├── config.py               # 简化的配置管理（基于环境变量）
│   ├── ima_client.py           # IMA API 客户端 (含 Tenacity 重试)
│   └── models.py               # 数据模型
├── ima_server_simple.py        # MCP 服务器主程序
├── requirements.txt            # Python 依赖
├── pyproject.toml             # 项目配置
├── Dockerfile                 # Docker 构建文件
├── docker-compose.yml         # Docker Compose 配置
├── README.md                  # 项目说明
└── CLAUDE.md                  # AI 辅助开发指导
```

### 核心文件说明

- **ima_server_simple.py**: MCP 服务器入口，定义了 `ask` 工具和资源。使用 Loguru 进行日志记录。
- **src/config.py**: 使用 Pydantic Settings 加载和验证环境变量。
- **src/ima_client.py**: 核心业务逻辑。
    - 使用 `tenacity` 实现指数退避重试和 Token 过期自动刷新。
    - 使用 `loguru` 记录详细的请求和 SSE 流日志。
    - 解析 SSE 流并将其转换为结构化的 `TextContent` (回答 + 参考资料)。

## 核心功能模块

### 1. IMA API 客户端 (`src/ima_client.py`)
- **功能**: 封装与腾讯 IMA Copilot API 的交互
- **主要方法**:
  - `ask_question_complete`: 包含完整重试逻辑的问答接口
  - `refresh_token`: 自动刷新 Token
  - `_process_sse_stream`: 处理流式响应，支持 UTF-8 增量解码
- **特性**:
  - **自动重试**: 网络错误或超时会自动重试
  - **Token 刷新**: 遇到认证错误自动刷新 Token 并重试请求
  - **结构化输出**: 将引用资料与回答文本分离

### 2. MCP 服务器 (`ima_server_simple.py`)
- **功能**: 使用 FastMCP 提供 MCP 协议接口
- **工具**:
  - `ask`: 问答工具，返回 `list[TextContent]`，包含正文和参考资料
- **资源**:
  - `ima://config`: 查看当前配置
  - `ima://help`: 帮助信息

## 使用方式

### 启动服务

**方式一：Docker Compose (推荐)**
```bash
docker-compose up -d
```

**方式二：本地运行**
```bash
# 安装依赖
pip install -r requirements.txt

# 启动
fastmcp run ima_server_simple.py:mcp --transport http --host 127.0.0.1 --port 8081
```

### 连接 MCP Inspector
```bash
npx @modelcontextprotocol/inspector
# 输入地址: http://127.0.0.1:8081/mcp
```

## 开发指南

### 代码风格
- 使用 `uvx ruff check --fix` 保持代码整洁
- 遵循 PEP 8 规范
- 使用 Type Hints

### 调试
- 日志文件位于 `logs/debug/` 目录
- 原始 SSE 响应流在错误时会保存到 `logs/debug/raw/` 目录
- 可以通过 `IMA_MCP_LOG_LEVEL` 环境变量调整日志级别

## 关键配置 (环境变量)

- `IMA_X_IMA_COOKIE`: 必需，认证 Cookie
- `IMA_X_IMA_BKN`: 必需，CSRF Token
- `IMA_REQUEST_TIMEOUT`: 请求超时 (默认 30s)
- `IMA_RETRY_COUNT`: 重试次数 (默认 3)