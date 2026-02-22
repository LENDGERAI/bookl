from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


CountryCode = Literal["AU", "US", "UK", "IN", "FR", "CUSTOM"]
LanguageCode = Literal["en", "fr"]
TransactionType = Literal["income", "expense", "receivable", "payable", "payroll", "marketing", "tax"]


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    country: CountryCode = "CUSTOM"
    language: LanguageCode = "en"
    base_currency: str | None = Field(default=None, min_length=3, max_length=8)


class BusinessRead(BaseModel):
    id: str
    name: str
    country: str
    language: str
    base_currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentRead(BaseModel):
    id: str
    business_id: str
    filename: str
    content_type: str
    status: str
    version: int
    duplicate_of_document_id: str | None
    error_message: str | None
    uploaded_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class UploadDocumentsResponse(BaseModel):
    message: str
    documents: list[DocumentRead]


class TransactionCreate(BaseModel):
    tx_type: TransactionType = "expense"
    category: str | None = None
    description: str | None = None
    counterparty: str | None = None
    reference_number: str | None = None
    occurred_on: date | None = None
    amount: Decimal = Field(gt=0)
    tax_amount: Decimal = Field(default=0)
    currency: str = "USD"
    payment_method: str | None = None
    source: str = "manual"


class TransactionUpdate(BaseModel):
    tx_type: TransactionType | None = None
    category: str | None = None
    description: str | None = None
    counterparty: str | None = None
    reference_number: str | None = None
    occurred_on: date | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    tax_amount: Decimal | None = None
    currency: str | None = None
    payment_method: str | None = None
    needs_review: bool | None = None


class TransactionRead(BaseModel):
    id: str
    business_id: str
    document_id: str | None
    tx_type: str
    category: str
    description: str | None
    counterparty: str | None
    reference_number: str | None
    occurred_on: date | None
    amount: Decimal
    tax_amount: Decimal
    currency: str
    payment_method: str | None
    confidence: float
    needs_review: bool
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CorrectionRequest(BaseModel):
    category: str = Field(min_length=2, max_length=120)


class NotificationRead(BaseModel):
    id: str
    level: str
    kind: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotResponse(BaseModel):
    currency: str
    total_income: Decimal
    total_expense: Decimal
    net_profit: Decimal
    cash_in: Decimal
    cash_out: Decimal
    receivables: Decimal
    payables: Decimal
    expense_breakdown: dict[str, Decimal]
    advisory: list[str]
    message: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    actions: list[str] = Field(default_factory=list)
    transactions: list[TransactionRead] = Field(default_factory=list)

