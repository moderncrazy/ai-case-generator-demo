from langchain.chat_models import init_chat_model

from src.config import settings

ollama_llm = init_chat_model(
    model=settings.ollama_model,
    model_provider="ollama",
    base_url=settings.ollama_api_host,
    max_tokens=settings.ollama_max_tokens,
    temperature=settings.ollama_temperature,
    max_retries=settings.model_output_retry,
)

minimax_llm = init_chat_model(
    model=settings.minimax_model,
    model_provider="anthropic",
    api_key=settings.minimax_api_key,
    base_url=settings.minimax_api_host,
    max_tokens=settings.minimax_max_tokens,
    temperature=settings.minimax_temperature,
    thinking={"type": "adaptive"},
)

default_model = minimax_llm