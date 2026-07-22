# LangChain 与 LangGraph 团队分享稿设计

## 1. 目标

在 `doc/` 目录新增一份面向团队内部的中文知识分享稿，帮助同学在 45–60 分钟内：

- 理解 LangChain 与 LangGraph 的定位、关系和职责边界；
- 掌握使用 LangChain/LangGraph 开发 AI 应用的核心概念与标准流程；
- 能够沿本项目真实代码理解模型调用、状态编排、工具调用、子图、持久化和流式响应；
- 了解 LangChain/LangGraph 与 Dify 的主要差异，并能根据场景做初步选型。

最终文件路径为 `doc/langchain_and_langgraph_intro.md`。

## 2. 读者与表达方式

读者同时包括刚接触 LangChain/LangGraph 的 Python 开发者，以及需要维护本项目的开发者。

文档采用“概念主线 + 项目映射”的组织方式，并以一次用户对话的完整生命周期作为贯穿案例。每个重要概念尽量按以下顺序说明：

1. 概念是什么；
2. 它解决什么问题；
3. 一个最小示例；
4. 本项目中的代码位置与使用方式；
5. 实践注意事项。

内容是可直接用于团队分享的介绍稿，而非 API 词典或完整源码注释。代码片段只保留理解概念所需的部分，并标注源文件路径。

## 3. 文档结构

最终分享稿按以下章节组织：

1. 分享目标与阅读地图；
2. LangChain 是什么、解决什么问题；
3. LangGraph 是什么，以及它与 LangChain 的关系；
4. LangChain 核心概念：Chat Model、Message、Prompt、Tool、Tool Calling、Structured Output、Runnable 与配置；
5. LangGraph 核心概念：State、Node、Edge、条件路由、循环、Reducer、`Command`、`Send`、`ToolNode`、子图、Checkpoint 与 Streaming；
6. 标准开发流程：状态建模、节点与工具、路由、编译与持久化、调用、流式输出、测试与调试；
7. 本项目完整请求链路；
8. 本项目典型代码模式；
9. LangChain/LangGraph 与 Dify 的简要对比和选型建议；
10. 常见误区、实践建议与总结。

篇幅按照 45–60 分钟分享控制：基础概念约 15 分钟，LangGraph 开发模式约 15 分钟，本项目代码走读约 20 分钟，其余时间用于对比、总结和讨论。

## 4. 概念关系设计

文档首先建立分层心智模型：

- LangChain 提供模型、消息、Prompt、Tool、结构化输出等构建 AI 应用的基础组件；
- LangGraph 在这些组件之上提供有状态、可循环、可分支、可持久化的工作流编排；
- 本项目以 LangGraph 为流程主轴，并在节点和工具内部使用 LangChain 组件完成模型交互。

文档使用一张 Mermaid 分层关系图呈现这三个层次，避免把 LangChain 与 LangGraph 误解为相互替代的同类工具。

## 5. 项目代码映射

### 5.1 模型与基础组件

- `src/graphs/common/llms.py`：通过 `init_chat_model` 统一初始化不同模型供应商；
- `src/graphs/nodes.py`：消息构造、模型绑定工具和节点执行；
- `src/graphs/tools.py`：`@tool`、工具参数、`ToolRuntime` 与 `Command`；
- `src/graphs/common/utils/structured_output_utils.py`：工具调用和结构化输出的公共封装。

### 5.2 状态与流程编排

- `src/graphs/state.py`：`MessagesState`、业务状态字段和 `Annotated` reducer；
- `src/graphs/graph.py`：主 `StateGraph`、节点、边、条件路由、业务子图、SQLite Checkpoint 与编译；
- `src/graphs/routes.py`：根据消息、回滚标记与业务阶段选择下一节点；
- `src/graphs/common/reduce.py`：覆盖、去重和带优先级的状态归并；
- `src/graphs/common/base/graph.py`：通用“生成—审核—优化—再审核”循环和嵌套评审子图；
- `src/graphs/common/base/routes.py` 与 `src/graphs/common/utils/router_utils.py`：`Send` 并发分支及路由复用。

### 5.3 执行、持久化与输出

