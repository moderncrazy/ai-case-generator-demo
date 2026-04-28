import time
import uuid
import traceback
import streamlit as st
import streamlit.components.v1 as components

from enum import StrEnum
from collections.abc import Callable
from streamlit import _DeltaGenerator

from src.frontend.enums.conversation_message_status import ConversationMessageStatus
from src.frontend.utils import utils
from src.frontend import constant as const
from src.frontend.service.project_service import ProjectService
from src.frontend.enums.conversation_role import ConversationRole
from src.frontend.schemas.conversation_message import ConversationMessage
from src.frontend.enums.conversation_message_type import ConversationMessageType

CHAT_INPUT_KEY = "chat_input"
CHAT_CONTEXT_CONTAINER_KEY = "chat_context_container"

MESSAGE_STATUS_WIDTH = 480
MESSAGE_STATUS_SUCCEED_LABEL = "加载完成"
MESSAGE_STATUS_ERROR_LABEL = "加载失败，请重试"
MESSAGE_STATUS_LOADING_LABEL = "加载中，请稍后..."

STATE_CHAT_MESSAGES = "chat_messages"
STATE_CHAT_PROJECT_ID = "chat_project_id"
STATE_CHAT_INPUT_DISABLED = "chat_input_disabled"

CONST_CUSTOM_MESSAGES_KEY = "custom_messages"


class OnChangeEvent(StrEnum):
    PROJECT_DOC_UPDATE = "project_doc_update"


def config_style():
    """配置样式"""
    st.html(
        f"""
        <style>
            /* 聊天伸缩框 */
            .st-key-{const.CHAT_EXPANDER_KEY} {{
                position: fixed;
                bottom: 2rem;
                right: 2rem;
                min-width: 3.5rem;
                min-height: 3.5rem;
                padding: 0.875rem;
                box-shadow: rgba(0, 0, 0, 0.16) 0px 4px 16px;
                z-index: 999999;
                border-radius: 1rem;
                max-width: fit-content;
                background-color: #fff;
            }}
            
            .st-key-{const.CHAT_EXPANDER_KEY} div[data-testid="stExpanderDetails"] {{
                height: 88vh !important;
                max-height: 88vh !important;
                width: 40rem !important;
                max-width: 40rem !important;
                overflow-y: auto;
                overflow-x: hidden;
            }}
            
            /* 聊天上下文框 */
            .st-key-{CHAT_CONTEXT_CONTAINER_KEY} {{
                max-height: 70vh !important;
                overflow-y: auto;
                overflow-x: hidden;
            }}
            
            /* 选中用户消息的容器 */
            [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
                flex-direction: row-reverse; /* 头像和气泡位置互换 */
                text-align: right;          /* 文字右对齐 */
                padding-right: 1rem;
                background-color: rgba(240, 242, 246, 0.5);
            }}
            
            /* 状态提示框 */
            .st-key-{CHAT_CONTEXT_CONTAINER_KEY} div[data-testid="stExpanderDetails"] {{
                height: auto !important;
                max-height: 30rem !important;
                width: auto !important;
                overflow-y: auto;
                overflow-x: hidden;
            }}
            
            /* 输入框 */
            .st-key-{CHAT_INPUT_KEY} {{
            }}

            .st-key-{CHAT_INPUT_KEY} div[data-baseweb="base-input"] {{
                max-height: 6vh !important;
                overflow-y: auto;
                overflow-x: hidden;
            }}

            .st-key-{CHAT_INPUT_KEY} textarea {{
                max-height: 100% !important;
            }}
            
            /* 聊天框字体 */
            .st-key-{const.CHAT_EXPANDER_KEY} h1 {{
                font-size: 1.5rem;
            }}
            .st-key-{const.CHAT_EXPANDER_KEY} h2 {{
                font-size: 1.25rem;
            }}
            .st-key-{const.CHAT_EXPANDER_KEY} h3 {{
                font-size: 1.125rem;
            }}
            .st-key-{const.CHAT_EXPANDER_KEY} h4 {{
                font-size: 1rem;
            }}
            .st-key-{const.CHAT_EXPANDER_KEY} h5 {{
                font-size: 0.875rem;
            }}
            .st-key-{const.CHAT_EXPANDER_KEY} h6 {{
                font-size: 0.75rem;
            }}
            
            /* 隐藏注入的 html 组件，用于自动滚动 */
            .st-key-{const.CHAT_EXPANDER_KEY} div[height="0px"][data-testid="stElementContainer"] {{
                display: none !important;
            }}

        </style>
        """,
    )


