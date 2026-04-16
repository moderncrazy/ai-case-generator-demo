from src.graphs.schemas import StateRequirementModule
from src.enums.requirement_module_status import RequirementModuleStatus


def update_module_content_by_name(name: str, content: str, modules: list[StateRequirementModule]):
    """根据模块名称更新模块内容和状态
    
    在需求模块优化完成后，将优化后的内容更新到模块列表中。
    状态变更为 DRAFT（草稿），等待最终确认。
    
    Args:
        name: 要更新的模块名称
        content: 优化后的模块内容
        modules: 模块列表（原地修改）
    """
    for module in modules:
        if module["name"] == name:
            module["content"] = content
            module["status"] = RequirementModuleStatus.DRAFT
