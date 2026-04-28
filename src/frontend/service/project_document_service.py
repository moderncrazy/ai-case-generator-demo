import uuid
import traceback

import streamlit as st

from src.frontend.utils import utils
from src.frontend import constant as const
from src.frontend.schemas.project_document import (
    ContextIssue,
    IssuesResponse,
    TextDocumentResponse,
    CompareTextDocumentResponse,
    RequirementModulesResponse,
)

SERVER_HOST = st.secrets["server"]["host"]

logger = utils.get_logger()


class ProjectDocumentService:

    @staticmethod
    def get_requirement_outline(project_id: str) -> TextDocumentResponse | None:
        """获取需求大纲"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/requirement-outline",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return TextDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取需求大纲失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_requirement_modules(project_id: str) -> RequirementModulesResponse | None:
        """获取需求模块"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/requirement-modules",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return RequirementModulesResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取需求模块失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_requirement_overall(project_id: str) -> TextDocumentResponse | None:
        """获取需求整体文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/requirement-overall",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return TextDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取需求整体文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_requirement_overall_compare(project_id: str) -> CompareTextDocumentResponse | None:
        """对比需求整体文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/requirement-overall/compare",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return CompareTextDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 对比需求整体文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_architecture(project_id: str) -> TextDocumentResponse | None:
        """获取架构设计文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/architecture",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return TextDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取架构设计文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_architecture_compare(project_id: str) -> CompareTextDocumentResponse | None:
        """对比架构设计文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/architecture/compare",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return CompareTextDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 对比架构设计文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_database(project_id: str) -> TextDocumentResponse | None:
        """获取数据库设计文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/database",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return TextDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取数据库设计文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_database_compare(project_id: str) -> CompareTextDocumentResponse | None:
        """对比数据库设计文档"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/database/compare",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return CompareTextDocumentResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 对比数据库设计文档失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_issues(project_id: str) -> IssuesResponse | None:
        """获取风险点和疑问"""
        trans_id = str(uuid.uuid4())
        try:
            client = utils.get_http_client()
            response = client.get(
                f"{SERVER_HOST}/api/v1/project/{project_id}/issues",
                headers={const.TRANSACTION_ID: trans_id}
            )
            resp = response.json()
            if resp.get("code") == 200:
                return IssuesResponse.model_validate(resp["data"])
            else:
                st.toast(resp.get("message", const.SYSTEM_ERROR_MESSAGE), icon="⚠️", duration="long")
                return None
        except Exception as e:
            logger.error(
                f"trans_id:{trans_id} 项目Id:{project_id} 获取风险点和疑问失败:{str(e)} 异常栈:\n{traceback.format_exc()}")
            return None

    @staticmethod
    def get_markdown_by_issues(issues: list[ContextIssue]) -> str:
        """将issues转换为 Markdown 格式文档"""
        content = ""
        if issues:
            for issue in issues:
                # 模块标题
                content += f"**问题：** {issue.content}\n\n"
                content += f"> **建议：** {issue.propose}\n\n"
        return content


# 导出单例
project_document_service = ProjectDocumentService()
