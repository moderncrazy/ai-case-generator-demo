from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from src.graphs import graph
from src.graphs.state import State
from src.graphs.common.schemas import StateNewProjectFile

from src.repositories.writes_repository import writes_repository
from src.repositories.checkpoints_repository import checkpoints_repository


class MainAgent:
    """主代理类
    
    负责管理 LangGraph 主工作流的执行，协调项目加载、文件理解和产品经理对话等流程。
    """

    def __init__(self):
        """初始化主代理，agent 实例初始为 None（懒加载）"""
        self._agent: CompiledStateGraph | None = None

    async def get_agent(self) -> CompiledStateGraph:
        """获取或创建编译后的 LangGraph agent
        
        Returns:
            CompiledStateGraph: 编译后的 LangGraph 状态图实例
        """
        if self._agent is None:
            self._agent = await graph.create_agent()
        return self._agent

    async def get_state(self, project_id: str) -> State | None:
        """获取项目当前的图状态
        
        Args:
            project_id: 项目ID，用于获取对应的 checkpoint 状态
            
        Returns:
            图状态字典，如果不存在则返回 None
        """
        agent = await self.get_agent()
        config = {"configurable": {"thread_id": project_id}}
        state_snapshot = await agent.aget_state(config=config)
        return state_snapshot.values if state_snapshot else None

    async def astream(self, project_id: str, message: str, new_file_list: list[StateNewProjectFile] = None):
        """异步流式执行主代理工作流
        
        处理用户消息和新上传文件，通过 LangGraph 工作流进行需求分析、任务分发等操作。
        
        Args:
            project_id: 项目Id，用于线程隔离和状态追踪
            message: 用户输入的消息内容
            new_file_list: 用户新上传的文件列表（可选），包含文件路径、类型等信息
        
        Returns:
            异步生成器，产生流式输出结果
        """
        self._agent = await self.get_agent()
        if new_file_list:
            state = {
                "messages": HumanMessage(content=message),
                "project_id": project_id,
                "new_file_list": new_file_list
            }
        else:
            state = {"messages": HumanMessage(content=message), "project_id": project_id}

        return self._agent.astream(
            state,
            config={"configurable": {"thread_id": project_id}},
            stream_mode=["values", "custom", "messages"],
            subgraphs=True,
            version="v2"
        )


main_agent = MainAgent()
