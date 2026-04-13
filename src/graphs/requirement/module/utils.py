from src.graphs.schemas import StateRequirementModule
from src.enums.requirement_module_status import RequirementModuleStatus


def update_module_content_by_name(name, content, modules: list[StateRequirementModule]):
    """根据名称修改对应模块内容"""
    for module in modules:
        if module["name"] == name:
            module["content"] = content
            module["status"] = RequirementModuleStatus.DRAFT
