from src.graphs.common.schemas import StateModule
from src.graphs.test.case.schemas import TestCase


def validate_module_ids_str(test_cases: list[TestCase], modules: list[StateModule]) -> str:
    """校验测试用例中引用的模块ID是否有效
    
    检查每个测试用例的 module_id 是否在模块列表中存在，
    返回无效测试用例的标题列表。
    
    Args:
        test_cases: 测试用例列表
        modules: 模块列表
        
    Returns:
        错误信息，若为空则校验通过
    """
    # 收集所有 module_id
    module_ids = [module["id"] for module in modules]
    # 找出无效的 测试用例
    module_id_not_found = []
    for test_case in test_cases:
        if test_case.module_id not in module_ids:
            module_id_not_found.append(test_case.title)

    error_message = ""
    if module_id_not_found:
        error_message += f"模块Id无效的测试用例：{",".join(module_id_not_found)}\n"
    return error_message
