import uvicorn

from scripts import create_tables, upgrade_certificate_schema


def main() -> None:
    """Initialize an existing local database safely before serving requests."""
    create_tables.main()
    upgrade_certificate_schema.main()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
