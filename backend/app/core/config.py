from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Certificate Evidence System API"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str | None = None
    jwt_secret: str | None = None
    public_verify_base_url: str = "http://127.0.0.1:5173/public/verify"

    # 测试链接入相关配置（P2加分项，只上链Merkle Root，见chain_service.py）。
    # 三个都不是必填——没配置的话chain_service会直接跳过上链、不报错，
    # 保证"链失败不影响主线"的降级要求（FISCO_BCOS与存证降级策略.md第5节）。
    chain_rpc_url: str | None = None
    chain_backend_private_key: str | None = None
    chain_contract_address: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
