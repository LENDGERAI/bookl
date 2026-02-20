from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from booklify.core.country_rules import get_country_profile
from booklify.core.database import SessionLocal
from booklify.core.i18n import tr
from booklify.core.security import SecurityService
from booklify.models import Business, Document, Transaction
from booklify.services.categorization import CategorizationService
from booklify.services.extraction import ExtractedTransaction, ExtractionService
from booklify.services.notifications import NotificationService
from booklify.services.queue import QueueService
from booklify.services.storage import StorageService


@dataclass(slots=True)
class UploadPayload:
    filename: str
    content_type: str
    content: bytes


class WorkflowService:
    def __init__(
        self,
        queue_service: QueueService,
        storage_service: StorageService,
        extraction_service: ExtractionService,
        categorization_service: CategorizationService,
        notification_service: NotificationService,
        security_service: SecurityService,
    ) -> None:
        self.queue_service = queue_service
        self.storage_service = storage_service
        self.extraction_service = extraction_service
        self.categorization_service = categorization_service
        self.notification_service = notification_service
        self.security_service = security_service

    def ingest_documents(
        self,
        db: Session,
        business: Business,
        uploads: list[UploadPayload],
        high_volume_threshold: int = 25,
    ) -> list[Document]:
        if not uploads:
            return []
        results: list[Document] = []

        self.notification_service.on_upload_batch(
            db,
            business.id,
            business.language,
            len(uploads),
            threshold=high_volume_threshold,
        )

        for upload in uploads:
            stored = self.storage_service.persist(
                business.id,
                upload.filename,
                upload.content,
                upload.content_type,
            )
            existing = db.scalar(
                select(Document).where(
                    Document.business_id == business.id,
                    Document.file_hash == stored.file_hash,
                )
            )
            if existing:
                self.notification_service.create(
                    db,
                    business.id,
                    level="info",
                    kind="duplicate_document",
                    message=tr(business.language, "duplicate_document"),
                )
                results.append(existing)
                continue

            next_version = (
                db.scalar(
                    select(func.coalesce(func.max(Document.version), 0)).where(
                        Document.business_id == business.id,
                        Document.filename == stored.normalized_filename,
                    )
                )
                or 0
            ) + 1
            document = Document(
                business_id=business.id,
                filename=stored.normalized_filename,
                content_type=stored.content_type,
                file_hash=stored.file_hash,
                storage_path=str(stored.path),
                status="queued",
                version=next_version,
            )
            db.add(document)
            db.flush()
            results.append(document)
        return results

    def queue_document(self, document_id: str) -> None:
        self.queue_service.enqueue(self.process_document, document_id)

    def process_document(self, document_id: str) -> None:
        with SessionLocal() as db:
            document = db.scalar(select(Document).where(Document.id == document_id))
            if not document:
                return
            business = db.scalar(select(Business).where(Business.id == document.business_id))
            if not business:
                return
            country_profile = get_country_profile(business.country, currency_override=business.base_currency)

            try:
                document.status = "processing"
                db.add(document)
                db.commit()

                extracted = self.extraction_service.extract(Path(document.storage_path), country_profile)
                if not extracted:
                    document.status = "review_required"
                    document.error_message = "No transaction data extracted."
                    document.processed_at = datetime.utcnow()
                    db.add(document)
                    self.notification_service.create(
                        db,
                        business.id,
                        level="warning",
                        kind="missing_data",
                        message="No usable transaction fields were found in this document.",
                    )
                    db.commit()
                    return

                raw_for_audit: list[dict[str, Any]] = []
                for record in extracted:
                    decision = self.categorization_service.categorize(db, business, country_profile, record)
                    tx = self._to_transaction(document, record, decision)
                    db.add(tx)
                    db.flush()
                    self.notification_service.on_transaction_created(
                        db,
                        business.id,
                        business.language,
                        country_profile,
                        tx,
                    )
                    raw_for_audit.append(record.raw | {"line_items": record.line_items})

                document.status = "processed"
                document.error_message = None
                document.processed_at = datetime.utcnow()
                document.extracted_payload_encrypted = self.security_service.encrypt_text(
                    json.dumps(raw_for_audit, default=self._json_default)
                )
                db.add(document)
                self.notification_service.create_deadline_reminders(
                    db,
                    business.id,
                    business.language,
                    country_profile,
                )
                self.notification_service.receivable_reminders(db, business.id)
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                document = db.scalar(select(Document).where(Document.id == document_id))
                if document:
                    document.status = "failed"
                    document.error_message = str(exc)[:1000]
                    document.processed_at = datetime.utcnow()
                    db.add(document)
                    db.commit()

    @staticmethod
    def _to_transaction(document: Document, extracted: ExtractedTransaction, decision: Any) -> Transaction:
        return Transaction(
            business_id=document.business_id,
            document_id=document.id,
            tx_type=decision.tx_type,
            category=decision.category,
            description=extracted.description,
            counterparty=extracted.counterparty,
            reference_number=extracted.reference_number,
            occurred_on=extracted.occurred_on,
            amount=float(extracted.amount),
            tax_amount=float(extracted.tax_amount),
            currency=(extracted.currency or "USD").upper(),
            payment_method=extracted.payment_method,
            confidence=decision.confidence,
            needs_review=decision.needs_review,
            source="upload",
            raw_payload_json=json.dumps(
                {"raw": extracted.raw, "line_items": extracted.line_items},
                default=WorkflowService._json_default,
            ),
        )

    @staticmethod
    def _json_default(value: Any) -> str:
        if isinstance(value, (datetime, Decimal)):
            return str(value)
        return str(value)

