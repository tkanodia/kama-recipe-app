from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SourceAsset(Base):
    __tablename__ = "source_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    original_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_asset_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    context_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list[IngestionJob]] = relationship(back_populates="source_asset")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    source_asset_id: Mapped[str] = mapped_column(String(64), ForeignKey("source_assets.id"), index=True)

    status: Mapped[str] = mapped_column(String(32), index=True)
    internal_state: Mapped[str] = mapped_column(String(64))
    internal_error_state: Mapped[str | None] = mapped_column(String(128), nullable=True)

    processor_family: Mapped[str] = mapped_column(String(32))
    processor_variant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)

    candidate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_artifact_ids: Mapped[list] = mapped_column(JSONB, default=list)

    error_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rerun_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    user_recoverable: Mapped[bool] = mapped_column(Boolean, default=True)

    extraction_plan: Mapped[list] = mapped_column(JSONB, default=list)
    state_history: Mapped[list] = mapped_column(JSONB, default=list)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_asset: Mapped[SourceAsset] = relationship(back_populates="jobs")


class NormalizedSourceArtifact(Base):
    __tablename__ = "normalized_source_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ingestion_job_id: Mapped[str] = mapped_column(String(64), ForeignKey("ingestion_jobs.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecipeCandidate(Base):
    __tablename__ = "recipe_candidates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    source_asset_id: Mapped[str] = mapped_column(String(64), ForeignKey("source_assets.id"))
    ingestion_job_id: Mapped[str] = mapped_column(String(64), ForeignKey("ingestion_jobs.id"))

    title: Mapped[str] = mapped_column(Text)
    ingredients: Mapped[list] = mapped_column(JSONB, default=list)
    steps: Mapped[list] = mapped_column(JSONB, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recipe_tags: Mapped[list] = mapped_column(JSONB, default=list)
    nutrition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[list] = mapped_column(JSONB, default=list)
    how_to_serve: Mapped[str | None] = mapped_column(Text, nullable=True)

    canonical_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    draft_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    review_mode: Mapped[str] = mapped_column(String(32), default="standard")

    review_findings: Mapped[list] = mapped_column(JSONB, default=list)
    field_confidence_map: Mapped[dict] = mapped_column(JSONB, default=dict)
    field_provenance_map: Mapped[dict] = mapped_column(JSONB, default=dict)
    selected_extraction_method: Mapped[str] = mapped_column(String(128), default="")
    source_artifact_ids: Mapped[list] = mapped_column(JSONB, default=list)

    decision_status: Mapped[str] = mapped_column(String(32), default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DraftRecipe(Base):
    __tablename__ = "draft_recipes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    origin_source_asset_id: Mapped[str] = mapped_column(String(64), ForeignKey("source_assets.id"))
    origin_recipe_candidate_id: Mapped[str] = mapped_column(String(64), ForeignKey("recipe_candidates.id"))

    title: Mapped[str] = mapped_column(Text)
    ingredients: Mapped[list] = mapped_column(JSONB, default=list)
    steps: Mapped[list] = mapped_column(JSONB, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recipe_tags: Mapped[list] = mapped_column(JSONB, default=list)
    nutrition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[list] = mapped_column(JSONB, default=list)
    how_to_serve: Mapped[str | None] = mapped_column(Text, nullable=True)
    promotion_eligible: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CanonicalRecipe(Base):
    __tablename__ = "canonical_recipes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    title: Mapped[str] = mapped_column(Text)
    ingredients: Mapped[list] = mapped_column(JSONB, default=list)
    steps: Mapped[list] = mapped_column(JSONB, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recipe_tags: Mapped[list] = mapped_column(JSONB, default=list)
    nutrition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[list] = mapped_column(JSONB, default=list)
    how_to_serve: Mapped[str | None] = mapped_column(Text, nullable=True)

    hero_image_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    journal_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_provenance_map: Mapped[dict] = mapped_column(JSONB, default=dict)

    source_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    origin_recipe_candidate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    promoted_from_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RecipeRevision(Base):
    __tablename__ = "recipe_revisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_recipe_id: Mapped[str] = mapped_column(String(64), ForeignKey("canonical_recipes.id"), index=True)
    snapshot_payload: Mapped[dict] = mapped_column(JSONB)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecipeMedia(Base):
    __tablename__ = "recipe_media"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_recipe_id: Mapped[str] = mapped_column(String(64), ForeignKey("canonical_recipes.id"), index=True)
    media_type: Mapped[str] = mapped_column(String(16), default="image")
    role: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    asset_ref: Mapped[str] = mapped_column(String(512))
    thumbnail_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True, default="other")
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_system: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    domain: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(128))
    created_by_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CookJournalEntry(Base):
    __tablename__ = "cook_journal_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_recipe_id: Mapped[str] = mapped_column(String(64), ForeignKey("canonical_recipes.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    body: Mapped[str] = mapped_column(Text)
    cooked_on: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecipeSearchIndexStatus(Base):
    __tablename__ = "recipe_search_index_status"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_recipe_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("canonical_recipes.id", ondelete="CASCADE"), unique=True, index=True
    )
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, default=True)
    stale_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stale_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AskSession(Base):
    __tablename__ = "ask_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    recipe_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AskMessage(Base):
    __tablename__ = "ask_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("ask_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    retrieved_recipe_ids: Mapped[list] = mapped_column(JSONB, default=list)
    cited_recipe_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    artifact_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_recipe_ids: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ArtifactRevision(Base):
    __tablename__ = "artifact_revisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String(64), ForeignKey("artifacts.id", ondelete="CASCADE"), index=True)
    snapshot_payload: Mapped[dict] = mapped_column(JSONB)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PantryItem(Base):
    __tablename__ = "pantry_items"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "ingredient_id", name="uq_pantry_user_ingredient"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    ingredient_id: Mapped[str] = mapped_column(String(64), ForeignKey("ingredients.id"), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JournalEntryMedia(Base):
    __tablename__ = "journal_entry_media"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    journal_entry_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cook_journal_entries.id"), index=True
    )
    asset_ref: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(32), default="uploaded")
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
