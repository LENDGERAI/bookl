from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from booklify.core.i18n import tr
from booklify.models import Business, Transaction


class AdvisoryService:
    def snapshot(self, db: Session, business: Business) -> dict[str, object]:
        rows = db.scalars(select(Transaction).where(Transaction.business_id == business.id)).all()

        income_types = {"income", "receivable"}
        expense_types = {"expense", "payable", "payroll", "marketing", "tax"}

        total_income = Decimal("0")
        total_expense = Decimal("0")
        receivables = Decimal("0")
        payables = Decimal("0")
        expense_breakdown: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        for tx in rows:
            amount = Decimal(str(tx.amount))
            if tx.tx_type in income_types:
                total_income += amount
            if tx.tx_type in expense_types:
                total_expense += amount
                expense_breakdown[tx.category] += amount
            if tx.tx_type == "receivable":
                receivables += amount
            if tx.tx_type == "payable":
                payables += amount

        net_profit = total_income - total_expense
        cash_in = total_income - receivables
        cash_out = total_expense - payables

        advisory = self._build_advisory(
            language=business.language,
            net_profit=net_profit,
            cash_in=cash_in,
            cash_out=cash_out,
            receivables=receivables,
            payables=payables,
        )

        return {
            "currency": business.base_currency,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_profit": net_profit,
            "cash_in": cash_in,
            "cash_out": cash_out,
            "receivables": receivables,
            "payables": payables,
            "expense_breakdown": dict(sorted(expense_breakdown.items(), key=lambda item: item[1], reverse=True)),
            "advisory": advisory,
            "message": tr(business.language, "snapshot_ready"),
        }

    @staticmethod
    def _build_advisory(
        *,
        language: str,
        net_profit: Decimal,
        cash_in: Decimal,
        cash_out: Decimal,
        receivables: Decimal,
        payables: Decimal,
    ) -> list[str]:
        french = language.lower() == "fr"
        advice: list[str] = []

        if net_profit < 0:
            advice.append(
                "Vos depenses depassent vos revenus. Envisagez de reporter certaines depenses discretes."
                if french
                else "Expenses are currently higher than income. Consider delaying discretionary expenses."
            )
        if receivables > payables * Decimal("1.5") and receivables > Decimal("0"):
            advice.append(
                "Vos creances sont elevees. Relancez les factures en retard pour proteger la tresorerie."
                if french
                else "Receivables are high. Follow up on overdue invoices to protect cash flow."
            )
        if cash_out > cash_in:
            advice.append(
                "Les sorties de tresorerie depassent les entrees. Surveillez les depenses hebdomadaires."
                if french
                else "Cash outflow is above inflow. Track weekly spending closely."
            )
        if not advice:
            advice.append(
                "Situation financiere stable. Continuez a surveiller la marge et les taxes."
                if french
                else "Financial position looks stable. Keep monitoring margin and taxes."
            )
        return advice

