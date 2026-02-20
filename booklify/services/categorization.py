from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from booklify.core.country_rules import CountryProfile
from booklify.models import Business, CategorizationFeedback, Transaction
from booklify.services.extraction import ExtractedTransaction


GLOBAL_KEYWORDS: dict[str, str] = {
    "rent": "Rent",
    "salary": "Payroll",
    "payroll": "Payroll",
    "ad": "Marketing",
    "ads": "Marketing",
    "hosting": "Software",
    "software": "Software",
    "subscription": "Software",
    "office": "Office Supplies",
    "stationery": "Office Supplies",
    "travel": "Travel",
    "flight": "Travel",
    "tax": "Tax",
    "vat": "Tax",
    "gst": "Tax",
    "consulting": "Consulting Income",
    "retainer": "Retainer Income",
    "invoice": "Service Income",
}


@dataclass(slots=True)
class CategorizationResult:
    tx_type: str
    category: str
    confidence: float
    needs_review: bool


class CategorizationService:
    def categorize(
        self,
        db: Session,
        business: Business,
        country_profile: CountryProfile,
        extracted: ExtractedTransaction,
    ) -> CategorizationResult:
        if extracted.category:
            guessed_type = self._resolve_type(extracted.tx_type, extracted.category)
            confidence = min(0.99, extracted.confidence_hint + 0.09)
            return CategorizationResult(guessed_type, extracted.category, confidence, confidence < 0.65)

        text = f"{extracted.description or ''} {extracted.counterparty or ''}".lower()
        words = re.findall(r"[a-zA-Z]{3,}", text)

        scores: dict[str, float] = {}
        for word in words:
            if category := GLOBAL_KEYWORDS.get(word):
                scores[category] = scores.get(category, 0.0) + 1.0
            if category := country_profile.expense_keywords.get(word):
                scores[category] = scores.get(category, 0.0) + 1.1
            if category := country_profile.income_keywords.get(word):
                scores[category] = scores.get(category, 0.0) + 1.1

        feedback_items = db.scalars(
            select(CategorizationFeedback).where(CategorizationFeedback.business_id == business.id)
        ).all()
        for entry in feedback_items:
            if entry.keyword.lower() in text:
                scores[entry.category] = scores.get(entry.category, 0.0) + entry.weight * 0.35

        pattern_category = self._lookup_historical_category(db, business.id, extracted.counterparty)
        if pattern_category:
            scores[pattern_category] = scores.get(pattern_category, 0.0) + 1.3

        if not scores:
            fallback = "Service Income" if extracted.tx_type == "income" else "Uncategorized"
            confidence = max(0.35, extracted.confidence_hint)
            tx_type = self._resolve_type(extracted.tx_type, fallback)
            return CategorizationResult(tx_type, fallback, confidence, True)

        best_category, best_score = sorted(scores.items(), key=lambda item: item[1], reverse=True)[0]
        score_base = min(1.0, math.log1p(best_score) / 2.0)
        confidence = min(0.98, max(extracted.confidence_hint, 0.42) + score_base * 0.5)

        if extracted.counterparty and pattern_category == best_category:
            confidence = min(0.99, confidence + 0.1)

        tx_type = self._resolve_type(extracted.tx_type, best_category)
        needs_review = confidence < 0.65 or extracted.occurred_on is None
        return CategorizationResult(tx_type, best_category, round(confidence, 2), needs_review)

    def apply_feedback(self, db: Session, business_id: str, transaction: Transaction, category: str) -> None:
        text = f"{transaction.description or ''} {transaction.counterparty or ''}".lower()
        keywords = {word for word in re.findall(r"[a-zA-Z]{4,}", text)}
        if not keywords:
            return
        for keyword in sorted(keywords)[:8]:
            entry = db.scalar(
                select(CategorizationFeedback).where(
                    CategorizationFeedback.business_id == business_id,
                    CategorizationFeedback.keyword == keyword,
                    CategorizationFeedback.category == category,
                )
            )
            if entry:
                entry.weight += 1
            else:
                db.add(
                    CategorizationFeedback(
                        business_id=business_id,
                        keyword=keyword,
                        category=category,
                        weight=1,
                    )
                )

    def _lookup_historical_category(self, db: Session, business_id: str, counterparty: str | None) -> str | None:
        if not counterparty:
            return None
        statement: Select[tuple[str, int]] = (
            select(Transaction.category, func.count(Transaction.id))
            .where(Transaction.business_id == business_id, Transaction.counterparty == counterparty)
            .group_by(Transaction.category)
            .order_by(func.count(Transaction.id).desc())
            .limit(1)
        )
        row = db.execute(statement).first()
        return row[0] if row else None

    @staticmethod
    def _resolve_type(extracted_type: str | None, category: str) -> str:
        if extracted_type in {"income", "expense", "receivable", "payable", "payroll", "marketing", "tax"}:
            return extracted_type
        category_lower = category.lower()
        if "income" in category_lower:
            return "income"
        if "payroll" in category_lower:
            return "payroll"
        if "marketing" in category_lower:
            return "marketing"
        if "tax" in category_lower:
            return "tax"
        return "expense"

