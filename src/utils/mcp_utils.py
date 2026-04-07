from async_lru import alru_cache
from langchain.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config import settings


@alru_cache(maxsize=1)
async def get_minimax_mcp_tools_by_name() -> dict[str, BaseTool]:
    """获取 MiniMax MCP 工具（带缓存）
    
    连接 MiniMax MCP 服务器，获取可用工具列表并转为 {name: tool} 字典。
    使用 @alru_cache 缓存，同一进程内只初始化一次 MCP 连接。
    
    Returns:
        工具字典，key 为工具名，如 "understand_image", "web_search" 等
    """
    mcp_client = MultiServerMCPClient({
        "MiniMax": {
            "transport": "stdio",
            "command": "uvx",
            "args": ["minimax-coding-plan-mcp", "-y"],
            "env": {
                "MINIMAX_API_KEY": settings.minimax_api_key,
                "MINIMAX_API_HOST": settings.minimax_mcp_host
            }
        }
    })
    tools = await mcp_client.get_tools()
    return {tool.name: tool for tool in tools}