def scroll_to_bottom():
    """滚动聊天框和状态栏到底部"""
    components.html(
        f"""
        <script>
            const _force_rerun = "{str(uuid.uuid4())}";
            var scrollInterval = setInterval(function() {{
                console.log(_force_rerun);
                var chatContainers = window.parent.document.querySelectorAll('.st-key-{CHAT_CONTEXT_CONTAINER_KEY}[data-testid="stVerticalBlock"]');
                chatContainers.forEach(function(container) {{
                     container.scrollTop = container.scrollHeight;
                }});
                
                var chatExpanderDetails = window.parent.document.querySelectorAll('[data-testid="stExpanderDetails"]');
                chatExpanderDetails.forEach(function(container) {{
                    container.scrollTop = container.scrollHeight;
                }});
            }}, 0);
            setTimeout(function() {{ clearInterval(scrollInterval); }}, 0);
        </script>
        """,
        height=0,
    )


def load_history(project_id: str):
    if project_id != st.session_state.get(STATE_CHAT_PROJECT_ID) or not st.session_state.get(STATE_CHAT_MESSAGES):
        # 设置项目Id
        st.session_state[STATE_CHAT_PROJECT_ID] = project_id
        # 获取对话历史
        message_data = ProjectService.get_conversation_messages(project_id)
        if message_data and message_data.items:
            st.session_state[STATE_CHAT_MESSAGES] = message_data.items
        else:
            st.session_state[STATE_CHAT_MESSAGES] = []


def show_message(chat_context_container: _DeltaGenerator):
    # if chat_context_container.button("加载更多历史消息"):
    #     print("加载更多历史消息")
    # 显示消息
    if st.session_state[STATE_CHAT_MESSAGES]:
        for msg in st.session_state[STATE_CHAT_MESSAGES]:
            role = msg.role
            content = msg.content
            metadata = msg.metadata
            # 人类消息
            if role == ConversationRole.USER:
                chat_context_container.chat_message("我", avatar="user").markdown(content)
            # 系统和AI消息
            else:
                chat_message = chat_context_container.chat_message("AI", avatar="assistant")
                # 若存在自定义消息 则放在 message_status
                if metadata.get(CONST_CUSTOM_MESSAGES_KEY):
                    # 根据 metadata.status 判断消息状态
                    message_status_state = "complete"
                    message_status_label = MESSAGE_STATUS_SUCCEED_LABEL
                    if (ConversationMessageStatus.FAILED.value
                            == metadata.get("status", ConversationMessageStatus.FAILED.value)):
                        message_status_state = "error"
                        message_status_label = MESSAGE_STATUS_ERROR_LABEL
                    message_status = chat_message.status(
                        message_status_label,
                        expanded=False,
                        state=message_status_state,
                        width=MESSAGE_STATUS_WIDTH
                    )
                    for custom_msg in metadata[CONST_CUSTOM_MESSAGES_KEY]:
                        message_status.markdown(custom_msg)
                chat_message.markdown(content)
        scroll_to_bottom()
    else:
        st.info("暂无对话记录，开始你的第一次对话吧！")


def disable_chat_expander():
    st.html(
        f"""
        <style>
            a {{pointer-events: none;}}
            button {{pointer-events: none;}}
            .st-key-{const.CHAT_EXPANDER_KEY} details summary {{pointer-events: none;}}
            .st-key-{CHAT_CONTEXT_CONTAINER_KEY} details summary {{pointer-events: auto;}}
        </style>
        """
    )


def enable_chat_expander():
    st.html(f"<style>.st-key-{const.CHAT_EXPANDER_KEY} details summary {{pointer-events: auto;}}</style>")


def chat_input_on_submit():
    # 提交后禁用聊天窗口
    st.session_state[STATE_CHAT_INPUT_DISABLED] = True
    # 禁用折叠窗口 和 按钮
    disable_chat_expander()


