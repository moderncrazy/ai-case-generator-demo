import orjson
from typing import List

from src.utils import utils
from src.graphs.schemas import StateApi
from src.repositories.api_repository import api_repository, ApiUpdate


class ApiService:
    """API 服务"""

    @staticmethod
    async def bulk_update_by_state_apis(project_id: str, apis: List[StateApi]):
        await api_repository.bulk_update(
            project_id,
            [
                ApiUpdate(
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

    @staticmethod
    async def list_by_project_to_state_api(project_id: str):
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


# 导出单例
api_service = ApiService()
