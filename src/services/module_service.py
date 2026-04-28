from typing import List, Tuple
from src.repositories.module_repository import module_repository
from src.schemas.module import ModuleResponse, ModuleTreeNode, ModuleTreeDocumentResponse
from src.agents.main_agent import main_agent


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
    def _group_modules_by_parent(modules: list) -> dict:
        """按 parent_id 分组模块
        
        Args:
            modules: 模块列表
            
        Returns:
            按 parent_id 分组的字典
        """
        modules_by_parent = {}
        for m in modules:
            parent_id = m.get("parent_id")
            if parent_id not in modules_by_parent:
                modules_by_parent[parent_id] = []
            modules_by_parent[parent_id].append(m)
        return modules_by_parent

    @staticmethod
    def _build_module_tree(modules_by_parent: dict, parent_id=None) -> List[ModuleTreeNode]:
        """构建模块树
        
        Args:
            modules_by_parent: 按 parent_id 分组的字典
            parent_id: 父模块 ID
            
        Returns:
            模块树节点列表
        """
        result = []
        for m in modules_by_parent.get(parent_id, []):
            children = ModuleService._build_module_tree(modules_by_parent, m.get("id"))
            result.append(ModuleTreeNode(
                id=m.get("id"),
                parent_id=m.get("parent_id"),
                name=m.get("name", ""),
                description=m.get("description"),
                children=children
            ))
        return result

    @staticmethod
    def build_module_tree_from_dict(modules: list) -> List[ModuleTreeNode]:
        """从模块数据构建模块树
        
        公共方法，可被 api_service、test_case_service 等共用。
        
        Args:
            modules: 模块列表
            
        Returns:
            模块树形结构列表
        """
        if not modules:
            return []
        modules_by_parent = ModuleService._group_modules_by_parent(modules)
        return ModuleService._build_module_tree(modules_by_parent, None)

    @staticmethod
    async def get_modules_tree(project_id: str) -> List[ModuleTreeNode]:
        """获取模块树形结构
        
        构建并返回项目的完整模块树形结构。
        
        Args:
            project_id: 项目 ID
            
        Returns:
            模块树形结构列表
        """
        all_modules = await module_repository.list_by_project(project_id)
        return ModuleService.build_module_tree_from_dict([m.to_dict() for m in all_modules])

    @staticmethod
    async def get_modules_compare(project_id: str) -> ModuleTreeDocumentResponse:
        """获取系统模块对比文档
        
        从 graph state 获取原始版本和优化版本的模块树形结构。
        
        Args:
            project_id: 项目 ID
            
        Returns:
            模块树文档响应（原始版和优化版）
        """
        state = await main_agent.get_state(project_id)
        original_modules = ModuleService.build_module_tree_from_dict(
            state.get("original_modules") if state else [])
        optimized_modules = ModuleService.build_module_tree_from_dict(
            state.get("optimized_modules") if state else [])
        return ModuleTreeDocumentResponse(
            original=original_modules,
            optimized=optimized_modules
        )


# 全局单例实例
module_service = ModuleService()
