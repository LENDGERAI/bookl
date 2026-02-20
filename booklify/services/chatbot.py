from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from booklify.core.country_rules import CountryProfile
from booklify.core.i18n import tr
from booklify.models import Business, ChatPreference, Notification
from booklify.schemas import TransactionCreate, TransactionRead, TransactionUpdate
from booklify.services.advisory import AdvisoryService
from booklify.services.transactions import TransactionService


class ChatbotService:
    def __init__(self, transaction_service: TransactionService, advisory_service: AdvisoryService) -> None:
        self.transaction_service = transaction_service
        self.advisory_service = advisory_service

    def handle(self, db: Session, business: Business, country_profile: CountryProfile, message: str) -> dict[str, object]:
        normalized = message.strip()
        lower = normalized.lower()
        self._remember(db, business.id, "last_intent_hint", lower[:80])

        add_match = re.search(
            r"add\s+(income|expense|receivable|payable|payroll|marketing|tax)\s+([0-9]+(?:\.[0-9]{1,2})?)(?:\s+(.+))?",
            lower,
        )
        if add_match:
            tx_type = add_match.group(1)
            amount = Decimal(add_match.group(2))
            tail = add_match.group(3) or ""
            category = self._capture(tail, r"category\s+([a-zA-Z ]+?)(?:\s+(?:from|to)\b|$)")
            counterparty = self._capture(tail, r"(?:from|to)\s+([a-zA-Z0-9 ._-]+)")
            payload = TransactionCreate(
                tx_type=tx_type,  # type: ignore[arg-type]
                amount=amount,
                currency=business.base_currency,
                description=tail or f"Added by chat ({tx_type})",
                category=category,
                counterparty=counterparty,
                source="chat",
            )
            tx = self.transaction_service.create_manual(db, business, country_profile, payload)
            return {
                "reply": tr(business.language, "chat_add_success"),
                "actions": [f"created:{tx.id}"],
                "transactions": [TransactionRead.model_validate(tx)],
            }

        update_match = re.search(r"(?:update|modify)\s+transaction\s+([a-zA-Z0-9-]+)\s+(.+)", lower)
        if update_match:
            tx_id = update_match.group(1)
            update_tail = update_match.group(2)
            tx = self.transaction_service.get(db, tx_id)
            if not tx or tx.business_id != business.id:
                return {"reply": "Transaction not found.", "actions": [], "transactions": []}
            amount_text = self._capture(update_tail, r"amount\s+([0-9]+(?:\.[0-9]{1,2})?)")
            category = self._capture(update_tail, r"category\s+([a-zA-Z ]+)$")
            updates = {}
            if amount_text:
                updates["amount"] = Decimal(amount_text)
            if category:
                updates["category"] = category
            if not updates:
                return {"reply": "No update fields detected.", "actions": [], "transactions": []}
            updated = self.transaction_service.update(db, tx, TransactionUpdate(**updates))
            return {
                "reply": tr(business.language, "chat_update_success"),
                "actions": [f"updated:{updated.id}"],
                "transactions": [TransactionRead.model_validate(updated)],
            }

        delete_match = re.search(r"(?:delete|remove)\s+transaction\s+([a-zA-Z0-9-]+)", lower)
        if delete_match:
            tx_id = delete_match.group(1)
            tx = self.transaction_service.get(db, tx_id)
            if not tx or tx.business_id != business.id:
                return {"reply": "Transaction not found.", "actions": [], "transactions": []}
            self.transaction_service.delete(db, tx)
            return {
                "reply": tr(business.language, "chat_delete_success"),
                "actions": [f"deleted:{tx_id}"],
                "transactions": [],
            }

        if any(word in lower for word in ("snapshot", "summary", "profit", "cash flow", "cashflow")):
            snapshot = self.advisory_service.snapshot(db, business)
            summary = (
                f"{snapshot['message']} Net profit: {snapshot['net_profit']} {snapshot['currency']}. "
                f"Cash in/out: {snapshot['cash_in']}/{snapshot['cash_out']}."
            )
            return {"reply": summary, "actions": ["snapshot"], "transactions": []}

        if any(word in lower for word in ("notifications", "alerts", "reminders")):
            rows = db.scalars(
                select(Notification).where(Notification.business_id == business.id).order_by(Notification.created_at.desc())
            ).all()
            if not rows:
                return {"reply": "No alerts right now.", "actions": ["notifications"], "transactions": []}
            lines = [f"- [{row.level}] {row.message}" for row in rows[:5]]
            return {"reply": "Recent alerts:\n" + "\n".join(lines), "actions": ["notifications"], "transactions": []}

        pref_match = re.search(r"prefer\s+currency\s+([A-Z]{3})", normalized)
        if pref_match:
            self._remember(db, business.id, "preferred_currency", pref_match.group(1))
            return {"reply": "Preference saved.", "actions": ["preference"], "transactions": []}

        return {"reply": tr(business.language, "chat_unknown"), "actions": [], "transactions": []}

    @staticmethod
    def _capture(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def _remember(db: Session, business_id: str, key: str, value: str) -> None:
        entry = db.scalar(
            select(ChatPreference).where(ChatPreference.business_id == business_id, ChatPreference.key == key)
        )
        if entry:
            entry.value = value
            db.add(entry)
        else:
            db.add(ChatPreference(business_id=business_id, key=key, value=value))

