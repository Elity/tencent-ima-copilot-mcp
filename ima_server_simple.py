#!/usr/bin/env python3
"""
IMA Copilot MCP 服务器 - 基于环境变量的简化版本
专注于 MCP 协议实现，配置通过环境变量管理
"""

import sys
from pathlib import Path
from datetime import datetime

from fastmcp import FastMCP
from mcp.types import TextContent
from loguru import logger

# 导入我们的模块
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config_manager, get_config, get_app_config
from ima_client import IMAAPIClient

# 配置详细的调试日志
app_config = get_app_config()

# 创建日志目录
log_dir = Path("logs/debug")
log_dir.mkdir(parents=True, exist_ok=True)

# 使用固定日志文件名（避免每次启动创建新文件导致累积）
log_file = log_dir / "ima_server.log"

# 配置 loguru
logger.remove()  # 移除默认的 sink
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> | <magenta>{extra}</magenta>"
)
logger.add(
    log_file,
    level="DEBUG",
    rotation="10 MB",
    retention="1 week",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message} | {extra}"
)

logger.info(f"调试日志已启用，日志文件: {log_file}")

# 创建 FastMCP 实例
mcp = FastMCP("IMA Copilot")

# 全局变量
ima_client: IMAAPIClient = None
_token_refreshed: bool = False  # 标记 token 是否已刷新


async def cleanup_client():
    """清理客户端资源"""
    global ima_client
    if ima_client:
        try:
            logger.info("👋 正在关闭 IMA 客户端会话...")
            await ima_client.close()
            logger.info("✅ 客户端会话已关闭")
        except Exception as e:
            logger.error(f"关闭客户端会话时发生错误: {e}")
        finally:
            ima_client = None


# 使用 atexit 注册同步清理（作为备用）
import atexit
def _sync_cleanup():
    """同步清理（atexit 回调）"""
    global ima_client
    if ima_client and ima_client.session and not ima_client.session.closed:
        logger.warning("⚠️ 通过 atexit 强制关闭未清理的会话")
        # 注意：atexit 中无法运行 async 代码，只能标记
        ima_client = None

atexit.register(_sync_cleanup)


async def ensure_client_ready():
    """确保客户端已初始化并且 token 有效"""
    global ima_client, _token_refreshed
    
    if not ima_client:
        logger.info("🚀 首次请求，初始化 IMA 客户端...")
        
        config = get_config()
        if not config:
            logger.error("❌ 配置未加载")
            return False
        
        try:
            # 启用原始SSE日志
            config.enable_raw_logging = True
            config.raw_log_dir = "logs/debug/raw"
            config.raw_log_on_success = False
            
            ima_client = IMAAPIClient(config)
            logger.debug("✅ IMA 客户端初始化成功")
        except Exception as e:
            logger.exception("❌ IMA 客户端初始化失败")
            return False
    
    # 如果还没刷新过 token，提前刷新一次（添加超时保护）
    if not _token_refreshed:
        logger.info("🔄 验证 token...")
        try:
            import asyncio
            # 为token刷新也添加超时保护（15秒）
            token_valid = await asyncio.wait_for(
                ima_client.ensure_valid_token(),
                timeout=15.0
            )
            
            if token_valid:
                _token_refreshed = True
                logger.info("✅ Token 验证成功")
                return True
            else:
                logger.warning("⚠️ Token 验证失败，尝试继续...")
                # 即使刷新失败也标记为 True，让后续请求在 ask_question 内部触发自动重试逻辑
                _token_refreshed = True 
                return True
        except asyncio.TimeoutError:
            logger.error("❌ Token 验证超时")
            return False
        except Exception as e:
            logger.exception("❌ Token 验证异常")
            return False
    
    return True


