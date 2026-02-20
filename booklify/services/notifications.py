from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from booklify.core.country_rules import CountryProfile
from booklify.core.i18n import tr
from booklify.models import Notification, Transaction


class NotificationService:
    def create(
        self,
        db: Session,
        business_id: str,
        *,
        level: str,
        kind: str,
        message: str,
    ) -> Notification:
        notification = Notification(
            business_id=business_id,
            level=level,
            kind=kind,
            message=message[:500],
        )
        db.add(notification)
        return notification

    def on_upload_batch(
        self,
        db: Session,
        business_id: str,
        language: str,
        uploaded_count: int,
        threshold: int,
    ) -> None:
        if uploaded_count >= threshold:
            self.create(
                db,
                business_id,
                level="warning",
                kind="high_upload_volume",
                message=tr(language, "high_upload_volume"),
            )

    def on_transaction_created(
        self,
        db: Session,
        business_id: str,
        language: str,
        country_profile: CountryProfile,
        tx: Transaction,
    ) -> None:
        amount = float(tx.amount)
        if amount >= country_profile.unusual_amount_threshold:
            self.create(
                db,
                business_id,
                level="warning",
                kind="unusual_transaction",
                message=f"Unusual transaction amount detected: {amount:.2f} {tx.currency}",
            )

        tax_total = db.scalar(
            select(func.coalesce(func.sum(Transaction.tax_amount), 0)).where(
                Transaction.business_id == business_id
            )
        )
        if tax_total and Decimal(str(tax_total)) >= Decimal("5000"):
            self.create(
                db,
                business_id,
                level="warning",
                kind="tax_liability",
                message=tr(language, "tax_liability_warning"),
            )

        if tx.needs_review:
            self.create(
                db,
                business_id,
                level="info",
                kind="review_needed",
                message=tr(language, "low_confidence"),
            )

    def create_deadline_reminders(
        self,
        db: Session,
        business_id: str,
        language: str,
        country_profile: CountryProfile,
    ) -> None:
        now = datetime.utcnow()
        due_this_month = now.replace(day=min(country_profile.tax_deadline_day, 28), hour=0, minute=0, second=0)
        if due_this_month < now:
            due_this_month = (due_this_month + timedelta(days=32)).replace(day=min(country_profile.tax_deadline_day, 28))

        days_left = (due_this_month.date() - now.date()).days
        if 0 <= days_left <= 7:
            self.create(
                db,
                business_id,
                level="warning",
                kind="deadline",
                message=f"Tax filing deadline in {days_left} day(s).",
            )

    def receivable_reminders(self, db: Session, business_id: str) -> None:
        cutoff = datetime.utcnow().date() - timedelta(days=30)
        stale_receivables = db.scalars(
            select(Transaction).where(
                Transaction.business_id == business_id,
                Transaction.tx_type == "receivable",
                Transaction.occurred_on.is_not(None),
                Transaction.occurred_on <= cutoff,
            )
        ).all()
        for tx in stale_receivables[:20]:
            self.create(
                db,
                business_id,
                level="info",
                kind="receivable_reminder",
                message=f"Invoice {tx.reference_number or tx.id} is unpaid for more than 30 days.",
            )

