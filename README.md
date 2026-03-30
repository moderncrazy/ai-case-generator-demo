# AI Case Generator Demo

> 基于 LLM 的智能测试用例生成平台，从需求文档自动生成测试用例、接口文档、压测脚本

---

## 🎯 项目简介

本项目是一个 AI 驱动的测试开发辅助工具，通过 LangGraph Multi-Agent 架构，自动完成从需求分析到测试用例生成的完整流程。

### 核心价值

- ⏱️ **效率提升** - 自动化生成测试用例，减少 60% 手工工作量
- 🤖 **AI 赋能** - 基于大语言模型，理解需求、生成用例、分析风险
- 📊 **全流程覆盖** - 需求 → 模块 → 用例 → 接口 → 压测
- 🔒 **私有化部署** - Ollama 本地大模型，零 API 成本，数据安全

---

## 📋 核心流程

```
1️⃣ 创建项目
        ↓
2️⃣ 上传需求文档（PDF / Word / Markdown）
        ↓
3️⃣ AI 评估需求
   ├── 需求合理性分析
   ├── 风险识别
   └── 不明确点标注
        ↓
4️⃣ 需求确认（Markdown 导出）
        ↓
5️⃣ 需求入库（向量数据库）
        ↓
6️⃣ 模块拆分（用户确认 + Markdown 导出）
        ↓
7️⃣ 模块入库
        ↓
8️⃣ 生成测试用例（用例分级 + Excel 导出）
        ↓
9️⃣ 用例入库
        ↓
🔟 接口设计（Postman/Curl 脚本导出）
        ↓
1️⃣1️⃣ 接口入库
        ↓
1️⃣2️⃣ Locust 压测脚本生成
```

**中途保存机制**：支持断点续传，随时保存、随时继续

---

## 🛠️ 技术栈

|    分类     | 技术                    | 说明             |
|:---------:|:----------------------|:---------------|
|  **语言**   | Python 3.11+          | 全栈 Python 开发   |
|  **前端**   | Streamlit             | AI 应用快速原型开发    |
|  **后端**   | FastAPI + Uvicorn     | 高性能异步 API      |
| **AI 框架** | LangChain + LangGraph | Multi-Agent 编排 |
|  **大模型**  | Ollama + Qwen3.5      | 本地部署，中文优化      |
|  **向量库**  | Chroma                | 轻量级向量数据库       |
|  **存储**   | DuckDB / SQLite       | 项目状态持久化        |
| **文档解析**  | PyMuPDF + python-docx | PDF/Word 解析    |

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- macOS / Linux / Windows
- 内存 8GB+（推荐 16GB）
- Ollama（本地大模型）

### 安装步骤

```bash
# 1. 克隆项目
git clone https://gitlab.s.hi-hub.xyz:8443/moderncrazy/ai-case-generator-demo.git
cd ai-case-generator-demo

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动 Ollama（后台运行）
ollama serve &

# 5. 下载 Qwen2.5 模型
ollama pull qwen2.5:14b

# 6. 启动应用
streamlit run src/streamlit_app.py
```

### Docker 部署（可选）

```bash
docker-compose up -d
```

---

## 📁 项目结构

```
ai-case-generator-demo/
├── README.md
├── requirements.txt
├── docker-compose.yml
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口
│   ├── streamlit_app.py        # Streamlit 前端
│   │
│   ├── agents/                 # Agent 逻辑
│   │   ├── requirement_agent.py    # 需求分析 Agent
│   │   ├── module_agent.py           # 模块拆分 Agent
│   │   └── testcase_agent.py        # 用例生成 Agent
│   │
│   ├── graph/                  # LangGraph 编排
│   │   └── workflow_graph.py        # 状态机定义
│   │
│   ├── services/               # 业务服务
│   │   ├── document_parser.py       # 文档解析
│   │   ├── knowledge_base.py        # 向量知识库
│   │   ├── project_manager.py       # 项目管理
│   │   └── exporter.py              # 导出功能
│   │
│   ├── models/                 # 数据模型
│   │   └── schemas.py                # Pydantic 模型
│   │
│   └── config.py               # 配置管理
│
├── data/                       # 数据目录
│   ├── db/                     # SQLite 数据库
│   ├── chroma/                 # 向量数据库
│   └── exports/                # 导出文件
│
└── templates/                  # 模板文件
    ├── requirement.md
    ├── module.md
    └── testcase.xlsx
```

---

## 🎓 学习路线

|   阶段    | 内容                                  | 预计时间 |
|:-------:|:------------------------------------|:----:|
|  Day 1  | 环境搭建 + Ollama + LangChain 入门        |  1天  |
|  Day 2  | LangChain 核心（Prompt / Chain / Tool） |  1天  |
|  Day 3  | LangGraph Agent 编排                  |  1天  |
|  Day 4  | Streamlit 前端开发                      |  1天  |
|  Day 5  | Chroma 向量数据库 + RAG                  |  1天  |
| Day 6-7 | 全链路整合 + Bug 修复                      |  2天  |

---

## 🎯 核心亮点（简历展示）

- ✅ **Multi-Agent 协作** - LangGraph StateGraph 编排多 Agent 协作
- ✅ **RAG 知识增强** - Chroma 向量库存储测试用例模板
- ✅ **本地大模型** - Ollama + Qwen2.5，零 API 成本
- ✅ **全流程自动化** - 需求到压测脚本一键生成

---

## 📝 License

MIT License

---

## 👤 Author

[Your Name](https://github.com/yourusername)
