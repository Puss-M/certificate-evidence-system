from sqlalchemy import Index, MetaData, Table, func, inspect, select, text
from sqlalchemy.engine import Engine

from app.db.session import engine
from app.models.credential_root import CredentialRoot
from app.models.merkle_tree_node import MerkleTreeNode
from app.models.project import Project
from app.models.user import AuthSession, Invitation, User


class SchemaUpgradeConflictError(RuntimeError):
    pass


def _database_engine() -> Engine:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")
    return engine


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(_database_engine())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    if column_name in _column_names(table_name):
        return
    with _database_engine().begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
    print(f"added {table_name}.{column_name}")


def _create_merkle_tables_if_missing() -> None:
    CredentialRoot.__table__.create(bind=_database_engine(), checkfirst=True)  # type: ignore[attr-defined]
    MerkleTreeNode.__table__.create(bind=_database_engine(), checkfirst=True)  # type: ignore[attr-defined]


def _create_project_table_if_missing() -> None:
    Project.__table__.create(bind=_database_engine(), checkfirst=True)  # type: ignore[attr-defined]


def _create_auth_tables_if_missing() -> None:
    User.__table__.create(bind=_database_engine(), checkfirst=True)  # type: ignore[attr-defined]
    Invitation.__table__.create(bind=_database_engine(), checkfirst=True)  # type: ignore[attr-defined]
    AuthSession.__table__.create(bind=_database_engine(), checkfirst=True)  # type: ignore[attr-defined]


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    inspector = inspect(_database_engine())
    constraints = {
        tuple(str(column_name) for column_name in item["column_names"] if column_name)
        for item in inspector.get_unique_constraints(table_name)
    }
    indexes = {
        tuple(str(column_name) for column_name in item["column_names"] if column_name)
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
    table = Table(table_name, MetaData(), autoload_with=_database_engine())
    columns = [table.c[column_name] for column_name in column_names]
    columns_label = ", ".join(column_names)
    with _database_engine().begin() as connection:
        duplicates = connection.execute(
            select(*columns, func.count().label("duplicate_count"))
            .select_from(table)
            .group_by(*columns)
            .having(func.count() > 1)
            .limit(5)
        ).all()
        if duplicates:
            raise SchemaUpgradeConflictError(
                f"cannot add {index_name}: {table_name} has duplicate keys "
                f"for ({columns_label}): {duplicates}; no rows were deleted, "
                "resolve the historical duplicates and rerun the upgrade"
            )
        Index(index_name, *columns, unique=True).create(bind=connection)
    print(f"added unique index {index_name}")


def main() -> None:
    if engine is None:
        print("DATABASE_URL is not configured; schema upgrade skipped")
        return

    _create_project_table_if_missing()
    _create_auth_tables_if_missing()

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
        _add_column_if_missing(
            "certificates",
            "institution_name",
            "institution_name VARCHAR(200) NULL",
        )

    if _column_names("students"):
        _add_column_if_missing("students", "college", "college VARCHAR(100) NULL")

    if _column_names("certificate_templates"):
        _add_column_if_missing(
            "certificate_templates",
            "institution_name",
            "institution_name VARCHAR(200) NOT NULL DEFAULT '示范学院'",
        )
        _add_column_if_missing(
            "certificate_templates",
            "updated_at",
            "updated_at DATETIME NULL",
        )

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
            "project_id",
            "project_id INT NULL",
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
        _add_column_if_missing(
            "credential_roots",
            "tx_hash",
            "tx_hash VARCHAR(80) NULL",
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
        with _database_engine().begin() as connection:
            connection.execute(
                text("UPDATE certificates SET updated_at = created_at WHERE updated_at IS NULL")
            )
            if (
                "template_id" in _column_names("certificates")
                and _column_names("certificate_templates")
            ):
                connection.execute(
                    text(
                        "UPDATE certificates SET institution_name = ("
                        "SELECT certificate_templates.institution_name "
                        "FROM certificate_templates "
                        "WHERE certificate_templates.template_id = certificates.template_id"
                        ") WHERE institution_name IS NULL"
                    )
                )

    if _column_names("certificate_templates"):
        with _database_engine().begin() as connection:
            connection.execute(
                text(
                    "UPDATE certificate_templates SET updated_at = created_at "
                    "WHERE updated_at IS NULL"
                )
            )

    print("certificate schema upgraded")


if __name__ == "__main__":
    main()
