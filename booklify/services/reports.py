from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Any

from openpyxl import Workbook

from booklify.models import Transaction

REPORT_COLUMNS = [
    "TransactionID",
    "Date",
    "Type",
    "Category",
    "Description",
    "Counterparty",
    "Reference",
    "Amount",
    "Tax",
    "Currency",
    "PaymentMethod",
    "Confidence",
    "NeedsReview",
    "Source",
]


class ReportService:
    def _row(self, tx: Transaction) -> dict[str, Any]:
        return {
            "TransactionID": tx.id,
            "Date": tx.occurred_on.isoformat() if isinstance(tx.occurred_on, date) else "",
            "Type": tx.tx_type,
            "Category": tx.category,
            "Description": tx.description or "",
            "Counterparty": tx.counterparty or "",
            "Reference": tx.reference_number or "",
            "Amount": str(Decimal(str(tx.amount)).quantize(Decimal("0.01"))),
            "Tax": str(Decimal(str(tx.tax_amount)).quantize(Decimal("0.01"))),
            "Currency": tx.currency,
            "PaymentMethod": tx.payment_method or "",
            "Confidence": f"{tx.confidence:.2f}",
            "NeedsReview": "YES" if tx.needs_review else "NO",
            "Source": tx.source,
        }

    def generate_csv(self, transactions: list[Transaction]) -> bytes:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        for tx in transactions:
            writer.writerow(self._row(tx))
        return buf.getvalue().encode("utf-8")

    def generate_xlsx(self, transactions: list[Transaction]) -> bytes:
        workbook = Workbook()
        all_sheet = workbook.active
        all_sheet.title = "All Transactions"
        self._write_sheet(all_sheet, transactions)

        typed = {
            "Income": [tx for tx in transactions if tx.tx_type == "income"],
            "Expenses": [tx for tx in transactions if tx.tx_type in {"expense", "marketing", "payroll", "tax"}],
            "Receivables": [tx for tx in transactions if tx.tx_type == "receivable"],
            "Payables": [tx for tx in transactions if tx.tx_type == "payable"],
        }
        for name, items in typed.items():
            sheet = workbook.create_sheet(title=name)
            self._write_sheet(sheet, items)

        out = io.BytesIO()
        workbook.save(out)
        return out.getvalue()

    def _write_sheet(self, sheet: Any, transactions: list[Transaction]) -> None:
        sheet.append(REPORT_COLUMNS)
        for tx in transactions:
            row = self._row(tx)
            sheet.append([row[col] for col in REPORT_COLUMNS])

