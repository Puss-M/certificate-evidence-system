from sqlalchemy import inspect, text

from app.db.session import engine
from app.models.credential_root import CredentialRoot
from app.models.merkle_tree_node import MerkleTreeNode


class SchemaUpgradeConflictError(RuntimeError):
    pass


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


def _create_merkle_tables_if_missing() -> None:
    CredentialRoot.__table__.create(bind=engine, checkfirst=True)
    MerkleTreeNode.__table__.create(bind=engine, checkfirst=True)


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    inspector = inspect(engine)
    constraints = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints(table_name)
    }
    indexes = {
        tuple(item["column_names"])
        for item in inspector.get_indexes(table_name)
        if item.get("unique")
    }
    return constraints | indexes


def _create_unique_index_if_missing(
    table_name: str,
    index_name: str,
    column_names: tuple[str, ...],
) -> None:
    if column_names in _unique_column_sets(table_name):
        return
    columns_sql = ", ".join(column_names)
    with engine.begin() as connection:
        duplicates = connection.execute(
            text(
                f"SELECT {columns_sql}, COUNT(*) AS duplicate_count "
                f"FROM {table_name} GROUP BY {columns_sql} "
                "HAVING COUNT(*) > 1 LIMIT 5"
            )
        ).all()
        if duplicates:
            raise SchemaUpgradeConflictError(
                f"cannot add {index_name}: {table_name} has duplicate keys "
                f"for ({columns_sql}): {duplicates}; no rows were deleted, "
                "resolve the historical duplicates and rerun the upgrade"
            )
        connection.execute(
            text(f"CREATE UNIQUE INDEX {index_name} ON {table_name} ({columns_sql})")
        )
    print(f"added unique index {index_name}")


def main() -> None:
    if engine is None:
        print("DATABASE_URL is not configured; schema upgrade skipped")
        return

    if _column_names("certificates"):
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

    if _column_names("students"):
        _add_column_if_missing("students", "college", "college VARCHAR(100) NULL")

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

    if _column_names("certificate_batches"):
        _create_merkle_tables_if_missing()
        _add_column_if_missing(
            "credential_roots",
            "leaf_order_rule",
            "leaf_order_rule VARCHAR(32) NOT NULL DEFAULT 'CERTIFICATE_NO_ASC'",
        )
        _create_unique_index_if_missing(
            "credential_roots",
            "uq_credential_roots_batch_id",
            ("batch_id",),
        )
        _create_unique_index_if_missing(
            "merkle_tree_nodes",
            "uq_merkle_tree_nodes_position",
            ("root_id", "level", "position_in_level"),
        )

    if _column_names("certificates"):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE certificates SET updated_at = created_at WHERE updated_at IS NULL")
            )

    print("certificate schema upgraded")


if __name__ == "__main__":
    main()
