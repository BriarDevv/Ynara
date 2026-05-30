"""initial schema - 6 tablas, 4 enums nativos, pgvector + pgcrypto.

TABLAS SAGRADAS (regla #3): users + memoria/audit. El downgrade DESTRUYE
datos: dropea las 6 tablas, los 4 tipos enum y la extension vector.

Revision ID: b7b06025f4bb
Revises:
Create Date: 2026-05-29 19:49:25.484334

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7b06025f4bb"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensiones: vector (pgvector) para columnas VECTOR; pgcrypto para
    # gen_random_uuid(). pgcrypto ya existe en Supabase pero IF NOT EXISTS
    # mantiene la migracion self-contained para una DB limpia.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # Tipos enum nativos creados explicitamente; create_type=False en las
    # columnas evita el doble-create (mode_enum se usa en sessions y audit_log).
    bind = op.get_bind()
    for enum_type in (
        postgresql.ENUM(
            "productividad",
            "estudio",
            "bienestar",
            "vida",
            "memoria",
            name="mode_enum",
            create_type=False,
        ),
        postgresql.ENUM(
            "semantic", "episodic", "procedural", name="memory_layer_enum", create_type=False
        ),
        postgresql.ENUM("gemma", "qwen", name="llm_model_enum", create_type=False),
        postgresql.ENUM(
            "read", "write", "update", "delete", name="audit_operation_enum", create_type=False
        ),
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=40), nullable=True),
        sa.Column("is_ephemeral", sa.Boolean(), nullable=False),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False),
        sa.Column("retention_sensitive_days", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "retention_sensitive_days BETWEEN 30 AND 365",
            name=op.f("ck_users_retention_sensitive_days_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "audit_log",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "operation",
            postgresql.ENUM(
                "read", "write", "update", "delete", name="audit_operation_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "target_layer",
            postgresql.ENUM(
                "semantic", "episodic", "procedural", name="memory_layer_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column(
            "origin_model",
            postgresql.ENUM("gemma", "qwen", name="llm_model_enum", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "origin_mode",
            postgresql.ENUM(
                "productividad",
                "estudio",
                "bienestar",
                "vida",
                "memoria",
                name="mode_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("origin_tool", sa.String(length=80), nullable=True),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "record_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_audit_log_record_hash_sha256_hex")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_audit_log_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"], unique=False)
    op.create_table(
        "procedural_memory",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "last_reinforced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("stale", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name=op.f("ck_procedural_memory_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_procedural_memory_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_procedural_memory")),
        sa.UniqueConstraint("user_id", "key", name="user_id_key_unique"),
    )
    op.create_index(
        op.f("ix_procedural_memory_user_id"), "procedural_memory", ["user_id"], unique=False
    )
    op.create_table(
        "sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "mode",
            postgresql.ENUM(
                "productividad",
                "estudio",
                "bienestar",
                "vida",
                "memoria",
                name="mode_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "episodic_memory",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.LargeBinary(), nullable=False),
        sa.Column("summary_embedding", Vector(1024), nullable=False),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(is_sensitive = false) OR (retention_days BETWEEN 1 AND 365)",
            name=op.f("ck_episodic_memory_retention_days_sensitive_cap"),
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name=op.f("ck_episodic_memory_retention_days_range"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_episodic_memory_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_episodic_memory_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_episodic_memory")),
        sa.UniqueConstraint("session_id", name=op.f("uq_episodic_memory_session_id")),
    )
    op.create_index(
        "ix_episodic_memory_summary_embedding_hnsw",
        "episodic_memory",
        ["summary_embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"summary_embedding": "vector_cosine_ops"},
    )
    op.create_index(
        op.f("ix_episodic_memory_user_id"), "episodic_memory", ["user_id"], unique=False
    )
    op.create_table(
        "semantic_memory",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("content_embedding", Vector(1024), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=True),
        sa.Column("source_session_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "importance IS NULL OR (importance BETWEEN 0 AND 100)",
            name=op.f("ck_semantic_memory_importance_range"),
        ),
        sa.ForeignKeyConstraint(
            ["source_session_id"],
            ["sessions.id"],
            name=op.f("fk_semantic_memory_source_session_id_sessions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_semantic_memory_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_semantic_memory")),
    )
    op.create_index(
        "ix_semantic_memory_content_embedding_hnsw",
        "semantic_memory",
        ["content_embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"content_embedding": "vector_cosine_ops"},
    )
    op.create_index(
        op.f("ix_semantic_memory_user_id"), "semantic_memory", ["user_id"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_semantic_memory_user_id"), table_name="semantic_memory")
    op.drop_index(
        "ix_semantic_memory_content_embedding_hnsw",
        table_name="semantic_memory",
        postgresql_using="hnsw",
        postgresql_ops={"content_embedding": "vector_cosine_ops"},
    )
    op.drop_table("semantic_memory")
    op.drop_index(op.f("ix_episodic_memory_user_id"), table_name="episodic_memory")
    op.drop_index(
        "ix_episodic_memory_summary_embedding_hnsw",
        table_name="episodic_memory",
        postgresql_using="hnsw",
        postgresql_ops={"summary_embedding": "vector_cosine_ops"},
    )
    op.drop_table("episodic_memory")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_procedural_memory_user_id"), table_name="procedural_memory")
    op.drop_table("procedural_memory")
    op.drop_index(op.f("ix_audit_log_user_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_created_at"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS audit_operation_enum")
    op.execute("DROP TYPE IF EXISTS llm_model_enum")
    op.execute("DROP TYPE IF EXISTS memory_layer_enum")
    op.execute("DROP TYPE IF EXISTS mode_enum")
    op.execute("DROP EXTENSION IF EXISTS vector")
