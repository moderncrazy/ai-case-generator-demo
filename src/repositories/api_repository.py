import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

from src.models.business.api import Api
from src.enums.http_method import HttpMethod


class ApiCreate(BaseModel):
    """创建接口参数"""
    id: str
    """API ID"""
    project_id: str
    """所属项目 ID"""
    name: str
    """接口名称"""
    method: HttpMethod
    """HTTP 方法"""
    path: str
    """接口路径"""
    module_id: str
    """所属模块 ID"""
    description: Optional[str] = None
    """接口描述"""
    request_headers: Optional[str] = None
    """请求头参数"""
    request_params: Optional[str] = None
    """URL 查询参数"""
    request_body: Optional[str] = None
    """请求体参数"""
    response_schema: str
    """响应结构定义"""
    test_script: Optional[str] = None
    """测试脚本"""


class ApiUpdate(BaseModel):
    """更新接口参数"""
    name: Optional[str] = None
    """接口名称"""
    method: Optional[HttpMethod] = None
    """HTTP 方法"""
    path: Optional[str] = None
    """接口路径"""
    module_id: Optional[str] = None
    """所属模块 ID"""
    description: Optional[str] = None
    """接口描述"""
    request_headers: Optional[str] = None
    """请求头参数"""
    request_params: Optional[str] = None
    """URL 查询参数"""
    request_body: Optional[str] = None
    """请求体参数"""
    response_schema: Optional[str] = None
    """响应结构定义"""
    test_script: Optional[str] = None
    """测试脚本"""


class ApiBulkUpdate(BaseModel):
    """更新接口参数"""
    id: str
    """API ID"""
    name: str
    """接口名称"""
    method: HttpMethod
    """HTTP 方法"""
    path: str
    """接口路径"""
    module_id: str
    """所属模块 ID"""
    description: Optional[str] = None
    """接口描述"""
    request_headers: Optional[str] = None
    """请求头参数"""
    request_params: Optional[str] = None
    """URL 查询参数"""
    request_body: Optional[str] = None
    """请求体参数"""
    response_schema: str
    """响应结构定义"""
    test_script: Optional[str] = None
    """测试脚本"""


class ApiRepository:
    """接口 Repository
    
    提供 API 接口（Api）的数据库操作，
    包括创建、更新、查询、按模块统计、批量操作等功能。
    """

    def __init__(self):
        self.model = Api

    async def create(self, api: ApiCreate) -> str | None:
        """创建接口
        
        Args:
            api: 创建参数
            
        Returns:
            新建接口的 ID，失败返回 None
        """
        now = datetime.now()
        results = await self.model.insert(
            self.model(
                id=api.id or str(uuid.uuid4()),
                project_id=api.project_id,
                module_id=api.module_id,
                name=api.name,
                method=api.method.value,
                path=api.path,
                description=api.description,
                request_headers=api.request_headers,
                request_params=api.request_params,
                request_body=api.request_body,
                response_schema=api.response_schema,
                test_script=api.test_script,
                created_at=now,
                updated_at=now,
            )
        )
        return results[0]["id"] if results else None

    async def update(
            self,
            id: str,
            api: ApiUpdate
    ) -> None:
        """更新接口
        
        Args:
            id: 接口 ID
            api: 更新参数
        """
        update_data: dict = {self.model.updated_at: datetime.now()}
        if api.name is not None:
            update_data[self.model.name] = api.name
        if api.method is not None:
            update_data[self.model.method] = api.method.value
        if api.path is not None:
            update_data[self.model.path] = api.path
        if api.module_id is not None:
            update_data[self.model.module_id] = api.module_id
        if api.description is not None:
            update_data[self.model.description] = api.description
        if api.request_headers is not None:
            update_data[self.model.request_headers] = api.request_headers
        if api.request_params is not None:
            update_data[self.model.request_params] = api.request_params
        if api.request_body is not None:
            update_data[self.model.request_body] = api.request_body
        if api.response_schema is not None:
            update_data[self.model.response_schema] = api.response_schema
        if api.test_script is not None:
            update_data[self.model.test_script] = api.test_script

        await self.model.update(update_data).where(
            self.model.id == id
        )

    async def get_by_id(self, id: str) -> Optional[Api]:
        """根据 ID 获取接口
        
        Args:
            id: 接口 ID
            
        Returns:
            接口对象，不存在返回 None
        """
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return Api(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[Api]:
        """获取项目的所有接口
        
        Args:
            project_id: 项目 ID
            
        Returns:
            接口列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [Api(**item) for item in results]

    async def list_by_module(self, module_id: str) -> List[Api]:
        """获取模块的所有接口
        
        Args:
            module_id: 模块 ID
            
        Returns:
            接口列表（按创建时间降序）
        """
        results = await self.model.select().where(
            self.model.module_id == module_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [Api(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的接口数量
        
        Args:
            project_id: 项目 ID
            
        Returns:
            接口数量
        """
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有接口
        
        Args:
            project_id: 项目 ID
            
        Returns:
            删除的记录数
        """
        return await self.model.delete().where(
            self.model.project_id == project_id
        )

    async def bulk_update(self, project_id: str, apis: List[ApiBulkUpdate]) -> List[str]:
        """批量更新接口（先删除项目下所有接口再插入）

        Args:
            project_id: 项目ID
            apis: 接口更新参数列表

        Returns:
            插入的接口ID列表
        """
        # 先删除项目下所有接口
        await self.delete_by_project(project_id)

        now = datetime.now()
        instances = [
            self.model(
                id=item.id or str(uuid.uuid4()),
                project_id=project_id,
                module_id=item.module_id,
                name=item.name,
                method=item.method.value,
                path=item.path,
                description=item.description,
                request_headers=item.request_headers,
                request_params=item.request_params,
                request_body=item.request_body,
                response_schema=item.response_schema,
                test_script=item.test_script,
                created_at=now,
                updated_at=now,
            )
            for item in apis
        ]
        results = await self.model.insert(*instances)
        return [item["id"] for item in results]

    async def paginate(
            self,
            project_id: str,
            page: int = 1,
            page_size: int = 20,
            module_id: str = None,
    ) -> tuple[List[Api], int]:
        """分页查询接口
        
        Args:
            project_id: 项目 ID
            page: 页码
            page_size: 每页数量
            module_id: 按模块筛选
            
        Returns:
            (接口列表, 总数) 元组
        """
        base_where = self.model.project_id == project_id
        if module_id:
            base_where = base_where & (self.model.module_id == module_id)
        total = await self.model.count().where(base_where)
        results = await (
            self.model.select()
            .where(base_where)
            .order_by(self.model.created_at, ascending=False)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        apis = [Api(**item) for item in results]
        return apis, total


# 全局单例实例
api_repository = ApiRepository()
