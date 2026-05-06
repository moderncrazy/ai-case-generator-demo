import re
import streamlit as st

from typing import Literal


def mermaid(mermaid_code: str, height: int | Literal["stretch", "content"] = "content"):
    """渲染 Mermaid 图表"""
    html = f"""
    <div class="mermaid">{mermaid_code}</div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true }});
    </script>
    """
    st.iframe(html, height=height)


def render_markdown(content: str):
    """分割渲染 Markdown + Mermaid"""
    # 用正则分割：markdown 文本 和 mermaid 代码块
    parts = re.split(r'(```mermaid\s*\n[\s\S]*?\n\s*```)', content)

    for part in parts:
        if part.strip().startswith('```mermaid'):
            # 提取 mermaid 代码
            mermaid_code = re.search(r'```mermaid\s*\n([\s\S]*?)\n\s*```', part)
            if mermaid_code:
                mermaid(mermaid_code.group(1))
        elif part.strip():
            # 普通 markdown 文本
            st.markdown(part)
