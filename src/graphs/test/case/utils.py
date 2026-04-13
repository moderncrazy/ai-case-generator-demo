from src.graphs.schemas import StateModule
from src.graphs.test.case.schemas import TestCase


def validate_module_ids_str(test_cases: list[TestCase], modules: list[StateModule]) -> str:
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
