from typing import List, Tuple
from src.models.module import Module
from src.repositories.module_repository import module_repository
from src.schemas.module import ModuleResponse, ModuleTreeNode


class ModuleService:
    """模块服务
    
    提供模块相关的业务逻辑处理，
    包括查询模块列表、获取模块树形结构等功能。
    """

    @staticmethod
    async def list_modules(
            project_id: str,
            page: int = 1,
            page_size: int = 20,
            parent_id: str = None,
    ) -> Tuple[List[ModuleResponse], int]:
        """查询模块列表
        
        分页查询项目的模块列表。
        
        Args:
            project_id: 项目 ID
            page: 页码（从 1 开始）
            page_size: 每页数量
            parent_id: 按父模块筛选（可选）
            
        Returns:
            (模块响应列表, 总数) 元组
        """
        modules, total = await module_repository.paginate(
            project_id=project_id,
            page=page,
            page_size=page_size,
            parent_id=parent_id,
        )
        return [ModuleResponse.model_validate(m.to_dict()) for m in modules], total

    @staticmethod
    async def get_modules_tree(project_id: str) -> List[ModuleTreeNode]:
        """获取模块树形结构
        
        构建并返回项目的完整模块树形结构。
        
        Args:
            project_id: 项目 ID
            
        Returns:
            模块树形结构列表（递归嵌套）
        """
        # 获取项目下所有模块
        all_modules = await module_repository.list_by_project(project_id)

        # 构建树形结构
        def build_tree(parent_id: str = None) -> List[ModuleTreeNode]:
            children = []
            for module in all_modules:
                if module.parent_id == parent_id:
                    node = ModuleTreeNode(
                        id=module.id,
                        parent_id=module.parent_id,
                        name=module.name,
                        description=module.description,
                        children=build_tree(module.id)
                    )
                    children.append(node)
            return children

        return build_tree()


# 全局单例实例
module_service = ModuleService()
