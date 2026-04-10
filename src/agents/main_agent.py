from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from src.graphs import graph
from src.graphs.schemas import StateNewProjectFile


class MainAgent:
    def __init__(self):
        self._agent: CompiledStateGraph | None = None

    async def _get_agent(self) -> CompiledStateGraph:
        if self._agent is None:
            self._agent = await graph.create_agent()
        return self._agent

    async def astream(self, project_id: str, message: str, new_file_list: list[StateNewProjectFile] = None):
        self._agent = await self._get_agent()
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
            stream_mode=["updates", "custom"],
            subgraphs=True,
            version="v2"
        )


main_agent = MainAgent()
