from src.models.module import Module


class ModuleService:
    """Module 服务"""

    @staticmethod
    def validate_modules(modules: list[Module]) -> dict:
        """校验模块列表的完整性

        - 白(未访问) → 灰(正在访问) → 黑(已完成)
        - 遍历时遇到灰色的节点说明有环
        使用 DFS 三色标记法检测循环引用，同时检查：
        1. 是否有根模块（parent_id 为空）
        2. 自引用检查
        3. 循环引用检查
        4. 父级是否存在

        Args:
            modules: 模块列表

        Returns:
            错误信息列表，若为空则校验通过
        """
        not_root = False
        not_found = []
        self_reference = []
        circular_reference = []
        not_found_parent_id = []
        module_map = {m.id: m for m in modules if m.id}
        color = {m.id: 0 for m in modules if m.id}  # 0=白, 1=灰, 2=黑

        # 检查是否有根模块
        root_modules = [m for m in modules if not m.parent_id]
        if not root_modules:
            not_root = True

        def dfs(module_id: str, path: list[str]) -> None:
            color[module_id] = 1  # 标记为灰色（访问中）
            module = module_map.get(module_id)

            if not module:
                not_found.append(module_id)
            else:
                parent_id = module.parent_id
                if parent_id:
                    if parent_id == module_id:
                        self_reference.append(module_id)
                    elif color.get(parent_id) == 1:  # 遇到灰色 = 有环
                        circular_reference.append(module_id)
                    elif parent_id not in module_map:
                        not_found_parent_id.append(module_id)
                    else:
                        dfs(parent_id, path + [module["name"]])

            color[module_id] = 2  # 标记为黑色（完成）

        for module_id in color:
            if color[module_id] == 0:
                dfs(module_id, [])

        return {"not_root": not_root, "not_found": not_found, "self_reference": self_reference,
                "circular_reference": circular_reference, "not_found_parent_id": not_found_parent_id}

    @staticmethod
    def validate_modules_to_str(modules: list[Module]) -> str:
        error_message = ""
        result = module_service.validate_modules(modules)
        if result.get("not_root"):
            error_message += "模块没有根节点\n"
        if result.get("not_found"):
            error_message += f"模块不存在：{",".join(result["not_found"])}\n"
        if result.get("self_reference"):
            error_message += f"模块自引用：{",".join(result["self_reference"])}\n"
        if result.get("circular_reference"):
            error_message += f"模块循环引用：{",".join(result["circular_reference"])}\n"
        if result.get("not_found_parent_id"):
            error_message += f"parent_id不存在：{",".join(result["not_found_parent_id"])}\n"
        return error_message


# 导出单例
module_service = ModuleService()
