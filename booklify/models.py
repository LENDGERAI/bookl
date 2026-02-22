from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from booklify.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(12), nullable=False, default="CUSTOM")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    custom_rules_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    documents: Mapped[list["Document"]] = relationship(back_populates="business", cascade="all,delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="business",
        cascade="all,delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="business",
        cascade="all,delete-orphan",
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("business_id", "file_hash", name="uq_business_filehash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="application/octet-stream")
    file_hash: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    duplicate_of_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    extracted_payload_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    business: Mapped["Business"] = relationship(back_populates="documents")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="document",
        cascade="all,delete-orphan",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    tx_type: Mapped[str] = mapped_column(String(40), nullable=False, default="expense")
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="Uncategorized")
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    payment_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="upload")
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    business: Mapped["Business"] = relationship(back_populates="transactions")
    document: Mapped["Document"] = relationship(back_populates="transactions")


class CategorizationFeedback(Base):
    __tablename__ = "categorization_feedback"
    __table_args__ = (UniqueConstraint("business_id", "keyword", "category", name="uq_feedback_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    weight: Mapped[int] = mapped_column(nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    kind: Mapped[str] = mapped_column(String(60), nullable=False, default="general")
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    business: Mapped["Business"] = relationship(back_populates="notifications")


class ChatPreference(Base):
    __tablename__ = "chat_preferences"
    __table_args__ = (UniqueConstraint("business_id", "key", name="uq_preference_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

