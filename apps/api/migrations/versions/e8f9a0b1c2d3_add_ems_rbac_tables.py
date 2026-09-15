"""add ems rbac tables (ems_role, ems_permission_rule, ems_user_role_assignment)

Revision ID: e8f9a0b1c2d3
Revises: 2f4c13b60f5b
Create Date: 2026-09-15

"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "2f4c13b60f5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. ems_role table
    if "ems_role" not in existing_tables:
        op.create_table(
            "ems_role",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("org_id", sa.Integer(), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("slug", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("is_system_template", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_clinical_specialist", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ems_role_org_id", "ems_role", ["org_id"])
        op.create_index("ix_ems_role_slug", "ems_role", ["slug"])
        op.create_index("ix_ems_role_org_slug", "ems_role", ["org_id", "slug"])
        op.create_index("ix_ems_role_org_template", "ems_role", ["org_id", "is_system_template"])
        op.create_index("ix_ems_role_is_system_template", "ems_role", ["is_system_template"])
    else:
        logger.info("ems_role already exists (create_all built it); skipping creation.")

    # 2. ems_permission_rule table
    if "ems_permission_rule" not in existing_tables:
        op.create_table(
            "ems_permission_rule",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("ems_role.id", ondelete="CASCADE"), nullable=False),
            sa.Column("resource_key", sa.String(length=64), nullable=False),
            sa.Column("can_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("can_create", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("can_update", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("can_delete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("can_approve", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("can_export", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("scope_level", sa.String(length=32), nullable=False, server_default="ALL"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("role_id", "resource_key", name="uq_ems_permission_rule_role_resource"),
        )
        op.create_index("ix_ems_permission_rule_role_id", "ems_permission_rule", ["role_id"])
        op.create_index("ix_ems_permission_rule_resource_key", "ems_permission_rule", ["resource_key"])
        op.create_index("ix_ems_permission_rule_role_resource", "ems_permission_rule", ["role_id", "resource_key"])
    else:
        logger.info("ems_permission_rule already exists (create_all built it); skipping creation.")

    # 3. ems_user_role_assignment table
    if "ems_user_role_assignment" not in existing_tables:
        op.create_table(
            "ems_user_role_assignment",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("ems_role.id", ondelete="CASCADE"), nullable=False),
            sa.Column("org_id", sa.Integer(), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
            sa.Column("campus_id", sa.Integer(), sa.ForeignKey("campus.id", ondelete="SET NULL"), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("class_section.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_ems_user_role_assignment_user_id", "ems_user_role_assignment", ["user_id"])
        op.create_index("ix_ems_user_role_assignment_role_id", "ems_user_role_assignment", ["role_id"])
        op.create_index("ix_ems_user_role_assignment_org_id", "ems_user_role_assignment", ["org_id"])
        op.create_index("ix_ems_user_role_assignment_campus_id", "ems_user_role_assignment", ["campus_id"])
        op.create_index("ix_ems_user_role_assignment_department_id", "ems_user_role_assignment", ["department_id"])
        op.create_index("ix_ems_user_role_assignment_section_id", "ems_user_role_assignment", ["section_id"])
        op.create_index("ix_ems_user_role_assignment_user_org", "ems_user_role_assignment", ["user_id", "org_id"])
        op.create_index("ix_ems_user_role_assignment_role", "ems_user_role_assignment", ["role_id"])
        op.create_index("ix_ems_user_role_assignment_scope", "ems_user_role_assignment", ["org_id", "campus_id", "department_id", "section_id"])
    else:
        logger.info("ems_user_role_assignment already exists (create_all built it); skipping creation.")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "ems_user_role_assignment" in existing_tables:
        op.drop_index("ix_ems_user_role_assignment_scope", table_name="ems_user_role_assignment")
        op.drop_index("ix_ems_user_role_assignment_role", table_name="ems_user_role_assignment")
        op.drop_index("ix_ems_user_role_assignment_user_org", table_name="ems_user_role_assignment")
        op.drop_index("ix_ems_user_role_assignment_section_id", table_name="ems_user_role_assignment")
        op.drop_index("ix_ems_user_role_assignment_department_id", table_name="ems_user_role_assignment")
        op.drop_index("ix_ems_user_role_assignment_campus_id", table_name="ems_user_role_assignment")
        op.drop_index("ix_ems_user_role_assignment_org_id", table_name="ems_user_role_assignment")
        op.drop_index("ix_ems_user_role_assignment_role_id", table_name="ems_user_role_assignment")
        op.drop_index("ix_ems_user_role_assignment_user_id", table_name="ems_user_role_assignment")
        op.drop_table("ems_user_role_assignment")

    if "ems_permission_rule" in existing_tables:
        op.drop_index("ix_ems_permission_rule_role_resource", table_name="ems_permission_rule")
        op.drop_index("ix_ems_permission_rule_resource_key", table_name="ems_permission_rule")
        op.drop_index("ix_ems_permission_rule_role_id", table_name="ems_permission_rule")
        op.drop_table("ems_permission_rule")

    if "ems_role" in existing_tables:
        op.drop_index("ix_ems_role_is_system_template", table_name="ems_role")
        op.drop_index("ix_ems_role_org_template", table_name="ems_role")
        op.drop_index("ix_ems_role_org_slug", table_name="ems_role")
        op.drop_index("ix_ems_role_slug", table_name="ems_role")
        op.drop_index("ix_ems_role_org_id", table_name="ems_role")
        op.drop_table("ems_role")
