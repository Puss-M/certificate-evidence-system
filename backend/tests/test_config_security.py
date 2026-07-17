import pytest

from app.core.config import Settings


def test_cors_origins_accept_explicit_http_origins() -> None:
    settings = Settings(
        _env_file=None,
        cors_allowed_origins="http://localhost:5173,https://example.test",
    )

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://example.test",
    ]


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "http://*.example.test",
        "file:///tmp/app",
        "http://user:password@example.test",
        "https://example.test/path",
    ],
)
def test_cors_origins_reject_unsafe_values(origin: str) -> None:
    settings = Settings(_env_file=None, cors_allowed_origins=origin)

    with pytest.raises(ValueError, match="invalid CORS origin"):
        settings.cors_origins
