"""全局配置：从环境变量读取（与技术方案 §11.3 对齐）。

支持从 `.env` 文件加载（开发用），生产环境通过 systemd `EnvironmentFile=` 注入。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。所有字段对应技术方案 §11.3 关键环境变量表。"""

    # === LLM ===
    deepseek_api_key: str = Field(default="", description="DeepSeek API Key（必填用于联调）")
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek 模型名；首版统一 deepseek-chat（技术方案 §3）",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API base URL",
    )

    # === 数据 ===
    gcp_data_dir: str = Field(
        default="./data",
        description="JSON 数据根目录；运行时所有场景包落盘于此",
    )

    # === CORS ===
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://43.155.205.89",
        description="允许的前端访问源，逗号分隔",
    )

    # === 日志 ===
    gcp_log_level: str = Field(default="INFO", description="日志级别")

    # === 对话上下文 ===
    dialogue_history_limit: int = Field(
        default=20,
        description="单次 LLM 调用读取的最大历史回合数（技术方案 §10.2）",
    )

    # === 服务元信息 ===
    service_name: str = Field(default="gcp-backend", description="服务标识符")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def data_dir_path(self) -> Path:
        return Path(self.gcp_data_dir).resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


_settings: Settings | None = None


def get_settings() -> Settings:
    """单例。首次调用时从环境变量加载。"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
