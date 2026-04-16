import uuid
import streamlit as st
from streamlit import _DeltaGenerator
import streamlit.components.v1 as components

from src.frontend.service.project_service import ProjectService
from src.frontend.enums.conversation_role import ConversationRole
from src.frontend.schemas.conversation_message import ConversationMessage, ConversationMessageResponse

CHAT_POPOVER_KEY = "chat_popover"
CHAT_CONTAINER_KEY = "chat_container"
CHAT_CONTEXT_CONTAINER_KEY = "chat_context_container"
CHAT_INPUT_KEY = "chat_input"

MESSAGE_STATUS_WIDTH = 250
MESSAGE_STATUS_SUCCEED_LABEL = "加载完成"
MESSAGE_STATUS_ERROR_LABEL = "加载失败，请重试"
MESSAGE_STATUS_LOADING_LABEL = "加载中，请稍后..."


def config_style():
    """配置样式"""
    st.html(
        f"""
        <style>
            /* 聊天按钮 */
            .st-key-{CHAT_POPOVER_KEY} button {{
                position: fixed;
                bottom: 3.5rem;
                right: 3.5rem;
                min-width: 3.5rem;
                min-height: 3.5rem;
                padding: 0.875rem;
                box-shadow: rgba(0, 0, 0, 0.16) 0px 4px 16px;
                z-index: 999;
                border-radius: 1rem;
                max-width: fit-content;
            }}
            
            /* 聊天框 */
            .st-key-{CHAT_CONTAINER_KEY} {{
                position: absolute;
                right: 20vw;
                z-index: 999;
                border-radius: 1rem;
                max-height: fit-content;
                max-width: fit-content;
            }}
            
            div[data-testid="stPopoverBody"]:has(.st-key-{CHAT_INPUT_KEY}) {{
                width: 40rem !important;
                height: 90vh !important;
                max-height: 90vh !important;
                margin-top: 5vh !important;
                margin-bottom: 5vh !important;
            }}
            
            div[data-testid="stVerticalBlock"]:has(.st-key-{CHAT_INPUT_KEY}) {{
                display: block !important;
            }}
            
            /* 输入框 */
            .st-key-{CHAT_INPUT_KEY} div[data-testid="stChatInput"] {{
                bottom: 0px !important;
                position: fixed !important;
                width: 90% !important;
                text-align: center !important;
                margin:10px !important;
                margin-bottom: 20px !important;
            }}
            
            .st-key-{CHAT_INPUT_KEY} div[data-baseweb="base-input"] {{
                max-height: 10vh !important;
            }}
            
            .st-key-{CHAT_INPUT_KEY} textarea {{
                max-height: 100% !important;
            }}

            /* 聊天上下文框 */
            div[data-testid="stPopoverBody"] .st-key-{CHAT_CONTEXT_CONTAINER_KEY} {{
                max-height: 76vh !important;
                overflow-y: auto;
                overflow-x: hidden;
            
            /* 选中用户消息的容器 (Streamlit 1.30+ 结构) */
            [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
                flex-direction: row-reverse; /* 头像和气泡位置互换 */
                text-align: right;          /* 文字右对齐 */
                padding-right: 1rem;
                background-color: rgba(240, 242, 246, 0.5);
            }}

            /* 针对用户消息气泡的微调 */
            [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {{
                # border-style: solid;
                # border-width: 1px;
                # border-color: rgba(49, 51, 63, 0.2);
                # border-radius: 0.5rem;
                # padding: 0.4rem 0.75rem;
                # background-color: rgba(240, 242, 246, 0.5);
            }}

        </style>
        """,
    )


def scroll_to_bottom():
    # 这段 JS 会找到所有带滚动条的容器并推到底部
    # 或者你可以通过 CSS 类名精确指定
    components.html(
        f"""
        <script>
            const _force_rerun = "{str(uuid.uuid4())}";
            var scrollInterval = setInterval(function() {{
                var chatContainers = window.parent.document.querySelectorAll('[data-testid="stLayoutWrapper"] > div');
                chatContainers.forEach(function(container) {{
                    container.scrollTop = container.scrollHeight;
                }});
            }}, 0);
            setTimeout(function() {{ clearInterval(scrollInterval); }}, 0);
        </script>
        """,
        height=0,
    )


