import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

from src.models import Api
from src.enums import HttpMethod


class ApiCreate(BaseModel):
    """创建接口参数"""
    project_id: str
    name: str
    method: HttpMethod
    path: str
    module_id: str
    description: str
    request_params: str
    request_body: str
    response_schema: str
    test_script: Optional[str] = None


class ApiRepository:
    """接口 Repository"""

    def __init__(self):
        self.model = Api

    async def create(self, api: ApiCreate) -> str | None:
        """创建接口"""
        now = datetime.now()
        results = await self.model.insert(
            self.model(
                id=str(uuid.uuid4()),
                project_id=api.project_id,
                module_id=api.module_id,
                name=api.name,
                method=api.method.value,
                path=api.path,
                description=api.description,
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
        name: Optional[str] = None,
        method: Optional[HttpMethod] = None,
        path: Optional[str] = None,
        module_id: Optional[str] = None,
        description: Optional[str] = None,
        request_params: Optional[str] = None,
        request_body: Optional[str] = None,
        response_schema: Optional[str] = None,
        test_script: Optional[str] = None,
    ) -> None:
        """更新接口"""
        update_data = {self.model.updated_at: datetime.now()}
        if name is not None:
            update_data[self.model.name] = name
        if method is not None:
            update_data[self.model.method] = method.value
        if path is not None:
            update_data[self.model.path] = path
        if module_id is not None:
            update_data[self.model.module_id] = module_id
        if description is not None:
            update_data[self.model.description] = description
        if request_params is not None:
            update_data[self.model.request_params] = request_params
        if request_body is not None:
            update_data[self.model.request_body] = request_body
        if response_schema is not None:
            update_data[self.model.response_schema] = response_schema
        if test_script is not None:
            update_data[self.model.test_script] = test_script

        await self.model.update(update_data).where(
            self.model.id == id
        )

    async def get_by_id(self, id: str) -> Optional[Api]:
        """根据 ID 获取记录"""
        result = await self.model.select().where(
            self.model.id == id
        ).first()
        return Api(**result) if result else None

    async def get_by_path_and_method(self, path: str, method: HttpMethod) -> Optional[Api]:
        """根据路径和方法获取接口"""
        result = await self.model.select().where(
            self.model.path == path,
            self.model.method == method.value
        ).first()
        return Api(**result) if result else None

    async def list_by_project(self, project_id: str) -> List[Api]:
        """获取项目的所有接口"""
        results = await self.model.select().where(
            self.model.project_id == project_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [Api(**item) for item in results]

    async def list_by_module(self, module_id: str) -> List[Api]:
        """获取模块的所有接口"""
        results = await self.model.select().where(
            self.model.module_id == module_id
        ).order_by(
            self.model.created_at, ascending=False
        )
        return [Api(**item) for item in results]

    async def count_by_project(self, project_id: str) -> int:
        """统计项目的接口数量"""
        return await self.model.count().where(
            self.model.project_id == project_id
        )

    async def delete_by_project(self, project_id: str) -> int:
        """删除项目的所有接口"""
        return await self.model.delete().where(
            self.model.project_id == project_id
        )


# 全局单例实例
api_repository = ApiRepository()
