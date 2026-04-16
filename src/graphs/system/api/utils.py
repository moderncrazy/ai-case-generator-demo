from src.graphs.schemas import StateModule
from src.graphs.system.api.schemas import SystemApi


def validate_module_ids_str(apis: list[SystemApi], modules: list[StateModule]) -> str:
    """验证 API 的模块 ID 是否有效
    
    检查每个 API 的 module_id 是否在模块列表中存在，
    返回无效的 API 名称列表。
    
    Args:
        apis: API 列表
        modules: 模块列表
        
    Returns:
        空字符串表示验证通过，错误信息字符串表示验证失败
    """
    # 收集所有 module_id
    module_ids = [module["id"] for module in modules]
    # 找出无效的 API
    module_id_not_found = []
    for api in apis:
        if api.module_id not in module_ids:
            module_id_not_found.append(api.name)

    error_message = ""
    if module_id_not_found:
        error_message += f"模块Id无效的接口：{",".join(module_id_not_found)}\n"
    return error_message
