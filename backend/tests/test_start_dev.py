from scripts import start_dev


def test_start_dev_initializes_database_before_uvicorn(monkeypatch) -> None:
    events: list[tuple[str, object]] = []

    monkeypatch.setattr(
        start_dev.create_tables,
        "main",
        lambda: events.append(("create_tables", None)),
    )
    monkeypatch.setattr(
        start_dev.upgrade_certificate_schema,
        "main",
        lambda: events.append(("upgrade_schema", None)),
    )
    monkeypatch.setattr(
        start_dev.uvicorn,
        "run",
        lambda app, **kwargs: events.append(("uvicorn", (app, kwargs))),
    )

    start_dev.main()

    assert events == [
        ("create_tables", None),
        ("upgrade_schema", None),
        (
            "uvicorn",
            (
                "app.main:app",
                {
                    "host": "0.0.0.0",
                    "port": 8000,
                    "log_level": "info",
                    "access_log": True,
                },
            ),
        ),
    ]
