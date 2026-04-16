import sys
import streamlit as st
from pathlib import Path

# 将项目根目录（src 的上一级）加入 sys.path
root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

st.switch_page("pages/home.py")
