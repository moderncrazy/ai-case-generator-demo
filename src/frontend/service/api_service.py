import uuid
import traceback

import streamlit as st

from src.frontend.utils import utils
from src.frontend import constant as const
from src.frontend.schemas.response import ListResponse
from src.frontend.schemas.api import ApiResponse, ApiTreeNode, ApiTreeDocumentResponse

SERVER_HOST = st.secrets["server"]["host"]

logger = utils.get_logger()


class ApiService:

    @staticmethod
    def list_apis(
            project_id: str,
            page: int = 1,
            page_size: int = 20,
            module_id: str = None,
    ) -> ListResponse[ApiResponse] | None:
        """查询接口列表"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/apis",
                headers={const.TRANSACTION_ID: trans_id},
                params={"page": page, "page_size": page_size, "module_id": module_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return ListResponse[ApiResponse].model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 页码:{page} 每页:{page_size} 模块Id:{module_id} 查询接口列表失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_apis_tree(project_id: str) -> list[ApiTreeNode] | None:
        """获取接口树形结构"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/apis/tree",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return [ApiTreeNode.model_validate(item) for item in resp.get("data", [])]
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取接口树形结构失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_apis_compare(project_id: str) -> ApiTreeDocumentResponse | None:
        """获取 API 对比文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/apis/compare",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return ApiTreeDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取 API 对比文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_markdown_by_apis_tree(api_tree_nodes: list[ApiTreeNode], level: int = 1) -> str:
        """将 API 树转换为 Markdown 格式文档"""
        content = ""
        if api_tree_nodes:
            for node in api_tree_nodes:
                # 模块标题
                content += f"{'#' * level} {node.module_name}\n\n"
                for api in node.apis:
                    # 接口名称
                    content += f"- {api.name}\n\n"
                    # 方法和路径（代码块）
                    content += f"```\n[{api.method.value}] {api.path}\n```\n\n"
                    # 接口描述
                    if api.description:
                        content += f"{api.description}\n\n"
                    # 请求头参数
                    if api.request_headers:
                        content += "**请求头参数**\n\n"
                        content += "| 字段名 | 类型 | 是否必填 | 描述 |\n"
                        content += "| ------ | ---- | -------- | ---- |\n"
                        for param in api.request_headers:
                            content += f"| {param.name} | {param.type} | {'是' if param.required else '否'} | {param.description} |\n"
                        content += "\n"
                    # 查询参数
                    if api.request_params:
                        content += "**查询参数**\n\n"
                        content += "| 字段名 | 类型 | 是否必填 | 描述 |\n"
                        content += "| ------ | ---- | -------- | ---- |\n"
                        for param in api.request_params:
                            content += f"| {param.name} | {param.type} | {'是' if param.required else '否'} | {param.description} |\n"
                        content += "\n"
                    # 请求体参数
                    if api.request_body:
                        content += "**请求体参数**\n\n"
                        content += "| 字段名 | 类型 | 是否必填 | 描述 |\n"
                        content += "| ------ | ---- | -------- | ---- |\n"
                        for param in api.request_body:
                            content += f"| {param.name} | {param.type} | {'是' if param.required else '否'} | {param.description} |\n"
                        content += "\n"
                    # 响应示例
                    if api.response_schema:
                        content += "### 响应示例\n\n"
                        content += "```json\n"
                        content += f"{api.response_schema}\n"
                        content += "```\n\n"
                # 递归处理子模块
                if node.children:
                    content += ApiService.get_markdown_by_apis_tree(node.children, level + 1)
        return content


# 导出单例
api_service = ApiService()
