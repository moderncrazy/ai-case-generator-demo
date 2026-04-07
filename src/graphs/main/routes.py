from typing import Literal

from src.graphs.main.state import State


def load_project_router(state: State) -> Literal["understand_image_node", "load_project_node"]:
    """决定是否走load_project_node节点"""
    if state.get("project_name"):
        return "understand_image_node"
    return "load_project_node"


def understand_image_router(state: State) -> Literal["understand_image_node", "product_manager_node"]:
    """决定是否走understand_image_node节点"""
    if state.get("new_file_list"):
        return "understand_image_node"
    return "product_manager_node"
