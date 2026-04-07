from langchain.chat_models import init_chat_model

from src.config import settings

ollama_llm = init_chat_model(
    model=settings.ollama_model,
    model_provider="ollama",
    base_url=settings.ollama_api_host
)

minimax_llm = init_chat_model(
    model=settings.minimax_model,
    model_provider="anthropic",
    api_key=settings.minimax_api_key,
    base_url=settings.minimax_api_host,
)
