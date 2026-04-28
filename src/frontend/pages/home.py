import streamlit as st
import streamlit_antd_components as sac

from src.frontend.utils import utils
from src.frontend.enums.project_progress import ProjectProgress
from src.frontend.service.project_service import ProjectService

PROJECT_PAGINATION_KEY = "project_pagination"

STATE_PROJECTS_RESP = "projects_resp"

CONFIG_PROJECT_PAGE_SIZE = 10


def to_project_page(project_id):
    st.switch_page("pages/project.py", query_params={"project_id": project_id})


@st.dialog("删除项目")
def delete_project_dialog(project_id: str, project_name: str):
    st.markdown(f"## 确认删除项目： {project_name} 吗？", text_alignment="center")
    st.markdown(":red[此操作不可逆请谨慎操作！]", text_alignment="center")
    confirm_col, cancel_col = st.columns([1, 1])
    with confirm_col:
        if st.button("确认", type="primary", use_container_width=True):
            del_result = ProjectService.delete_project(project_id, utils.get_user_id())
            if del_result:
                st.session_state[STATE_PROJECTS_RESP] = None
                st.rerun()
    with cancel_col:
        if st.button("取消", type="secondary", use_container_width=True):
            st.rerun()


def app():
    """首页"""

    # 初始化页面
    utils.init_page()

    title, github = st.columns([3, 1], vertical_alignment="top")
    with title:
        st.title("AI Case Generator Demo")
    with github:
        st.markdown("""
        #### ⭐ 欢迎支持项目
        [![GitHub Stars](https://img.shields.io/github/stars/moderncrazy/ai-case-generator-demo?style=social)](https://github.com/moderncrazy/ai-case-generator-demo)
        [![GitHub Issues](https://img.shields.io/github/issues-raw/moderncrazy/ai-case-generator-demo)](https://github.com/moderncrazy/ai-case-generator-demo/issues)
        """)

    st.markdown("---")

    # Demo 说明区
    with st.expander("📖 关于项目", expanded=True):
        introduction, github = st.columns([2, 1], vertical_alignment="top")

        with introduction:
            st.markdown("""
            ### 🎯 项目简介
            基于 LLM 的智能需求分析和测试用例生成平台，通过 LangGraph Multi-Agent 架构实现从需求文档到测试用例的全流程自动化：
    
            - 📝 **需求分析** - 上传需求文档，AI 自动提取关键信息、识别业务逻辑
            - 🏗️ **系统设计** - 生成架构方案、模块划分、数据库结构、API 接口文档
            - 🧪 **用例生成** - 自动生成带优先级分级的测试用例
            
            ### 🚀 使用方法
            1. 创建项目 → 输入项目名称和描述
            2. 输入需求 → 描述功能需求或上传需求文档
            3. AI 生成 → 自动完成：需求大纲 → 模块拆分 → 系统设计 → 测试用例
            4. 查看结果 → 查看生成的需求文档、架构设计、测试用例
            """)

        with github:
            st.markdown("""
            ### 📢 项目状态
            本项目目前处于 **Early Demo** 阶段。正聚焦于 **Multi-Agent 协同精度**与**系统响应性能**的优化
            
            **✨ 技术亮点**
            - 🔧 LangGraph 状态机编排 - 多 Agent 并发协作与状态自动归约
            - ⚡ 异步 RAG 架构 - Milvus 向量检索 + BGE-M3 本地向量化
            - 📡 SSE 流式渲染 - 实时展示 Agent 执行过程
            
            ---
            
            **💼 关于作者**
            
            一名拥有 Java & Node.js 资深背景的开发者，目前正深度投入于 Python AI 生态与 Agent 编排架构的落地实践
               - 🔭 **职业状态**：处于开放的技术探索与职业转型期，欢迎关于 **Python 架构**、 **测试开发工程化** 或 **模型评测** 相关的职位邀约与技术交流
               
            \u200c
            """)

    # 创建项目区
    st.subheader("✨ 创建新项目")
    with st.form("create_project_form"):
        col1, col2 = st.columns([2, 1], vertical_alignment="bottom")
        with col1:
            project_name = st.text_input("项目名称", placeholder="请输入项目名称")
        with col2:
            submitted = st.form_submit_button("创建项目", type="primary", use_container_width=True)

        project_description = st.text_area("项目描述（选填）", placeholder="请输入项目描述", height=80)

        if submitted and project_name:
            with st.spinner("创建中..."):
                project_id = ProjectService.create_project(project_name, project_description)
                if project_id:
                    to_project_page(project_id)
        elif submitted and not project_name:
            st.warning("⚠️ 请输入项目名称")

    st.divider()

    # 项目列表区
    st.subheader("📁 项目列表")

    # 展示表头
    cols = st.columns([2, 2, 3, 1, 1])
    headers = ["项目名称", "描述", "进度", "创建时间", "操作"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")

    # 获取项目列表
    if not st.session_state.get(STATE_PROJECTS_RESP):
        st.session_state[STATE_PROJECTS_RESP] = ProjectService.get_projects(page=1, page_size=CONFIG_PROJECT_PAGE_SIZE)

    projects_resp = st.session_state.get(STATE_PROJECTS_RESP)

    st.divider()

    if projects_resp and projects_resp.items:
        page = projects_resp.page
        total = projects_resp.total
        projects = projects_resp.items

        for project in projects:
            cols = st.columns([2, 2, 3, 1, 1])

            # 项目名称
            with cols[0]:
                st.markdown(f"**{project.name}**")

            # 描述
            with cols[1]:
                desc = project.description
                st.caption(desc[:30] + "..." if len(desc) > 30 else desc if desc else "-")

            # 进度
            with cols[2]:
                progress = ProjectProgress.from_code(project.progress)
                st.progress(progress.get_percent())
                st.caption(progress.label)

            # 创建时间
            with cols[3]:
                created_at = project.created_at
                if created_at:
                    st.caption(created_at.strftime("%Y-%m-%d %H:%M"))
                else:
                    st.caption("-")

            # 操作按钮
            with cols[4]:
                enter_col, delete_col = st.columns(2)
                with enter_col:
                    if st.button("进入", key=f"project_enter_{project.id}", type="primary"):
                        to_project_page(project.id)
                with delete_col:
                    if st.button("删除", key=f"project_delete_{project.id}", type="secondary"):
                        delete_project_dialog(project.id, project.name)

        st.divider()

        # 分页
        select_page = sac.pagination(key=PROJECT_PAGINATION_KEY, total=total, index=page,
                                     page_size=CONFIG_PROJECT_PAGE_SIZE, align='center',
                                     show_total=True)
        # 根据分页加载项目
        if select_page != page:
            st.session_state[STATE_PROJECTS_RESP] = ProjectService.get_projects(
                page=int(select_page), page_size=CONFIG_PROJECT_PAGE_SIZE)

    else:
        st.info("📭 暂无项目，请创建第一个项目开始使用")


if __name__ == "__main__":
    app()
