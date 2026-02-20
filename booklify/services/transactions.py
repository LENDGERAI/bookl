from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from booklify.core.country_rules import CountryProfile
from booklify.models import Business, Transaction
from booklify.schemas import TransactionCreate, TransactionUpdate
from booklify.services.categorization import CategorizationService
from booklify.services.extraction import ExtractedTransaction
from booklify.services.notifications import NotificationService


class TransactionService:
    def __init__(
        self,
        categorization_service: CategorizationService,
        notification_service: NotificationService,
    ) -> None:
        self.categorization_service = categorization_service
        self.notification_service = notification_service

    def create_manual(
        self,
        db: Session,
        business: Business,
        country_profile: CountryProfile,
        payload: TransactionCreate,
    ) -> Transaction:
        extracted = ExtractedTransaction(
            tx_type=payload.tx_type,
            category=payload.category,
            description=payload.description,
            counterparty=payload.counterparty,
            reference_number=payload.reference_number,
            occurred_on=payload.occurred_on,
            amount=Decimal(payload.amount),
            tax_amount=Decimal(payload.tax_amount),
            currency=payload.currency,
            payment_method=payload.payment_method,
            confidence_hint=0.62,
            raw={"source": payload.source},
        )
        decision = self.categorization_service.categorize(db, business, country_profile, extracted)
        tx = Transaction(
            business_id=business.id,
            tx_type=payload.tx_type or decision.tx_type,
            category=payload.category or decision.category,
            description=payload.description,
            counterparty=payload.counterparty,
            reference_number=payload.reference_number,
            occurred_on=payload.occurred_on,
            amount=float(payload.amount),
            tax_amount=float(payload.tax_amount),
            currency=payload.currency,
            payment_method=payload.payment_method,
            confidence=decision.confidence,
            needs_review=decision.needs_review,
            source=payload.source,
        )
        db.add(tx)
        db.flush()
        self.notification_service.on_transaction_created(
            db,
            business.id,
            business.language,
            country_profile,
            tx,
        )
        return tx

    def list_for_business(self, db: Session, business_id: str) -> list[Transaction]:
        return db.scalars(
            select(Transaction).where(Transaction.business_id == business_id).order_by(Transaction.created_at.desc())
        ).all()

    def get(self, db: Session, tx_id: str) -> Transaction | None:
        return db.scalar(select(Transaction).where(Transaction.id == tx_id))

    def update(self, db: Session, tx: Transaction, payload: TransactionUpdate) -> Transaction:
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(tx, field, value)
        db.add(tx)
        db.flush()
        return tx

    def delete(self, db: Session, tx: Transaction) -> None:
        db.delete(tx)

