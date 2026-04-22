import json
import asyncio

import streamlit as st
import streamlit_antd_components as sac

from src.frontend.utils import utils
from src.frontend import constant as const
from src.frontend.service.project_service import ProjectService
from src.frontend.enums.project_file_type import ProjectFileType
from src.frontend.enums.project_progress import ProjectProgress
from src.frontend.schemas.project import ProjectDetailResponse

from src.frontend.components.chat_frame import chat_frame

STATE_SHOW_PROJECT_FILE_TYPE = "show_project_file_type"


def project_file_on_click(project_file_type: ProjectFileType):
    st.session_state[STATE_SHOW_PROJECT_FILE_TYPE] = project_file_type


def show_project_file_type(file_container, project: ProjectDetailResponse):
    match st.session_state[STATE_SHOW_PROJECT_FILE_TYPE]:
        case ProjectFileType.REQUIREMENT_OUTLINE:
            if project.requirement_outline_design:
                file_container.markdown(project.requirement_outline_design)
                return
        case ProjectFileType.REQUIREMENT_MODULE:
            if project.requirement_module_design:
                modules = json.loads(project.requirement_module_design)
                for module in modules:
                    file_container.title(f"{module["order"]}. {module["name"]}", text_alignment="left")
                    file_container.badge(module["status"], color="blue")
                    file_container.caption(module["description"], text_alignment="left")
                    file_container.divider()
                    file_container.markdown(module.get("content") or "> 暂无详细内容")
                return
        case ProjectFileType.REQUIREMENT_OVERALL:
            if project.requirement_overall_design:
                file_container.markdown(project.requirement_overall_design)
                return
        case ProjectFileType.SYSTEM_ARCHITECTURE:
            if project.architecture_design:
                file_container.markdown(project.architecture_design)
                return
        case ProjectFileType.SYSTEM_MODULE:
            pass
        case ProjectFileType.SYSTEM_DATABASE:
            if project.database_design:
                file_container.markdown(project.database_design)
                return
        case ProjectFileType.SYSTEM_API:
            pass
        case ProjectFileType.TEST_CASE:
            pass
        case _:
            file_container.subheader("项目文档展示区域", text_align="center")


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
    project = asyncio.run(ProjectService.get_project_detail(project_id))

    if not project:
        st.error("❌ 项目不存在或加载失败")
        st.page_link("pages/home.py", label="返回首页")
        return

        # 默认打开聊天框
    if st.session_state.get(const.CHAT_POPOVER_KEY) is None:
        st.session_state[const.CHAT_POPOVER_KEY] = True

    # 聊天框
    asyncio.run(chat_frame(project_id))

    back, title = st.columns([2, 30], vertical_alignment="center")
    with back:
        st.page_link("pages/home.py", label="\u200c\n\n返回\n\n\u200c", icon=":material/arrow_back:")
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
    if not st.session_state.get(STATE_SHOW_PROJECT_FILE_TYPE):
        st.session_state[STATE_SHOW_PROJECT_FILE_TYPE] = ProjectFileType.REQUIREMENT_OUTLINE

    # 展示项目文件
    show_project_file_type(file_container, project)

    # 项目文件侧边栏
    with st.sidebar:
        st.header("项目文档列表", text_alignment="center")
        st.button("需求大纲", type="tertiary", use_container_width=True,
                  on_click=lambda: project_file_on_click(ProjectFileType.REQUIREMENT_OUTLINE),
                  disabled=False if project.requirement_outline_design else True)

        st.button("需求模块", type="tertiary", use_container_width=True,
                  on_click=lambda: project_file_on_click(ProjectFileType.REQUIREMENT_MODULE),
                  disabled=False if project.requirement_module_design else True)

        st.button("需求PRD", type="tertiary", use_container_width=True,
                  on_click=lambda: project_file_on_click(ProjectFileType.REQUIREMENT_OVERALL),
                  disabled=False if project.requirement_overall_design else True)

        st.button("架构文档", type="tertiary", use_container_width=True,
                  on_click=lambda: project_file_on_click(ProjectFileType.SYSTEM_ARCHITECTURE),
                  disabled=False if project.architecture_design else True)

        st.button("系统模块", type="tertiary", use_container_width=True,
                  on_click=lambda: project_file_on_click(ProjectFileType.SYSTEM_MODULE),
                  disabled=True)

        st.button("数据库文档", type="tertiary", use_container_width=True,
                  on_click=lambda: project_file_on_click(ProjectFileType.SYSTEM_DATABASE),
                  disabled=False if project.database_design else True)

        st.button("接口文档", type="tertiary", use_container_width=True,
                  on_click=lambda: project_file_on_click(ProjectFileType.SYSTEM_API),
                  disabled=True)

        st.button("测试用例", type="tertiary", use_container_width=True,
                  on_click=lambda: project_file_on_click(ProjectFileType.TEST_CASE),
                  disabled=True)


if __name__ == "__main__":
    app()
