from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: AnyHttpUrl = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(
        default="translategemma:latest",
        validation_alias="OLLAMA_MODEL",
    )
    default_source_lang: str = Field(default="en", validation_alias="DEFAULT_SOURCE_LANG")
    default_target_lang: str = Field(default="zh", validation_alias="DEFAULT_TARGET_LANG")
    request_timeout_seconds: int = Field(
        default=120,
        validation_alias="REQUEST_TIMEOUT_SECONDS",
        ge=1,
    )