async def load_history(project_id: str):
    if not st.session_state.get("chat_messages"):
        # 获取对话历史
        message_data = await ProjectService.get_conversation_messages(project_id)
        if message_data and message_data.items:
            st.session_state["chat_messages"] = message_data.items
        else:
            st.session_state["chat_messages"] = []


@st.fragment
def show_message(chat_context_container: _DeltaGenerator):
    # if chat_context_container.button("加载更多历史消息"):
    #     print("加载更多历史消息")
    # 显示消息
    chat_message = None
    message_status = None
    if st.session_state["chat_messages"]:
        for msg in st.session_state["chat_messages"]:
            role = msg.role
            content = msg.content
            # 人类消息直接展示
            if role == ConversationRole.USER:
                chat_context_container.chat_message("我", avatar="user").markdown(content)
                if message_status:
                    message_status.update(label=MESSAGE_STATUS_ERROR_LABEL, expanded=False, state="error")
                    chat_message = None
                    message_status = None
            # 系统消息合并至 assistant_message_group
            elif role == ConversationRole.SYSTEM:
                if message_status:
                    message_status.markdown(content)
                else:
                    chat_message = chat_context_container.chat_message("AI", avatar="assistant")
                    message_status = chat_message.status(MESSAGE_STATUS_LOADING_LABEL, expanded=True, state="running",
                                                         width=MESSAGE_STATUS_WIDTH)
                    message_status.markdown(content)
            else:
                if message_status:
                    message_status.update(label=MESSAGE_STATUS_SUCCEED_LABEL, expanded=False, state="complete")
                    chat_message.markdown(content)
                    chat_message = None
                    message_status = None
                else:
                    chat_context_container.chat_message("AI", avatar="assistant").markdown(content)
        if message_status:
            message_status.update(label=MESSAGE_STATUS_ERROR_LABEL, expanded=False, state="error")
        scroll_to_bottom()
    else:
        st.info("暂无对话记录，开始你的第一次对话吧！")


async def chat_frame(project_id: str) -> None:
    """固定在右侧的聊天窗口"""

    # UI 组件
    chat_container = st.container(key=CHAT_CONTAINER_KEY)
    with chat_container:
        chat_popover = chat_container.popover(":material/chat: Chat", key=CHAT_POPOVER_KEY)
        with chat_popover:
            chat_context_container = chat_popover.container(key=CHAT_CONTEXT_CONTAINER_KEY)
            with chat_context_container:
                # 配置样式
                config_style()

                await load_history(project_id)

                show_message(chat_context_container)

                # 对话输入
            prompt = st.chat_input(
                "输入你的问题或需求...",
                accept_file=True,
                file_type=st.secrets["server"]["upload_file_types"],
                max_upload_size=st.secrets["server"]["upload_file_max_size"],
                key=CHAT_INPUT_KEY
            )
            if prompt:
                st.session_state["chat_messages"].append(ConversationMessage(
                    id=str(uuid.uuid4()),
                    role=ConversationRole.USER,
                    content=prompt.text
                ))
                chat_context_container.chat_message("我", avatar="user").markdown(prompt.text)
                scroll_to_bottom()
                chat_message = chat_context_container.chat_message("AI", avatar="assistant")
                message_status = chat_message.status(MESSAGE_STATUS_LOADING_LABEL, expanded=True, state="running",
                                                     width=MESSAGE_STATUS_WIDTH)
                try:
                    async for response in ProjectService.project_discuss(project_id, prompt.text, prompt.files):
                        st.session_state["chat_messages"].append(response.message)
                        st.session_state["context"] = response.context
                        print(st.session_state["context"])
                        if response.message.role == ConversationRole.SYSTEM:
                            message_status.markdown(response.message.content)
                        else:
                            message_status.update(label=MESSAGE_STATUS_SUCCEED_LABEL, expanded=False, state="complete")
                            chat_message.markdown(response.message.content)
                        scroll_to_bottom()
                except Exception as e:
                    print(f"对话接口异常:{str(e)}")
                    message_status.update(label=MESSAGE_STATUS_ERROR_LABEL, expanded=False, state="error")
