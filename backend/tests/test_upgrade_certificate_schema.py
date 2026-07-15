from sqlalchemy import create_engine, inspect, text

from scripts import upgrade_certificate_schema as upgrader


def test_upgrade_adds_missing_batch_fields_without_recreating_tables(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE certificates (certificate_id INTEGER, created_at DATETIME)")
        )
        connection.execute(
            text(
                "CREATE TABLE certificate_batches "
                "(batch_id INTEGER, batch_no VARCHAR(64), batch_name VARCHAR(128), "
                "status VARCHAR(32), created_at DATETIME)"
            )
        )
        connection.execute(
            text("CREATE TABLE revocation_records (certificate_id INTEGER, reason VARCHAR(255))")
        )

    monkeypatch.setattr(upgrader, "engine", engine)
    upgrader.main()

    inspector = inspect(engine)
    batch_columns = {column["name"] for column in inspector.get_columns("certificate_batches")}
    certificate_columns = {column["name"] for column in inspector.get_columns("certificates")}
    revocation_columns = {column["name"] for column in inspector.get_columns("revocation_records")}

    assert {"project_name", "template_id", "student_ids"} <= batch_columns
    assert {"project_name", "issue_time", "previous_certificate_no", "updated_at"} <= certificate_columns
    assert {"action_type", "new_certificate_no"} <= revocation_columns
