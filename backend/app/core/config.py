from functools import lru_cache
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Certificate Evidence System API"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str | None = None
    jwt_secret: str | None = None
    auth_access_token_minutes: int = 120
    enable_demo_auth: bool = False
    public_verify_base_url: str = "http://127.0.0.1:5173/public/verify"
    enable_demo_data: bool = False
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        for raw_origin in self.cors_allowed_origins.split(","):
            origin = raw_origin.strip().rstrip("/")
            if not origin:
                continue
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or "*" in parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"invalid CORS origin: {origin}")
            origins.append(origin)
        return origins

    # 测试链接入相关配置（P2加分项，只上链Merkle Root，见chain_service.py）。
    # 三个都不是必填——没配置的话chain_service会直接跳过上链、不报错，
    # 保证"链失败不影响主线"的降级要求（FISCO_BCOS与存证降级策略.md第5节）。
    chain_rpc_url: str | None = None
    chain_backend_private_key: str | None = None
    chain_contract_address: str | None = None
    chain_expected_chain_ids: str = "1337,31337"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
