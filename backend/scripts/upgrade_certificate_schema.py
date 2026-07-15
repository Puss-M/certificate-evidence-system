from sqlalchemy import inspect, text

from app.db.session import engine


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    if column_name in _column_names(table_name):
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
    print(f"added {table_name}.{column_name}")


def main() -> None:
    if engine is None:
        print("DATABASE_URL is not configured; schema upgrade skipped")
        return

    if not _column_names("certificates"):
        print("certificates table does not exist, run scripts.create_tables first")
        return

    _add_column_if_missing(
        "certificates",
        "project_name",
        "project_name VARCHAR(200) NOT NULL DEFAULT '软件开发实训'",
    )
    _add_column_if_missing("certificates", "issue_time", "issue_time DATETIME NULL")
    _add_column_if_missing(
        "certificates",
        "previous_certificate_no",
        "previous_certificate_no VARCHAR(80) NULL",
    )
    _add_column_if_missing("certificates", "updated_at", "updated_at DATETIME NULL")

    if _column_names("certificate_batches"):
        # These fields were added after the initial batch table was created.
        # Keep them nullable so existing batches remain usable after upgrade.
        _add_column_if_missing(
            "certificate_batches",
            "project_name",
            "project_name VARCHAR(200) NULL",
        )
        _add_column_if_missing(
            "certificate_batches",
            "template_id",
            "template_id INT NULL",
        )
        _add_column_if_missing(
            "certificate_batches",
            "student_ids",
            "student_ids JSON NULL",
        )

    if _column_names("revocation_records"):
        _add_column_if_missing(
            "revocation_records",
            "action_type",
            "action_type VARCHAR(32) NOT NULL DEFAULT 'REVOKE'",
        )
        _add_column_if_missing(
            "revocation_records",
            "new_certificate_no",
            "new_certificate_no VARCHAR(80) NULL",
        )

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE certificates SET updated_at = created_at WHERE updated_at IS NULL")
        )

    print("certificate schema upgraded")


if __name__ == "__main__":
    main()
