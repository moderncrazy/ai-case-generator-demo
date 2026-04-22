import asyncio
import streamlit as st

from src.frontend.utils import utils
from src.frontend.enums.project_progress import ProjectProgress
from src.frontend.service.project_service import ProjectService

def app():
    """首页"""

    # 初始化页面
    utils.init_page()

    st.title("AI Case Generator Demo")
    st.markdown("---")

    # Demo 说明区
    with st.expander("📖 关于本项目", expanded=True):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("""
            ### 🎯 项目简介
            基于 LLM 的智能测试用例生成平台，从需求文档自动生成测试用例、接口文档、压测脚本。
            
            ### ⏱️ 核心价值
            - **效率提升** - 自动化生成测试用例，减少 60% 手工工作量
            - **AI 赋能** - 基于大语言模型，理解需求、生成用例、分析风险
            - **全流程覆盖** - 需求 → 模块 → 用例 → 接口 → 压测
            - **私有化部署** - Ollama 本地大模型，零 API 成本，数据安全
            """)

            st.markdown("""
            ### 🛠️ 技术栈
            | 分类 | 技术 | 说明 |
            |:---|:---|:---|
            | 前端 | Streamlit | AI 应用快速原型开发 |
            | 后端 | FastAPI + Uvicorn | 高性能异步 API |
            | AI 框架 | LangChain + LangGraph | Multi-Agent 编排 |
            | 大模型 | Ollama + Qwen3.5 | 本地部署，中文优化 |
            | 向量库 | Chroma | 轻量级向量数据库 |
            | 存储 | DuckDB / SQLite | 项目状态持久化 |
            """)

            st.markdown("""
            ### 📋 核心流程
            ```
            1. 创建项目
            2. 上传需求文档（PDF / Word / Markdown）
            3. AI 评估需求
            4. 需求确认 → 入库
            5. 模块拆分 → 入库
            6. 生成测试用例 → Excel 导出
            7. 接口设计 → Postman/Curl 导出
            8. Locust 压测脚本生成
            ```
            """)

        with col2:
            st.markdown("""
            ### 🚀 快速开始
            ```bash
            # 1. 克隆项目
            git clone <repo>
            
            # 2. 安装依赖
            pip install -r requirements.txt
            
            # 3. 启动 Ollama
            ollama serve &
            ollama pull qwen2.5:14b
            
            # 4. 启动后端
            uvicorn src.main:app
            
            # 5. 启动前端
            streamlit run src/frontend/app.py
            ```
            """)

    st.markdown("---")

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
                project_id = asyncio.run(ProjectService.create_project(project_name, project_description))
                if project_id:
                    st.success(f"✅ 项目创建成功！")
                    st.session_state.selected_project_id = project_id
                    st.rerun()
                else:
                    st.error("❌ 项目创建失败，请检查后端服务是否运行")
        elif submitted and not project_name:
            st.warning("⚠️ 请输入项目名称")

    st.markdown("---")

    # 项目列表区
    st.subheader("📁 我的项目")

    # 获取项目列表
    projects_data = asyncio.run(ProjectService.get_projects())

    if projects_data and projects_data.items:
        projects = projects_data.items
        total = projects_data.total

        st.info(f"共 {total} 个项目")

        # 表格展示
        cols = st.columns([3, 2, 2, 2, 1])
        headers = ["项目名称", "描述", "进度", "创建时间", "操作"]
        for col, header in zip(cols, headers):
            col.markdown(f"**{header}**")

        st.markdown("---")

        for project in projects:
            cols = st.columns([3, 2, 2, 2, 1])

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
                if st.button("进入", key=f"enter_{project.id}", type="primary"):
                    st.session_state.selected_project_id = project.id
                    st.switch_page("pages/project.py", query_params={"project_id": project.id})

        st.markdown("---")

    else:
        st.info("📭 暂无项目，请创建第一个项目开始使用")

    # 调试信息
    with st.expander("🔧 调试信息", expanded=False):
        st.write("Session State:", st.session_state)
        st.write("Query Params:", dict(st.query_params))


if __name__ == "__main__":
    app()
