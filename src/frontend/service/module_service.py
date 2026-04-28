import uuid
import traceback

import streamlit as st

from src.frontend.utils import utils
from src.frontend import constant as const
from src.frontend.schemas.response import ListResponse
from src.frontend.schemas.module import ModuleResponse, ModuleTreeNode, ModuleTreeDocumentResponse

SERVER_HOST = st.secrets["server"]["host"]

logger = utils.get_logger()


class ModuleService:

    @staticmethod
    def list_modules(
            project_id: str,
            page: int = 1,
            page_size: int = 20,
            parent_id: str = None,
    ) -> ListResponse[ModuleResponse] | None:
        """查询模块列表"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/modules",
                headers={const.TRANSACTION_ID: trans_id},
                params={"page": page, "page_size": page_size, "parent_id": parent_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return ListResponse[ModuleResponse].model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 页码:{page} 每页:{page_size} 父模块Id:{parent_id} 查询模块列表失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_modules_tree(project_id: str) -> list[ModuleTreeNode] | None:
        """获取模块树形结构"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/modules/tree",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return [ModuleTreeNode.model_validate(item) for item in resp.get("data", [])]
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取模块树形结构失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_modules_compare(project_id: str) -> ModuleTreeDocumentResponse | None:
        """获取模块对比文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/modules/compare",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return ModuleTreeDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取模块对比文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_markdown_by_modules_tree(modules: list[ModuleTreeNode], index=1) -> str:
        """将 module 树转换为 Markdown 格式文档"""
        content = ""
        if modules:
            for module in modules:
                content += f"{"#" * index} {module.name}\n\n{module.description}\n\n"
                if module.children:
                    content += ModuleService.get_markdown_by_modules_tree(module.children, index + 1)
        return content


# 导出单例
module_service = ModuleService()
