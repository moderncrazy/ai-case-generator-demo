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
    log_level: str = Field(default="INFO", description="日志级别")
    log_rotation_size: int = Field(default=100, description="日志轮换大小 MB")
    log_retention_days: int = Field(default=7, description="日志保留天数")


# 日志初始化配置
def setup_logging(setting: Settings) -> None:
    logger.remove()
    log_path = BASE_DIR / "logs"
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


settings = Settings()