@mcp.tool()
async def ask(question: str) -> list[TextContent]:
    """向腾讯 IMA 知识库询问任何问题

    Args:
        question: 要询问的问题

    Returns:
        IMA 知识库的回答
    """
    global ima_client
    
    # 生成请求ID用于日志追踪
    import uuid
    request_id = str(uuid.uuid4())[:8]
    
    # 绑定上下文
    with logger.contextualize(request_id=request_id):
        # 确保客户端已初始化并且 token 有效
        if not await ensure_client_ready():
            return [TextContent(type="text", text="[ERROR] IMA 客户端初始化或 token 刷新失败，请检查配置")]

        logger.debug("🔍 ask 工具调用", question_preview=question[:50])

        if not question or not question.strip():
            return [TextContent(type="text", text="[ERROR] 问题不能为空")]

        try:
            logger.debug("发送问题", length=len(question))

            # MCP 客户端（如 Claude Desktop）通常有 60 秒的请求超时限制
            # 设置一个略短的超时以确保在 MCP 超时前返回结果
            # 如果 IMA 响应时间过长，将返回部分结果
            mcp_safe_timeout = 50  # 50秒，留出 10 秒缓冲
            
            logger.info(f"⏱️ 开始处理问题（超时限制: {mcp_safe_timeout}秒）")
            logger.info(f"📝 问题内容: {question[:100]}{'...' if len(question) > 100 else ''}")
            
            # 将超时控制传递给 ask_question_complete，以便在超时时返回部分结果
            import asyncio
            try:
                messages = await asyncio.wait_for(
                    ima_client.ask_question_complete(question, timeout=mcp_safe_timeout),
                    timeout=mcp_safe_timeout + 5  # 外层超时稍长一点
                )
            except asyncio.TimeoutError:
                logger.error(f"❌ MCP 服务器层面超时（{mcp_safe_timeout + 5}秒）")
                return [TextContent(
                    type="text", 
                    text=f"[ERROR] 请求超时（超过 {mcp_safe_timeout}秒）。IMA 响应时间过长，请尝试简化问题或稍后重试。"
                )]
            
            # 即使没有消息，也会返回包含错误信息的消息列表
            if not messages:
                logger.warning("⚠️ 未收到响应")
                return [TextContent(type="text", text="[ERROR] 没有收到任何响应，或者请求超时未产生任何输出")]

            # 打印完整的qa结果
            logger.info("-" * 80)
            logger.info("完整 QA 结果 (原始消息列表):")
            for i, msg in enumerate(messages):
                logger.info(f"  消息 {i + 1} (类型: {msg.type.value}): {msg.content[:200]}...")
            logger.info("-" * 80)

            response = ima_client._extract_text_content(messages)
            
            # 如果没有提取到文本内容，检查是否有系统错误消息
            if not response:
                error_msgs = [msg.content for msg in messages if msg.type == 'system']
                if error_msgs:
                    response = f"[ERROR] {'; '.join(error_msgs)}"
                    logger.warning("⚠️ 未提取到文本，返回系统错误", error=response)
                else:
                    response = "没有收到有效回复"
                    
            logger.debug("✅ 获取响应", length=len(response))
            
            content_list = [TextContent(type="text", text=response)]

            # 提取并添加参考资料信息
            try:
                knowledge_info = ima_client._extract_knowledge_info(messages)
                if knowledge_info:
                    ref_text = "### 📚 参考资料\n\n"
                    for i, item in enumerate(knowledge_info, 1):
                        title = item.get('title', '未知标题')
                        intro = item.get('introduction', '')
                        # 截断过长的简介
                        if intro and len(intro) > 150:
                            intro = intro[:150] + "..."
                        
                        ref_text += f"{i}. **{title}**\n"
                        if intro:
                            ref_text += f"   > {intro}\n"
                        ref_text += "\n"
                    
                    content_list.append(TextContent(type="text", text=ref_text))
                    logger.debug("✅ 添加参考资料", count=len(knowledge_info))
            except Exception as e:
                logger.warning(f"提取参考资料失败: {e}")

            # 打印返回 ask 的内容
            logger.info("-" * 80)
            logger.info(f"ask 工具返回内容 (Block 数量: {len(content_list)}):")
            for i, block in enumerate(content_list):
                 logger.info(f"Block {i+1} ({len(block.text)} chars):\n{block.text[:200]}...")
            logger.info("-" * 80)
            
            return content_list
                
        except Exception as e:
            logger.exception("询问 IMA 时发生错误")
            
            # 返回更友好的错误信息
            error_str = str(e).lower()
            if "超时" in str(e) or "timeout" in error_str:
                return [TextContent(type="text", text="[ERROR] 请求超时，请稍后重试")]
            elif "认证" in str(e) or "auth" in error_str:
                return [TextContent(type="text", text="[ERROR] 认证失败，请检查 IMA 配置信息")]
            elif "网络" in str(e) or "network" in error_str or "connection" in error_str:
                return [TextContent(type="text", text="[ERROR] 网络连接失败，请检查网络设置")]
            else:
                return [TextContent(type="text", text=f"[ERROR] 询问失败: {str(e)}")]


