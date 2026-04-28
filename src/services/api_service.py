import orjson
from typing import List, Tuple

from src.agents.main_agent import main_agent
from src.services.module_service import module_service
from src.repositories.module_repository import module_repository
from src.repositories.api_repository import api_repository
from src.schemas.api import ApiResponse, ApiTreeNode, ApiRequestParam, ApiTreeDocumentResponse


class ApiService:
    """API 服务
    
    提供 API 接口相关的业务逻辑处理，
    包括批量更新接口、查询接口列表、获取接口树形结构等功能。
    """

    @staticmethod
    def _parse_request_params(data: str | list) -> List[ApiRequestParam]:
        """解析请求参数字符串或列表

        将 JSON 格式的参数字符串或列表解析为 ApiRequestParam 列表。

        Args:
            data: JSON 字符串或列表

        Returns:
            解析后的参數列表，解析失败返回空列表
        """
        if data:
            if isinstance(data, str):
                data = orjson.loads(data)
            return [ApiRequestParam(**item) for item in data]
        return []

    @staticmethod
    def _convert_api_to_response(api) -> ApiResponse:
        """将 API 模型或字典转换为 ApiResponse

        Args:
            api: API 模型或字典

        Returns:
            ApiResponse 对象
        """
        response = ApiResponse.model_validate(api)
        response.request_headers = ApiService._parse_request_params(api.request_headers)
        response.request_params = ApiService._parse_request_params(api.request_params)
        response.request_body = ApiService._parse_request_params(api.request_body)
        return response

    @staticmethod
    def _group_apis_by_module(apis: list) -> dict:
        """按 module_id 分组 ApiResponse

        Args:
            apis: ApiResponse 列表

        Returns:
            按 module_id 分组的字典
        """
        apis_by_module = {}
        for api in apis:
            module_id = api.module_id
            if module_id:
                if module_id not in apis_by_module:
                    apis_by_module[module_id] = []
                apis_by_module[module_id].append(api)
        return apis_by_module

    @staticmethod
    def _build_api_tree(module_nodes: list, apis_by_module: dict) -> List[ApiTreeNode]:
        """构建 API 树

        Args:
            module_nodes: 模块树节点列表
            apis_by_module: 按 module_id 分组的字典

        Returns:
            API 树节点列表
        """
        result = []
        for node in module_nodes:
            children = ApiService._build_api_tree(node.children, apis_by_module) if node.children else []
            result.append(ApiTreeNode(
                module_id=node.id,
                module_name=node.name,
                apis=apis_by_module.get(node.id, []),
                children=children
            ))
        return result

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
        # 获取项目下所有模块并转为字典格式
        all_modules = await module_repository.list_by_project(project_id)
        module_dicts = [m.to_dict() for m in all_modules]

        # 复用 module_service 的模块树构建方法
        module_tree = module_service.build_module_tree_from_dict(module_dicts)

        # 获取项目下所有接口并转换为 ApiResponse
        all_apis = await api_repository.list_by_project(project_id)
        api_responses = [ApiService._convert_api_to_response(api) for api in all_apis]

        # 复用公共方法构建 API 树
        return ApiService._build_api_tree(
            module_tree, ApiService._group_apis_by_module(api_responses))

    @staticmethod
    async def get_apis_compare(project_id: str) -> ApiTreeDocumentResponse:
        """获取 API 对比文档
        
        从 graph state 获取原始版本和优化版本的 API 树形结构。
        
        Args:
            project_id: 项目 ID
            
        Returns:
            API 树文档响应（原始版和优化版）
        """
        state = await main_agent.get_state(project_id)
        modules = state.get("optimized_modules") or []

        # 复用 module_service 的模块树构建方法
        module_tree = module_service.build_module_tree_from_dict(modules)

        # 分别构建原始版和优化版的 API 树
        original_apis = state.get("original_apis") if state else []
        optimized_apis = state.get("optimized_apis") if state else []

        original_api_tree = ApiService._build_api_tree(
            module_tree, ApiService._group_apis_by_module(
                [ApiService._convert_api_to_response(api) for api in original_apis]))
        optimized_api_tree = ApiService._build_api_tree(
            module_tree, ApiService._group_apis_by_module(
                [ApiService._convert_api_to_response(api) for api in optimized_apis]))

        return ApiTreeDocumentResponse(
            original=original_api_tree,
            optimized=optimized_api_tree
        )


# 导出单例
api_service = ApiService()
