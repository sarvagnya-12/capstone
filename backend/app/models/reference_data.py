"""Read-only reference tables mirroring the dataset-extraction pipeline's frozen
output schemas (Capstone Dataset (Archived)/.../schemas/*.json), column-for-column.
Populated by scripts/ingest_dataset_pipeline.py (Step 13). No FK relationships into
the application's own tables (products, etc.) -- the pipeline's product_id namespace
is separate from this application's products.id, so these are joined/queried by
product_id at the application layer, not foreign-keyed.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestionMixin:
    """Fields added by our ingestion process, not present in the pipeline's own schema."""

    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_dataset_version: Mapped[str] = mapped_column(String, nullable=False)


class RefProduct(Base, IngestionMixin):
    """Mirrors schemas/master_products_schema.json."""

    __tablename__ = "ref_products"

    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    brand: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    retail_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    release_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    primary_color: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    secondary_color: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    material: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_refs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    review_refs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    market_record_refs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    product_intelligence_refs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    relationship_counts: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class RefImage(Base, IngestionMixin):
    """Mirrors schemas/images_schema.json."""

    __tablename__ = "ref_images"

    image_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    original_image_url: Mapped[str] = mapped_column(String, nullable=False)
    image_type: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_format: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    download_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class RefReview(Base, IngestionMixin):
    """Mirrors schemas/reviews_schema.json."""

    __tablename__ = "ref_reviews"

    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_review_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    review_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reviewer_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    verified_purchase: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    helpful_votes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class RefMarket(Base, IngestionMixin):
    """Mirrors schemas/market_schema.json. market_type/price_type/availability are
    stored as plain strings, not Postgres enums -- their vocabulary is owned and
    validated by the external pipeline, not by this application.
    """

    __tablename__ = "ref_market"

    market_record_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    market_type: Mapped[str] = mapped_column(String, nullable=False)
    price_type: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    availability: Mapped[str] = mapped_column(String, nullable=False)
    stock_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    release_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class RefProductIntelligence(Base, IngestionMixin):
    """Mirrors schemas/product_intelligence_schema.json."""

    __tablename__ = "ref_product_intelligence"

    intelligence_record_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    brand_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand_mission: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campaign_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campaign_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campaign_theme: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    marketing_strategy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_age_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_age_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_income_segment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_region: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_lifestyle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    brand_positioning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand_ambassador: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tagline: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    product_family: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parent_company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country_of_origin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    launch_region: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    distribution_channels: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sustainability_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    competitor_products: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    competitor_brands: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
