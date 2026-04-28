import time
import streamlit as st
import streamlit_antd_components as sac
from streamlit_adjustable_columns import adjustable_columns

from src.frontend.utils import utils
from src.frontend import constant as const
from src.frontend.service.api_service import ApiService
from src.frontend.service.module_service import ModuleService
from src.frontend.service.project_service import ProjectService
from src.frontend.service.test_case_service import TestCaseService
from src.frontend.service.project_document_service import ProjectDocumentService
from src.frontend.enums.project_doc_type import ProjectDocType
from src.frontend.enums.project_progress import ProjectProgress
from src.frontend.schemas.project import ProjectBasicInfoResponse

from src.frontend.components.chat_frame import chat_frame, OnChangeEvent

STATE_RISKS = "risks"
STATE_DISABLE_ALL = "disable_all"
STATE_UNCLEAR_POINTS = "unclear_points"
STATE_SHOW_PROJECT_FILE_TYPE = "show_project_file_type"


def project_doc_button_label(label: str, project_file_type: ProjectDocType) -> str:
    """如果当前 type 被选中 label 变成红色"""
    if st.session_state.get(STATE_SHOW_PROJECT_FILE_TYPE) == project_file_type:
        return f":red[{label}]"
    return label


def project_doc_on_click(project_file_type: ProjectDocType):
    st.session_state[STATE_SHOW_PROJECT_FILE_TYPE] = project_file_type


def show_project_file_type(file_container, project: ProjectBasicInfoResponse):
    match st.session_state.get(STATE_SHOW_PROJECT_FILE_TYPE):
        case ProjectDocType.REQUIREMENT_OUTLINE:
            if project.has_requirement_outline:
                resp = ProjectDocumentService.get_requirement_outline(project.id)
                if resp and resp.content:
                    file_container.markdown(resp.content)
        case ProjectDocType.REQUIREMENT_MODULE:
            if project.has_requirement_modules:
                resp = ProjectDocumentService.get_requirement_modules(project.id)
                if resp and resp.modules:
                    for module in resp.modules:
                        file_container.title(f"{module.order}. {module.name}", text_alignment="left")
                        file_container.badge(module.status, color="blue")
                        file_container.caption(module.description, text_alignment="left")
                        file_container.divider()
                        file_container.markdown(module.content or "> 暂无详细内容")
        case ProjectDocType.REQUIREMENT_OVERALL:
            if project.has_requirement_overall:
                resp = ProjectDocumentService.get_requirement_overall_compare(project.id)
                if resp:
                    with file_container:
                        original, optimized = adjustable_columns(2, labels=["原始文档", "优化后文档"])
                        with original:
                            st.markdown(resp.original or "")
                        with optimized:
                            st.markdown(resp.optimized or "")
        case ProjectDocType.SYSTEM_ARCHITECTURE:
            if project.has_architecture:
                resp = ProjectDocumentService.get_architecture_compare(project.id)
                if resp:
                    with file_container:
                        original, optimized = adjustable_columns(2, labels=["原始文档", "优化后文档"])
                        with original:
                            st.markdown(resp.original or "")
                        with optimized:
                            st.markdown(resp.optimized or "")
        case ProjectDocType.SYSTEM_MODULE:
            if project.has_modules:
                resp = ModuleService.get_modules_compare(project.id)
                if resp:
                    with file_container:
                        original, optimized = adjustable_columns(2, labels=["原始文档", "优化后文档"])
                        with original:
                            st.markdown(ModuleService.get_markdown_by_modules_tree(resp.original))
                        with optimized:
                            st.markdown(ModuleService.get_markdown_by_modules_tree(resp.optimized))
        case ProjectDocType.SYSTEM_DATABASE:
            if project.has_database:
                resp = ProjectDocumentService.get_database_compare(project.id)
                if resp:
                    with file_container:
                        original, optimized = adjustable_columns(2, labels=["原始文档", "优化后文档"])
                        with original:
                            st.markdown(resp.original or "")
                        with optimized:
                            st.markdown(resp.optimized or "")
        case ProjectDocType.SYSTEM_API:
            if project.has_apis:
                resp = ApiService.get_apis_compare(project.id)
                if resp:
                    with file_container:
                        original, optimized = adjustable_columns(2, labels=["原始文档", "优化后文档"])
                        with original:
                            st.markdown(ApiService.get_markdown_by_apis_tree(resp.original))
                        with optimized:
                            st.markdown(ApiService.get_markdown_by_apis_tree(resp.optimized))
        case ProjectDocType.TEST_CASE:
            if project.has_test_cases:
                resp = TestCaseService.get_test_cases_compare(project.id)
                if resp:
                    with file_container:
                        original, optimized = adjustable_columns(2, labels=["原始文档", "优化后文档"])
                        with original:
                            st.markdown(TestCaseService.get_markdown_by_test_cases_tree(resp.original))
                        with optimized:
                            st.markdown(TestCaseService.get_markdown_by_test_cases_tree(resp.optimized))
        case ProjectDocType.ISSUES:
            with file_container:
                risks, unclear_points = adjustable_columns(2, labels=["风险点", "待明确问题"])
                with risks:
                    st.markdown(ProjectDocumentService.get_markdown_by_issues(st.session_state.get(STATE_RISKS)))
                with unclear_points:
                    st.markdown(
                        ProjectDocumentService.get_markdown_by_issues(st.session_state.get(STATE_UNCLEAR_POINTS)))
        case _:
            (file_container
             .container(border=True, height=500, horizontal_alignment="center", vertical_alignment="center")
             .caption("暂无项目文档，快来通过对话生成项目文档吧！", text_alignment="center"))


