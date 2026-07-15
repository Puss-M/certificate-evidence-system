import pytest
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
        connection.execute(
            text("CREATE TABLE students (student_id INTEGER, student_no VARCHAR(64), student_name VARCHAR(64))")
        )
        connection.execute(
            text(
                "CREATE TABLE credential_roots "
                "(root_id INTEGER PRIMARY KEY, root_no VARCHAR(64), batch_id INTEGER, "
                "merkle_root VARCHAR(64), previous_root_hash VARCHAR(64), "
                "current_root_hash VARCHAR(64), odd_leaf_rule VARCHAR(32), "
                "leaf_count INTEGER, created_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE merkle_tree_nodes "
                "(node_id INTEGER PRIMARY KEY, root_id INTEGER, level INTEGER, "
                "position_in_level INTEGER, node_hash VARCHAR(64), certificate_no VARCHAR(80))"
            )
        )

    monkeypatch.setattr(upgrader, "engine", engine)
    upgrader.main()
    upgrader.main()

    inspector = inspect(engine)
    batch_columns = {column["name"] for column in inspector.get_columns("certificate_batches")}
    certificate_columns = {column["name"] for column in inspector.get_columns("certificates")}
    revocation_columns = {column["name"] for column in inspector.get_columns("revocation_records")}
    student_columns = {column["name"] for column in inspector.get_columns("students")}
    root_columns = {column["name"] for column in inspector.get_columns("credential_roots")}

    assert {"project_name", "template_id", "student_ids"} <= batch_columns
    assert {"project_name", "issue_time", "previous_certificate_no", "updated_at"} <= certificate_columns
    assert {"action_type", "new_certificate_no"} <= revocation_columns
    assert "college" in student_columns
    assert "leaf_order_rule" in root_columns
    assert {"credential_roots", "merkle_tree_nodes"} <= set(inspector.get_table_names())

    root_unique_columns = upgrader._unique_column_sets("credential_roots")
    node_unique_columns = upgrader._unique_column_sets("merkle_tree_nodes")
    assert ("batch_id",) in root_unique_columns
    assert ("root_id", "level", "position_in_level") in node_unique_columns


@pytest.mark.parametrize(
    ("table_ddl", "insert_sql", "table_name", "index_name", "column_names"),
    [
        (
            "CREATE TABLE credential_roots (root_id INTEGER PRIMARY KEY, batch_id INTEGER)",
            "INSERT INTO credential_roots (root_id, batch_id) VALUES (1, 7), (2, 7)",
            "credential_roots",
            "uq_credential_roots_batch_id",
            ("batch_id",),
        ),
        (
            "CREATE TABLE merkle_tree_nodes "
            "(node_id INTEGER PRIMARY KEY, root_id INTEGER, level INTEGER, position_in_level INTEGER)",
            "INSERT INTO merkle_tree_nodes "
            "(node_id, root_id, level, position_in_level) VALUES (1, 3, 0, 0), (2, 3, 0, 0)",
            "merkle_tree_nodes",
            "uq_merkle_tree_nodes_position",
            ("root_id", "level", "position_in_level"),
        ),
    ],
)
def test_unique_index_upgrade_reports_duplicates_without_deleting_rows(
    monkeypatch,
    table_ddl,
    insert_sql,
    table_name,
    index_name,
    column_names,
):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text(table_ddl))
        connection.execute(text(insert_sql))

    monkeypatch.setattr(upgrader, "engine", engine)
    with pytest.raises(upgrader.SchemaUpgradeConflictError, match="no rows were deleted"):
        upgrader._create_unique_index_if_missing(
            table_name,
            index_name,
            column_names,
        )

    with engine.connect() as connection:
        row_count = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
    assert row_count == 2
