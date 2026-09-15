import importlib
from logging.config import fileConfig
import os
import alembic_postgresql_enum # noqa: F401
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlmodel import SQLModel
from alembic import context

from config.config import get_learnhouse_config

# LearnHouse config

lh_config = get_learnhouse_config()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Alembic must target the same DB as the running app. The alembic.ini URL is
# only a dev fallback (hardcoded localhost); inside Docker the real URL is in
# LEARNHOUSE_SQL_CONNECTION_STRING (e.g. postgresql://...@db:5432/...).
_runtime_db_url = os.environ.get("LEARNHOUSE_SQL_CONNECTION_STRING")
if _runtime_db_url:
    # Alembic uses psycopg2 (sync); strip the async driver suffix if present.
    _runtime_db_url = _runtime_db_url.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    config.set_main_option("sqlalchemy.url", _runtime_db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

# IMPORTING ALL SCHEMAS
base_dir = 'src/db'
base_module_path = 'src.db'

# Recursively walk through the base directory
for root, dirs, files in os.walk(base_dir):
    # Filter out __init__.py and non-Python files
    module_files = [f for f in files if f.endswith('.py') and f != '__init__.py']
    # Calculate the module's base path from its directory structure
    path_diff = os.path.relpath(root, base_dir)
    if path_diff == '.':
        # Root of the base_dir, no additional path to add
        current_module_base = base_module_path
    else:
        # Convert directory path to a module path
        current_module_base = f"{base_module_path}.{path_diff.replace(os.sep, '.')}"
    
    # Dynamically import each module
    for file_name in module_files:
        module_name = file_name[:-3]  # Remove the '.py' extension
        full_module_path = f"{current_module_base}.{module_name}"
        importlib.import_module(full_module_path)

# IMPORTING ALL SCHEMAS

target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def _install_idempotent_guards():
    """Wrap Alembic Operations methods so pre-existing tables/columns don't crash migrations."""
    import sqlalchemy as sa
    from alembic.operations import Operations

    orig_add_column = Operations.add_column
    orig_drop_column = Operations.drop_column
    orig_alter_column = Operations.alter_column
    orig_create_table = Operations.create_table
    orig_drop_table = Operations.drop_table
    orig_rename_table = Operations.rename_table
    orig_create_index = Operations.create_index
    orig_drop_index = Operations.drop_index
    orig_create_foreign_key = Operations.create_foreign_key
    orig_drop_constraint = Operations.drop_constraint
    orig_create_unique_constraint = Operations.create_unique_constraint
    orig_create_check_constraint = Operations.create_check_constraint

    def _ensure_enum_type(bind, col_type):
        if col_type is None:
            return
        enum_name = getattr(col_type, "name", None)
        enums = getattr(col_type, "enums", None)
        if enum_name and enums:
            try:
                res = bind.execute(
                    sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
                    {"name": enum_name},
                ).scalar()
                if not res:
                    vals = ", ".join("'" + str(v).replace("'", "''") + "'" for v in enums)
                    bind.execute(sa.text(f"CREATE TYPE {enum_name} AS ENUM ({vals})"))
            except Exception:
                pass

    def _ensure_enums_in_args(bind, *args):
        for arg in args:
            if isinstance(arg, sa.Column):
                _ensure_enum_type(bind, getattr(arg, "type", None))
            elif hasattr(arg, "columns"):
                for col in arg.columns:
                    _ensure_enum_type(bind, getattr(col, "type", None))

    def safe_add_column(self, table_name, column, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name in insp.get_table_names():
            existing = {c["name"] for c in insp.get_columns(table_name)}
            if column.name in existing:
                return None
        _ensure_enums_in_args(bind, column)
        return orig_add_column(self, table_name, column, **kw)

    def safe_drop_column(self, table_name, column_name, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name not in insp.get_table_names():
            return None
        existing = {c["name"] for c in insp.get_columns(table_name)}
        if column_name not in existing:
            return None
        return orig_drop_column(self, table_name, column_name, **kw)

    def safe_alter_column(self, table_name, column_name, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name not in insp.get_table_names():
            return None
        existing = {c["name"] for c in insp.get_columns(table_name)}
        if column_name not in existing:
            return None
        return orig_alter_column(self, table_name, column_name, **kw)

    def safe_create_table(self, table_name, *columns, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name in insp.get_table_names():
            return None
        _ensure_enums_in_args(bind, *columns)
        return orig_create_table(self, table_name, *columns, **kw)

    def safe_drop_table(self, table_name, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name not in insp.get_table_names():
            return None
        return orig_drop_table(self, table_name, **kw)

    def safe_rename_table(self, old_table_name, new_table_name, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        tables = insp.get_table_names()
        if old_table_name not in tables:
            return None
        if new_table_name in tables:
            return None
        return orig_rename_table(self, old_table_name, new_table_name, **kw)

    def safe_create_index(self, index_name, table_name, columns, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name in insp.get_table_names():
            existing = {idx["name"] for idx in insp.get_indexes(table_name) if idx.get("name")}
            if index_name in existing:
                return None
        return orig_create_index(self, index_name, table_name, columns, **kw)

    def safe_drop_index(self, index_name, table_name=None, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name and table_name in insp.get_table_names():
            existing = {idx["name"] for idx in insp.get_indexes(table_name) if idx.get("name")}
            if index_name not in existing:
                return None
        return orig_drop_index(self, index_name, table_name=table_name, **kw)

    def safe_create_foreign_key(self, constraint_name, source_table, referent_table, local_cols, remote_cols, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        tables = insp.get_table_names()
        if source_table not in tables or referent_table not in tables:
            return None
        existing = {fk["name"] for fk in insp.get_foreign_keys(source_table) if fk.get("name")}
        if constraint_name and constraint_name in existing:
            return None
        return orig_create_foreign_key(self, constraint_name, source_table, referent_table, local_cols, remote_cols, **kw)

    def safe_drop_constraint(self, constraint_name, table_name, type_=None, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name not in insp.get_table_names():
            return None
        fks = {fk["name"] for fk in insp.get_foreign_keys(table_name) if fk.get("name")}
        uniques = {u["name"] for u in insp.get_unique_constraints(table_name) if u.get("name")}
        checks = {c["name"] for c in insp.get_check_constraints(table_name) if c.get("name")}
        all_cons = fks | uniques | checks
        if constraint_name and constraint_name not in all_cons:
            return None
        return orig_drop_constraint(self, constraint_name, table_name, type_=type_, **kw)

    def safe_create_unique_constraint(self, constraint_name, table_name, columns, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name not in insp.get_table_names():
            return None
        existing = {u["name"] for u in insp.get_unique_constraints(table_name) if u.get("name")}
        if constraint_name and constraint_name in existing:
            return None
        return orig_create_unique_constraint(self, constraint_name, table_name, columns, **kw)

    def safe_create_check_constraint(self, constraint_name, table_name, condition, **kw):
        bind = self.get_bind()
        insp = sa.inspect(bind)
        if table_name not in insp.get_table_names():
            return None
        checks = {c["name"] for c in insp.get_check_constraints(table_name) if c.get("name")}
        if constraint_name and constraint_name in checks:
            return None
        return orig_create_check_constraint(self, constraint_name, table_name, condition, **kw)

    Operations.add_column = safe_add_column
    Operations.drop_column = safe_drop_column
    Operations.alter_column = safe_alter_column
    Operations.create_table = safe_create_table
    Operations.drop_table = safe_drop_table
    Operations.rename_table = safe_rename_table
    Operations.create_index = safe_create_index
    Operations.drop_index = safe_drop_index
    Operations.create_foreign_key = safe_create_foreign_key
    Operations.drop_constraint = safe_drop_constraint
    Operations.create_unique_constraint = safe_create_unique_constraint
    Operations.create_check_constraint = safe_create_check_constraint


_install_idempotent_guards()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        try:
            SQLModel.metadata.create_all(connection)
        except Exception:
            pass

        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