def chat_frame_on_change(event: OnChangeEvent, data: dict):
    match event:
        case OnChangeEvent.PROJECT_DOC_UPDATE:
            time.sleep(1)
            st.session_state[STATE_SHOW_PROJECT_FILE_TYPE] = data["content"]


def app():
    """项目详情页"""

    # 初始化页面
    utils.init_page()

    # 获取项目ID
    project_id = st.query_params.get("project_id")

    if not project_id:
        st.error("❌ 未选择项目，请从首页进入")
        st.page_link("pages/home.py", label="返回首页")
        return

    # 获取项目详情
    project = ProjectService.get_project_detail(project_id)

    if not project:
        st.error("❌ 项目不存在或加载失败")
        st.page_link("pages/home.py", label="返回首页")
        return

        # 默认打开聊天框
    if st.session_state.get(const.CHAT_EXPANDER_KEY) is None:
        st.session_state[const.CHAT_EXPANDER_KEY] = True

    # 聊天框
    chat_frame(project_id, on_change=chat_frame_on_change)

    # 返回按钮 和 标题
    back, title = st.columns([2, 28], vertical_alignment="center")
    with back:
        st.page_link("pages/home.py", label="\u200c\n\n返回\n\n\u200c", icon=":material/arrow_back:",
                     disabled=st.session_state.get(STATE_DISABLE_ALL, False))
    with title:
        # 页面标题
        st.title(f"📂 {project.name}")

    st.divider()

    # 项目进度
    current_progress = ProjectProgress.from_code(project.progress)
    sac.steps(
        index=current_progress.get_index(),
        items=[sac.StepsItem(title=step.label, disabled=True)
               for index, step in enumerate(ProjectProgress, 0)],
        placement="vertical"
    )

    # 文档显示区
    file_container = st.container()

    # 默认展示需求大纲
    if not st.session_state.get(STATE_SHOW_PROJECT_FILE_TYPE) and project.has_requirement_outline:
        st.session_state[STATE_SHOW_PROJECT_FILE_TYPE] = ProjectDocType.REQUIREMENT_OUTLINE

    # 展示项目文件
    show_project_file_type(file_container, project)

    # 项目文件侧边栏
    with st.sidebar:
        st.header("项目文档列表", text_alignment="center")

        # 获取风险点和不确定项
        issues_resp = ProjectDocumentService.get_issues(project.id)
        if issues_resp and (issues_resp.risks or issues_resp.unclear_points):
            st.session_state[STATE_RISKS] = issues_resp.risks
            st.session_state[STATE_UNCLEAR_POINTS] = issues_resp.unclear_points
            st.button(project_doc_button_label("风险和不确定项", ProjectDocType.ISSUES), type="tertiary",
                      icon="🚨", use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.ISSUES),
                      disabled=st.session_state.get(STATE_DISABLE_ALL, False))

        st.button(project_doc_button_label("需求大纲", ProjectDocType.REQUIREMENT_OUTLINE), type="tertiary",
                  use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.REQUIREMENT_OUTLINE),
                  disabled=st.session_state.get(STATE_DISABLE_ALL, False) or not project.has_requirement_outline)

        st.button(project_doc_button_label("需求模块", ProjectDocType.REQUIREMENT_MODULE), type="tertiary",
                  use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.REQUIREMENT_MODULE),
                  disabled=st.session_state.get(STATE_DISABLE_ALL, False) or not project.has_requirement_modules)

        st.button(project_doc_button_label("需求PRD", ProjectDocType.REQUIREMENT_OVERALL), type="tertiary",
                  use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.REQUIREMENT_OVERALL),
                  disabled=st.session_state.get(STATE_DISABLE_ALL, False) or not project.has_requirement_overall)

        st.button(project_doc_button_label("架构文档", ProjectDocType.SYSTEM_ARCHITECTURE), type="tertiary",
                  use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.SYSTEM_ARCHITECTURE),
                  disabled=st.session_state.get(STATE_DISABLE_ALL, False) or not project.has_architecture)

        st.button(project_doc_button_label("系统模块", ProjectDocType.SYSTEM_MODULE), type="tertiary",
                  use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.SYSTEM_MODULE),
                  disabled=st.session_state.get(STATE_DISABLE_ALL, False) or not project.has_modules)

        st.button(project_doc_button_label("数据库文档", ProjectDocType.SYSTEM_DATABASE), type="tertiary",
                  use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.SYSTEM_DATABASE),
                  disabled=st.session_state.get(STATE_DISABLE_ALL, False) or not project.has_database)

        st.button(project_doc_button_label("接口文档", ProjectDocType.SYSTEM_API), type="tertiary",
                  use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.SYSTEM_API),
                  disabled=st.session_state.get(STATE_DISABLE_ALL, False) or not project.has_apis)

        st.button(project_doc_button_label("测试用例", ProjectDocType.TEST_CASE), type="tertiary",
                  use_container_width=True, on_click=lambda: project_doc_on_click(ProjectDocType.TEST_CASE),
                  disabled=st.session_state.get(STATE_DISABLE_ALL, False) or not project.has_test_cases)


if __name__ == "__main__":
    app()
