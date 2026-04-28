import orjson

from src import constant as const
from src.utils import utils as gutils
from src.graphs.common.schemas import StateApi
from src.repositories.api_repository import api_repository, ApiBulkUpdate
from src.repositories.project_file_repository import project_file_repository


async def bulk_update_by_state_apis(project_id: str, apis: list[StateApi]):
    """批量更新接口

    根据状态数据批量更新项目的接口信息。

    Args:
        project_id: 项目 ID
        apis: 状态中的 API 列表
    """
    await api_repository.bulk_update(
        project_id,
        [
            ApiBulkUpdate(
                id=item["id"],
                name=item["name"],
                method=item["method"],
                path=item["path"],
                module_id=item["module_id"],
                description=item.get("description"),
                request_headers=gutils.to_json(item.get("request_headers") or []),
                request_params=gutils.to_json(item.get("request_params") or []),
                request_body=gutils.to_json(item.get("request_body") or []),
                response_schema=item["response_schema"],
                test_script=item.get("test_script"),
            )
            for item in apis
        ]
    )


async def list_by_project_to_state_api(project_id: str) -> list[StateApi]:
    """查询项目接口转为状态对象

    从数据库查询项目接口并转换为状态格式。

    Args:
        project_id: 项目 ID

    Returns:
        状态 API 列表
    """
    results = await api_repository.list_by_project(project_id)
    return [
        StateApi(
            id=item.id,
            name=item.name,
            method=item.method,
            path=item.path,
            module_id=item.module_id,
            description=item.description,
            request_headers=orjson.loads(item.request_headers),
            request_params=orjson.loads(item.request_params),
            request_body=orjson.loads(item.request_body),
            response_schema=item.response_schema,
            test_script=item.test_script,
        )
        for item in results
    ]


async def format_project_files_summary_to_str(project_id: str) -> str:
    """提取项目文件摘要转为字符串

    将项目中所有文件的摘要信息整合为一个字符串，
    用于提供给 AI 作为上下文信息。

    Args:
        project_id: 项目 ID

    Returns:
        包含所有文件摘要的字符串
    """
    content = ""
    project_files = await project_file_repository.list_by_project(project_id)
    for item in project_files:
        content += f"文件Id：{item.id}\n文件名：{item.name}\n上传时间：{item.created_at}\n文件摘要：\n{item.summary}\n\n----------{item.name} end----------\n\n"
    return content if content else const.EMPTY_ZH
