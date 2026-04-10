import os, sys
from pathlib import Path
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 基础目录
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    app_name: str = "ai-case-generator-demo"
    version: str = "0.1.0"

    # 日志配置
    log_path: Path = Field(default=BASE_DIR / "logs", description="Log Path")
    log_level: str = Field(default="INFO", description="Log Level")
    log_rotation_size: int = Field(default=100, description="Log Rotation Size MB")
    log_retention_days: int = Field(default=7, description="Log Retention Days")

    # Project file
    project_file_max_size: int = Field(default=10 * 1024 * 1024, description="Project File Max Size")
    project_file_total_max_size: int = Field(default=20 * 1024 * 1024, description="Project File Total Max Size")
    project_file_types: list[str] = Field(default=["pdf", "jpg", "png"], description="Project File Types")
    project_file_base_path: Path = Field(default=BASE_DIR / "data/project", description="Project File Base Path")

    # ClamAV
    clam_av_host: str = Field(default="http://localhost", description="Clam AV Host")
    clam_av_port: int = Field(default=3310, description="Clam AV Port")

    # LLM
    minimax_model: str = Field(default="MiniMax-M2.7", description="Minimax Model")
    minimax_api_key: str = Field(default="", description="Minimax API key")
    minimax_api_host: str = Field(default="https://api.minimaxi.com/anthropic", description="Minimax API Host")
    minimax_mcp_host: str = Field(default="https://api.minimaxi.com", description="Minimax MCP Host")
    minimax_max_tokens: int = Field(default=16384, description="Minimax Max Tokens")
    minimax_temperature: float = Field(default=1, description="Minimax Temperature")

    ollama_model: str = Field(default="qwen3.5:9b-q8_0", description="Ollama Model")
    ollama_api_host: str = Field(default="http://localhost:11434", description="Ollama API Host")
    ollama_max_tokens: int = Field(default=16384, description="Ollama Max Tokens")
    ollama_temperature: float = Field(default=0.3, description="Ollama Temperature")

    model_output_retry: int = Field(default=3, description="Model Output Retry")
    model_structured_output_retry: int = Field(default=3, description="Model Structured Output Retry")

    # Database
    milvus_project_file_collection_name: str = Field(
        default="project_file",
        description="Milvus Project File Collection Name"
    )
    milvus_project_context_collection_name: str = Field(
        default="project_context",
        description="Milvus Project Context Collection Name"
    )
    milvus_search_sparse_weight: float = Field(
        default=0.5,
        description="Milvus Search Sparse Weight"
    )
    milvus_search_dense_weight: float = Field(
        default=0.5,
        description="Milvus Search Dense Weight"
    )
    milvus_database_path: Path = Field(
        default=BASE_DIR / "data/db/vector_store.db",
        description="Milvus Database Path"
    )
    langgraph_sqlite_checkpoint_path: Path = Field(
        default=BASE_DIR / "data/db/checkpoint.db",
        description="LangGraph SQLite Checkpoint Path"
    )
    business_database_path: Path = Field(
        default=BASE_DIR / "data/db/business.db",
        description="Business Database Path"
    )

    # Embedding Model
    embedding_model_name: str = Field(
        default="gpahal/bge-m3-onnx-int8",
        description="Embedding Model Name"
    )
    embedding_model_local_path: Path | None = Field(
        default=BASE_DIR / "models/bge-m3-onnx-int8",
        description="Embedding Model Local Path"
    )


# 日志初始化配置
def setup_logging(setting: Settings) -> None:
    logger.remove()
    log_path = setting.log_path
    log_path.mkdir(exist_ok=True)

    # 打印配置
    logger.add(sink=sys.stdout, level=setting.log_level)
    logger.add(
        sink=log_path / "app.log",
        level=setting.log_level,
        rotation=f"{setting.log_rotation_size} MB",
        retention=f"{setting.log_retention_days} days",
        compression="zip",
        enqueue=True,
        serialize=True
    )


# 设置 PICCOLO_CONF
os.environ.setdefault("PICCOLO_CONF", "src.models.base")

# 设置 HF 模型离线调用
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

settings = Settings()
