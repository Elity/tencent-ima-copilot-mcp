# IMA Copilot MCP 服务器

基于 FastMCP v2 框架的腾讯 IMA Copilot MCP (Model Context Protocol) 服务器，**使用环境变量配置**，简化项目结构，专注于 MCP 协议实现。

## ✨ 主要特性

- 🚀 **极简配置**: 仅需两个必需参数即可启动，开箱即用
- 🤖 **MCP 协议支持**: 完整实现 Model Context Protocol 规范
- 🔧 **环境变量配置**: 通过 `.env` 文件管理所有配置
- 📡 **HTTP 传输**: 支持 HTTP 传输协议，便于 MCP Inspector 连接
- 🛠️ **增强型 MCP 工具**: 提供腾讯 IMA 知识库问答功能，返回结果包含回答文本和结构化参考资料
- 🔄 **Token 自动刷新**: 智能管理认证 token，自动刷新保持会话有效
- 💪 **Tenacity-powered Retries**: 集成 tenacity 库，优化重试机制，支持指数退避和针对性错误重试
- 📝 **Loguru-enhanced Logging**: 采用 Loguru 提升日志体验，提供更清晰、结构化的日志输出
- ⏱️ **超时保护**: 内置请求超时机制，防止长时间阻塞 (已提升至 300 秒)
- 🎯 **一键启动**: 简化的启动流程，自动环境检查和配置验证
- 🐳 **Docker 支持**: 提供官方 Docker 镜像，开箱即用

## 快速开始

### 方式一：使用 Docker（推荐）

#### 1. 使用 Docker Run

```bash
# 拉取镜像
docker pull highkay/tencent-ima-copilot-mcp:latest

# 运行容器（需要替换以下两个必需的环境变量）
docker run -d \
  --name ima-copilot-mcp \
  -p 8081:8081 \
  -e IMA_X_IMA_COOKIE="your_x_ima_cookie_here" \
  -e IMA_X_IMA_BKN="your_x_ima_bkn_here" \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  highkay/tencent-ima-copilot-mcp:latest

# 查看日志
docker logs -f ima-copilot-mcp
```

#### 2. 使用 Docker Compose（更便捷）

创建 `.env` 文件（或直接在 shell 中设置环境变量）：

```bash
# .env 文件
IMA_X_IMA_COOKIE="your_x_ima_cookie_here"
IMA_X_IMA_BKN="your_x_ima_bkn_here"
```

启动服务：

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 方式二：本地安装

#### 1. 安装依赖

```bash
# 安装 FastMCP、tenacity、Loguru 和所有依赖
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
# 复制配置文件模板
cp .env.example .env

# 编辑 .env 文件，填入从浏览器获取的 IMA 认证信息
nano .env  # 或使用其他编辑器
```

#### 必需配置项

以下环境变量必须正确配置才能使用服务：

- **`IMA_X_IMA_COOKIE`**: X-Ima-Cookie 请求头值（包含平台信息、token 等）
- **`IMA_X_IMA_BKN`**: X-Ima-Bkn 请求头值（业务密钥）

#### 3. 获取 IMA 认证信息

#### 步骤 1: 访问 IMA Copilot

1. 访问 [https://ima.qq.com](https://ima.qq.com) 并登录
2. 按 F12 打开开发者工具
3. 切换到 **Network** (网络) 标签页

#### 步骤 2: 获取认证头信息

1. 在 IMA 中发送一条消息
2. 找到向 `/cgi-bin/assistant/qa` 的 POST 请求
3. 查看 **Request Headers**，复制以下字段：
   - `x-ima-cookie` → `IMA_X_IMA_COOKIE`
   - `x-ima-bkn` → `IMA_X_IMA_BKN`

#### 4. 启动服务器

##### 方式一：使用启动脚本（推荐）

```bash
# Windows
start.bat

# 或使用 Python 脚本（跨平台）
python run.py
```

##### 方式二：使用 fastmcp 命令

```bash
fastmcp run ima_server_simple.py:mcp --transport http --host 127.0.0.1 --port 8081
```

#### 5. 使用 MCP Inspector

```bash
# 安装 MCP Inspector
npx @modelcontextprotocol/inspector

# 连接到服务器
# 在 Inspector 中输入: http://127.0.0.1:8081/mcp
```

### 服务端点

- **MCP 协议端点**: `http://127.0.0.1:8081/mcp`（用于 MCP Inspector 或其他 MCP 客户端）
- **日志文件**: `logs/debug/ima_server_YYYYMMDD_HHMMSS.log`（Loguru 自动生成和管理）
- **原始 SSE 日志**: `logs/debug/raw/sse_*.log`（发生错误时自动保存）

## 可用的 MCP 工具

### 1. `ask`

向腾讯 IMA 知识库询问任何问题

**参数:**
- `question` (必需): 要询问的问题

**示例:**
```
问题: "什么是机器学习？"
问题: "如何制作番茄炒蛋？"
```

**特性:**
- 自动管理会话，无需手动创建
- 智能 token 刷新，确保认证有效
- **300 秒超时保护**，防止长时间等待
- 返回内容为 **`TextContent` 列表**，包含**回答文本**和格式化后的**参考资料**

## 可用的 MCP 资源

### 1. `ima://config`

获取当前配置信息（不包含敏感数据）

### 2. `ima://help`

获取帮助信息

## 配置选项

### 必需的环境变量

| 变量名 | 说明 | 获取方式 |
|--------|------|---------|
| `IMA_X_IMA_COOKIE` | X-Ima-Cookie 请求头 | 从浏览器开发者工具 Network 标签中复制 |
| `IMA_X_IMA_BKN` | X-Ima-Bkn 请求头 | 从浏览器开发者工具 Network 标签中复制 |

### 可选的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `IMA_KNOWLEDGE_BASE_ID` | 知识库 ID | `7305806844290061` |
| `IMA_MCP_HOST` | MCP 服务器地址 | `127.0.0.1` |
| `IMA_MCP_PORT` | MCP 服务器端口 | `8081` |
| `IMA_MCP_LOG_LEVEL` | 日志级别 (支持 `DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `IMA_REQUEST_TIMEOUT` | IMA API 请求超时时间（秒） | `30` |
| `IMA_ROBOT_TYPE` | 机器人类型 | `5` |
| `IMA_SCENE_TYPE` | 场景类型 | `1` |
| `IMA_MODEL_TYPE` | 模型类型 | `4` |

## 故障排除

### 常见问题

**Q: 认证失败（Token 验证失败）怎么办？**

A:
1. 检查 `.env` 文件中的 `IMA_X_IMA_COOKIE` 和 `IMA_X_IMA_BKN` 是否正确
2. 确认 `IMA_X_IMA_COOKIE` 中包含 `IMA-REFRESH-TOKEN` 字段
3. 重新从浏览器获取最新的认证信息

**Q: 如何连接特定的知识库？**

A:
在 `.env` 文件中设置 `IMA_KNOWLEDGE_BASE_ID` 即可。获取方法：
1. 在 IMA 网页选择知识库
2. 找到 `init_session` 请求
3. 查看 Payload 中的 `knowledge_base_id`

## 许可证

MIT License