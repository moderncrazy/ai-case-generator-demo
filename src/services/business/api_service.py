import orjson

from src.utils import utils
from src.graphs.common.schemas import StateApi
from src.services.business.redis_service import redis_service
from src.repositories.api_repository import api_repository, ApiBulkUpdate


class ApiService:
    """系统Api服务"""

    def __init__(self):
        self.repository = api_repository

    async def bulk_update_by_state_apis(self, project_id: str, apis: list[StateApi]):
        """批量更新接口

        根据状态数据批量更新项目的接口信息。

        Args:
            project_id: 项目 ID
            apis: 状态中的 API 列表
        """
        await self.repository.bulk_update(
            project_id,
            [
                ApiBulkUpdate(
                    id=item["id"],
                    name=item["name"],
                    method=item["method"],
                    path=item["path"],
                    module_id=item["module_id"],
                    description=item.get("description"),
                    request_headers=utils.to_json(item.get("request_headers") or []),
                    request_params=utils.to_json(item.get("request_params") or []),
                    request_body=utils.to_json(item.get("request_body") or []),
                    response_schema=item["response_schema"],
                    test_script=item.get("test_script"),
                )
                for item in apis
            ]
        )
        await redis_service.delete_project_basic_info_cache(project_id)

    async def list_by_project_to_state_api(self, project_id: str) -> list[StateApi]:
        """查询项目接口转为状态对象

        从数据库查询项目接口并转换为状态格式。

        Args:
            project_id: 项目 ID

        Returns:
            状态 API 列表
        """
        results = await self.repository.list_by_project(project_id)
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


api_service = ApiService()
