import orjson
from typing import List, Tuple
from collections import defaultdict

from src.utils import utils
from src.graphs.schemas import StateApi
from src.repositories.module_repository import module_repository
from src.repositories.api_repository import api_repository, ApiBulkUpdate
from src.schemas.api import ApiResponse, ApiTreeNode, ApiRequestParam


class ApiService:
    """API 服务
    
    提供 API 接口相关的业务逻辑处理，
    包括批量更新接口、查询接口列表、获取接口树形结构等功能。
    """

    @staticmethod
    async def bulk_update_by_state_apis(project_id: str, apis: List[StateApi]):
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
    async def list_by_project_to_state_api(project_id: str) -> List[StateApi]:
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

    @staticmethod
    def _parse_request_params(json_str: str) -> List[ApiRequestParam]:
        """解析请求参数字符串
        
        将 JSON 格式的参数字符串解析为 ApiRequestParam 列表。
        
        Args:
            json_str: JSON 格式参数字符串
            
        Returns:
            解析后的参數列表，解析失败返回空列表
        """
        if not json_str:
            return []
        try:
            items = orjson.loads(json_str)
            return [ApiRequestParam(**item) for item in items]
        except Exception:
            return []

    @staticmethod
    async def list_apis(
            project_id: str,
            page: int = 1,
            page_size: int = 20,
            module_id: str = None,
    ) -> Tuple[List[ApiResponse], int]:
        """查询接口列表
        
        分页查询项目的接口列表。
        
        Args:
            project_id: 项目 ID
            page: 页码（从 1 开始）
            page_size: 每页数量
            module_id: 按模块筛选（可选）
            
        Returns:
            (接口响应列表, 总数) 元组
        """
        apis, total = await api_repository.paginate(
            project_id=project_id,
            page=page,
            page_size=page_size,
            module_id=module_id,
        )
        result = []
        for api in apis:
            result.append(ApiResponse(
                id=api.id,
                project_id=api.project_id,
                module_id=api.module_id,
                name=api.name,
                method=api.method,
                path=api.path,
                description=api.description,
                request_headers=ApiService._parse_request_params(api.request_headers),
                request_params=ApiService._parse_request_params(api.request_params),
                request_body=ApiService._parse_request_params(api.request_body),
                response_schema=api.response_schema,
                test_script=api.test_script,
                created_at=api.created_at,
            ))
        return result, total

    @staticmethod
    async def get_apis_tree(project_id: str) -> List[ApiTreeNode]:
        """获取接口树形结构
        
        按模块父子级组织项目的接口列表。
        
        Args:
            project_id: 项目 ID
            
        Returns:
            接口树形结构列表
        """
        # 获取项目下所有模块
        all_modules = await module_repository.list_by_project(project_id)
        module_dict = {m.id: m for m in all_modules}

        # 获取项目下所有接口
        all_apis = await api_repository.list_by_project(project_id)

        # 按 module_id 分组接口
        apis_by_module = defaultdict(list)
        for api in all_apis:
            apis_by_module[api.module_id].append(
                ApiResponse(
                    id=api.id,
                    project_id=api.project_id,
                    module_id=api.module_id,
                    name=api.name,
                    method=api.method,
                    path=api.path,
                    description=api.description,
                    request_headers=ApiService._parse_request_params(api.request_headers),
                    request_params=ApiService._parse_request_params(api.request_params),
                    request_body=ApiService._parse_request_params(api.request_body),
                    response_schema=api.response_schema,
                    test_script=api.test_script,
                    created_at=api.created_at,
                )
            )

        # 构建树形结构
        def build_tree(parent_id: str = None) -> List[ApiTreeNode]:
            children = []
            for module in all_modules:
                if module.parent_id == parent_id:
                    node = ApiTreeNode(
                        module_id=module.id,
                        module_name=module.name,
                        apis=apis_by_module.get(module.id, []),
                        children=build_tree(module.id)
                    )
                    children.append(node)
            return children

        return build_tree()


# 导出单例
api_service = ApiService()