- `src/agents/main_agent.py`：图的懒加载、`thread_id`、状态读取和多模式异步流；
- `src/services/interface/conversation_message_interface_service.py`：消费 `values`、`custom`、`messages` 三类事件并转换为 SSE；
- `src/config.py`：Checkpoint 文件位置等运行配置。

## 6. 贯穿案例的数据流

文档用一张 Mermaid 流程图展示以下调用链：

```text
HTTP 请求
  → ConversationMessageInterfaceService
  → MainAgent.astream()
  → LangGraph 主图
  → 产品经理节点
  → ToolNode 或业务子图
  → Reducer 合并状态
  → SQLite Checkpoint 持久化
  → LangGraph 流事件
  → SSE 返回前端
```

讲解时分别指出：LangChain 组件在哪些步骤参与模型交互，LangGraph 在哪些步骤负责流程控制，以及项目业务代码如何连接二者。

## 7. LangChain/LangGraph 与 Dify 对比

对比保持简短、中立，聚焦开发方式和适用边界，不做脱离场景的优劣排名。比较维度包括：

- 产品定位：代码框架与可视化 AI 应用平台；
- 开发方式：Python 编排与 UI/DSL 编排；
- 灵活性、抽象边界和业务集成能力；
- 调试、测试、部署、运维和团队协作；
- 适用场景与混合使用方式。

选型结论为：快速验证、标准化工作流和低代码协作可优先考虑 Dify；复杂状态、动态路由、深度业务集成和工程可测试性通常更适合 LangGraph。两者可以组合使用，例如由 Dify 承载应用入口或通用平台能力，由 LangGraph 实现复杂领域流程。

## 8. 实践建议与常见误区

实践建议覆盖：

- 先定义状态，再实现节点、工具和路由；
- 节点保持单一职责，流程决策与业务执行分离；
- Tool 输入输出结构化，并明确状态更新范围；
- 并发分支必须设计对应 Reducer；
- 使用 `thread_id` 隔离会话和 Checkpoint；
- 明确消费不同 Streaming 模式的目的；
- 分层测试节点、路由、图和模型输出契约。

常见误区覆盖：

- 将 LangChain 和 LangGraph 当成同一层或相互替代；
- 将所有 Prompt、工具和流程控制塞入单个 Agent 节点；
- 忽略并发状态写入的归并语义；
- 误解 `Command.goto` 的作用范围；
- 滥用全局状态或遗漏 `thread_id`；
- 只验证模型回答，不验证状态迁移和结构化输出。

## 9. 错误处理、测试与调试内容

分享稿会说明本项目的异常边界和调试观察点：

- 节点内模型或工具异常如何记录并向上层传播；
- 服务层如何将异常转换为前端可消费的 SSE 消息；
- 日志中应观察当前节点、路由目标、项目 ID、事务 ID 和状态变更；
- 节点使用固定输入状态做单元测试；
- 路由使用参数化状态表测试；
- 图级测试使用可控模型或工具替身验证分支、循环和结束条件；
- 对结构化输出验证 schema，而不是只比较自然语言文本。

## 10. 资料与准确性要求

- 以仓库当前依赖版本为基准：LangChain `>=1.2.15`、LangGraph `>=1.1.6`；
- 涉及当前 API、产品定位和 Dify 能力的内容以 LangChain、LangGraph、Dify 官方资料为准；
- 不复制大段外部文档，采用自己的表述并在文末提供官方延伸阅读链接；
- 所有项目路径、符号名和代码片段都从当前仓库核对；
- Mermaid 图须保持 Markdown 可渲染，代码块须标注语言。

## 11. 验收标准

- 最终文件存在于 `doc/langchain_and_langgraph_intro.md`；
- 内容可支持一次 45–60 分钟的团队内部分享；
- 同时覆盖 LangChain/LangGraph 关系、核心概念、标准开发流程、本项目代码用法和 Dify 对比；
- 至少包含分层关系图和项目请求生命周期图；
- 每个主要项目案例均提供准确的文件路径；
- 不含 `TBD`、`TODO`、未解释术语或无法验证的绝对化结论；
- Markdown 结构、代码片段和 Mermaid 语法通过人工与静态检查。
