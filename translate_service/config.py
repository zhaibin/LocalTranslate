from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    ollama_base_url: AnyHttpUrl = Field(
        default="http://127.0.0.1:11434",
        alias="OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(
        default="translategemma:latest",
        alias="OLLAMA_MODEL",
    )
    default_source_lang: str = Field(default="en", alias="DEFAULT_SOURCE_LANG")
    default_target_lang: str = Field(default="zh", alias="DEFAULT_TARGET_LANG")
    request_timeout_seconds: int = Field(
        default=120,
        alias="REQUEST_TIMEOUT_SECONDS",
        ge=1,
    )
