"""initial schema: tenancy, documents, chunks, fixes, audit, RLS

Revision ID: 0001
Revises:
Create Date: 2026-06-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, TSVECTOR, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024  # BGE-M3 contract — must match fixmate.core.models.EMBEDDING_DIM

TENANT_TABLES = [
    "users",
    "equipment_profiles",
    "documents",
    "conversations",
    "answer_logs",
    "messages",
    "fixes",
    "chunks",
    "figures",
    "feedback",
    "audit_events",
]


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def _org_fk() -> sa.Column:
    return sa.Column(
        "organization_id",
        UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "organizations",
        _uuid_pk(),
        sa.Column("name", sa.Text, nullable=False),
        _created_at(),
    )

    op.create_table(
        "users",
        _uuid_pk(),
        _org_fk(),
        sa.Column("email", sa.Text),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        _created_at(),
        sa.CheckConstraint("role IN ('tech', 'curator', 'admin')", name="users_role_check"),
    )

    op.create_table(
        "equipment_profiles",
        _uuid_pk(),
        _org_fk(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("manufacturer", sa.Text),
        sa.Column("model", sa.Text),
        _created_at(),
    )

    op.create_table(
        "documents",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "equipment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("equipment_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "superseded_by", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")
        ),
        sa.Column("storage_key", sa.Text, nullable=False),
        _created_at(),
    )

    op.create_table(
        "conversations",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "equipment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("equipment_profiles.id", ondelete="SET NULL"),
        ),
        _created_at(),
    )

    op.create_table(
        "answer_logs",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
        ),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer_text", sa.Text, nullable=False),
        sa.Column(
            "retrieved_chunk_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("model_version", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("confidence", sa.Text, nullable=False),
        sa.Column("citations", JSONB),
        sa.Column("groundedness", JSONB),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default=sa.text("0")),
        _created_at(),
    )

    op.create_table(
        "messages",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "answer_log_id",
            UUID(as_uuid=True),
            sa.ForeignKey("answer_logs.id", ondelete="SET NULL"),
        ),
        _created_at(),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="messages_role_check"),
    )

    op.create_table(
        "fixes",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "equipment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("equipment_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text),
        sa.Column(
            "answer_log_id",
            UUID(as_uuid=True),
            sa.ForeignKey("answer_logs.id", ondelete="SET NULL"),
        ),
        sa.Column("proposed_text", sa.Text, nullable=False),
        sa.Column("photos", JSONB),
        sa.Column(
            "submitted_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.Text, nullable=False, server_default=sa.text("'submitted'")),
        sa.Column(
            "reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("review_notes", sa.Text),
        sa.Column("ai_prescreen_report", JSONB),
        sa.Column("approved_at", TIMESTAMP(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        _created_at(),
        sa.Column(
            "updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "state IN ('submitted', 'pending_review', 'approved', 'rejected', 'unsafe', 'retired')",
            name="fixes_state_check",
        ),
    )

    op.create_table(
        "chunks",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE")
        ),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("page", sa.Integer),
        sa.Column("fix_id", UUID(as_uuid=True), sa.ForeignKey("fixes.id", ondelete="CASCADE")),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        # 'english' config gives stemming; revisit if more launch languages land (FR-7).
        sa.Column("tsv", TSVECTOR, sa.Computed("to_tsvector('english', content)", persisted=True)),
        _created_at(),
        sa.CheckConstraint(
            "source_type IN ('manual', 'field_fix')", name="chunks_source_type_check"
        ),
    )

    op.create_table(
        "figures",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("caption", sa.Text),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("bbox", JSONB),
        _created_at(),
    )

    op.create_table(
        "feedback",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("helped", sa.Boolean, nullable=False),
        sa.Column("fix_id", UUID(as_uuid=True), sa.ForeignKey("fixes.id", ondelete="SET NULL")),
        _created_at(),
    )

    op.create_table(
        "audit_events",
        _uuid_pk(),
        _org_fk(),
        sa.Column("actor_id", UUID(as_uuid=True)),
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("before", JSONB),
        sa.Column("after", JSONB),
        _created_at(),
    )

    for table in TENANT_TABLES:
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])

    op.execute(
        "CREATE INDEX ix_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ix_chunks_tsv ON chunks USING gin (tsv)")

    # RLS: tenant isolation enforced at the query level (CLAUDE.md §4.5, §6).
    # FORCE makes policies apply even to the table owner.
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (organization_id = current_setting('app.current_org_id')::uuid)"
        )
    # organizations is the tenant root: a session may only see its own org row;
    # creating organizations is a bootstrap operation done by the owner role.
    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON organizations "
        "USING (id = current_setting('app.current_org_id')::uuid)"
    )

    # Application role: CRUD but no BYPASSRLS, so RLS policies always apply.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fixmate_app') THEN
                CREATE ROLE fixmate_app LOGIN PASSWORD 'fixmate_app';
            END IF;
        END
        $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO fixmate_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fixmate_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fixmate_app"
    )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.drop_table(table)
    op.drop_table("organizations")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM fixmate_app"
    )
    # Covers alembic_version, which the upgrade's GRANT ALL TABLES also caught.
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM fixmate_app")
    op.execute("REVOKE USAGE ON SCHEMA public FROM fixmate_app")
    op.execute("DROP ROLE IF EXISTS fixmate_app")