def chat_frame(project_id: str, on_change: Callable[[OnChangeEvent, dict], None] | None = None) -> None:
    """固定在右侧的聊天窗口"""

    # UI 组件
    chat_expander = st.expander(":material/chat: Chat", key=const.CHAT_EXPANDER_KEY,
                                on_change=lambda: print(st.session_state[const.CHAT_EXPANDER_KEY]))

    # 默认不禁用聊天
    if st.session_state.get(STATE_CHAT_INPUT_DISABLED) is None:
        st.session_state[STATE_CHAT_INPUT_DISABLED] = False

    with chat_expander:
        chat_context_container = chat_expander.container(key=CHAT_CONTEXT_CONTAINER_KEY)
        with chat_context_container:
            # 配置样式
            config_style()

            load_history(project_id)

            show_message(chat_context_container)

        st.space("stretch")

        # 对话输入
        prompt = st.chat_input(
            "输入你的问题或需求...（Shift+Enter 换行）",
            accept_file=True,
            disabled=st.session_state[STATE_CHAT_INPUT_DISABLED],
            file_type=st.secrets["server"]["upload_file_types"],
            max_upload_size=st.secrets["server"]["upload_file_max_size"],
            key=CHAT_INPUT_KEY,
            on_submit=chat_input_on_submit
        )

        if prompt:
            # 记录消息
            st.session_state[STATE_CHAT_MESSAGES].append(ConversationMessage(
                id=str(uuid.uuid4()),
                role=ConversationRole.USER,
                type=ConversationMessageType.MESSAGE,
                content=prompt.text
            ))
            chat_context_container.chat_message("我", avatar="user").markdown(prompt.text)
            scroll_to_bottom()
            chat_message = chat_context_container.chat_message("AI", avatar="assistant")
            message_status = chat_message.status(MESSAGE_STATUS_LOADING_LABEL, expanded=True, state="running",
                                                 width=MESSAGE_STATUS_WIDTH)

            # 发起对话
            def project_discuss():
                try:
                    # 当前流说话的角色
                    stream_role = None
                    user_id = utils.get_user_id()
                    for response in ProjectService.project_discuss(
                            project_id, user_id, prompt.text, prompt.files):
                        # 如果存在上下文则更新
                        if response.context:
                            st.session_state["context"] = response.context
                        # 若是 end 消息 关闭等待栏 否则正常显示
                        if response.message.type == ConversationMessageType.END:
                            message_status.update(
                                label=MESSAGE_STATUS_SUCCEED_LABEL, expanded=False, state="complete")
                        # 阶段消息 展示在loading 栏中
                        elif response.message.type == ConversationMessageType.STAGE:
                            message_status.update(label=response.message.content, expanded=True, state="running")
                        # 实体消息正式展示
                        elif response.message.type == ConversationMessageType.MESSAGE:
                            st.session_state[STATE_CHAT_MESSAGES].append(response.message)
                            chat_message.markdown(response.message.content)
                        # 流式消息拼接展示
                        elif response.message.type == ConversationMessageType.STREAM:
                            # 如果AI角色有变化 则显示说话人 否则直接输出
                            if not stream_role or stream_role != response.message.assistant_role:
                                stream_role = response.message.assistant_role
                                yield f"\n\n**{stream_role.get_name_zh()}:** {response.message.content}"
                            else:
                                yield response.message.content
                        # 通知消息 弹出通知
                        elif response.message.type == ConversationMessageType.NOTIFY:
                            st.toast(response.message.content, icon="🎉", duration="long")
                        elif response.message.type == ConversationMessageType.DOC_UPDATE:
                            # 如果存在回调方法 则执行
                            if on_change:
                                on_change(OnChangeEvent.PROJECT_DOC_UPDATE, {"content": response.message.content})
                        scroll_to_bottom()
                except Exception as e:
                    print(f"对话接口异常:{traceback.format_exc()}")
                    message_status.update(label=MESSAGE_STATUS_ERROR_LABEL, expanded=False, state="error")

            # 为流消息准备的markdown
            stream_content = message_status.write_stream(project_discuss)
            if stream_content:
                # 获取最后一条消息 将流式消息内容插入 custom_messages
                latest_msg = st.session_state[STATE_CHAT_MESSAGES][-1]
                if latest_msg.metadata.get(CONST_CUSTOM_MESSAGES_KEY):
                    latest_msg.metadata[CONST_CUSTOM_MESSAGES_KEY].append("---")
                    latest_msg.metadata[CONST_CUSTOM_MESSAGES_KEY].append(stream_content)
                else:
                    latest_msg.metadata[CONST_CUSTOM_MESSAGES_KEY] = [stream_content]
            # 消息接收完毕 解除禁用
            st.session_state[STATE_CHAT_INPUT_DISABLED] = False
            st.rerun()