@mcp.resource("ima://config")
def get_config_resource() -> str:
    """获取当前配置信息（不包含敏感数据）"""
    try:
        config = get_config()
        if not config:
            return "配置未加载"

        # 返回非敏感的配置信息
        config_info = "IMA 配置信息:\n"
        config_info += f"客户端ID: {config.client_id}\n"
        config_info += f"请求超时: {config.timeout}秒\n"
        config_info += f"重试次数: {config.retry_count}\n"
        config_info += f"代理设置: {config.proxy or '未设置'}\n"
        config_info += f"创建时间: {config.created_at}\n"
        if config.updated_at:
            config_info += f"更新时间: {config.updated_at}\n"

        return config_info

    except Exception as e:
        logger.error(f"获取配置资源时发生错误: {e}")
        return f"[ERROR] 获取配置失败: {str(e)}"


@mcp.resource("ima://help")
def get_help_resource() -> str:
    """获取使用帮助信息"""
    help_text = """
# IMA Copilot MCP 服务器帮助

## 概述
这是基于环境变量配置的 IMA Copilot MCP 服务器，提供腾讯 IMA 知识库的 MCP 协议接口。

## 配置方式
通过环境变量或 .env 文件配置 IMA 认证信息：

1. 复制 .env.example 为 .env
2. 填入从浏览器获取的认证信息：
   - IMA_COOKIES: 完整的 cookies 字符串
   - IMA_X_IMA_COOKIE: X-Ima-Cookie 请求头
   - IMA_X_IMA_BKN: X-Ima-Bkn 请求头

## 工具
- `ask`: 向 IMA 知识库询问问题

## 资源
- `ima://config`: 查看配置信息
- `ima://help`: 查看帮助信息

## 启动方式
```bash
# 使用 fastmcp 命令启动
fastmcp run ima_server_simple.py:mcp --transport http --host 127.0.0.1 --port 8081

# 或使用 Python 直接运行
python ima_server_simple.py
```

## 连接方式
使用 MCP Inspector 连接到: http://127.0.0.1:8081/mcp
"""
    return help_text


def main():
    """主函数 - 直接启动服务器时使用"""
    app_config = get_app_config()

    print("IMA Copilot MCP 服务器")
    print("=" * 50)
    print("版本: 简化版 (基于环境变量)")
    print(f"服务地址: http://{app_config.host}:{app_config.port}")
    print(f"MCP 端点: http://{app_config.host}:{app_config.port}/mcp")
    print(f"日志级别: {app_config.log_level}")
    print("=" * 50)

    # 验证配置
    config = get_config()
    if config and config.x_ima_cookie and config.x_ima_bkn:
        print("[OK] 配置加载成功，必需认证信息已设置")
    else:
        print("[ERROR] 配置加载失败或必需认证信息缺失，请检查环境变量")
        sys.exit(1) # Added exit if config is bad

    print("=" * 50)
    print("启动命令:")
    print(f"fastmcp run ima_server_simple.py:mcp --transport http --host {app_config.host} --port {app_config.port}")
    print("=" * 50)


if __name__ == "__main__":
    main()


__all__ = ["mcp"]