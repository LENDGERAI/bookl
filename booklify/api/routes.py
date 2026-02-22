from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from booklify.core.config import Settings, get_settings
from booklify.core.country_rules import get_country_profile, list_supported_countries
from booklify.core.database import get_db
from booklify.core.i18n import tr
from booklify.models import Business, Document, Notification, Transaction
from booklify.schemas import (
    BusinessCreate,
    BusinessRead,
    ChatRequest,
    ChatResponse,
    CorrectionRequest,
    DocumentRead,
    NotificationRead,
    SnapshotResponse,
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
    UploadDocumentsResponse,
)
from booklify.services.container import ServiceContainer
from booklify.services.workflows import UploadPayload

router = APIRouter()


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


def get_business_or_404(db: Session, business_id: str) -> Business:
    business = db.scalar(select(Business).where(Business.id == business_id))
    if not business:
        raise HTTPException(status_code=404, detail="Business not found.")
    return business


def get_transaction_or_404(db: Session, tx_id: str) -> Transaction:
    tx = db.scalar(select(Transaction).where(Transaction.id == tx_id))
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return tx


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/countries")
def countries() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for code in list_supported_countries():
        profile = get_country_profile(code)
        items.append({"code": code, "name": profile.name, "currency": profile.currency})
    return items


@router.post("/businesses", response_model=BusinessRead, status_code=status.HTTP_201_CREATED)
def create_business(
    payload: BusinessCreate,
    db: Session = Depends(get_db),
) -> Business:
    profile = get_country_profile(payload.country)
    business = Business(
        name=payload.name,
        country=payload.country,
        language=payload.language,
        base_currency=(payload.base_currency or profile.currency).upper(),
    )
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


@router.get("/businesses/{business_id}", response_model=BusinessRead)
def get_business(
    business_id: str,
    db: Session = Depends(get_db),
) -> Business:
    return get_business_or_404(db, business_id)


@router.post("/businesses/{business_id}/documents/upload", response_model=UploadDocumentsResponse)
async def upload_documents(
    business_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    services: ServiceContainer = Depends(get_services),
) -> UploadDocumentsResponse:
    business = get_business_or_404(db, business_id)
    if len(files) > settings.max_upload_files:
        raise HTTPException(status_code=400, detail=tr(business.language, "upload_limit_error"))

    payloads: list[UploadPayload] = []
    for file in files:
        content = await file.read()
        payloads.append(
            UploadPayload(
                filename=file.filename or "unknown",
                content_type=file.content_type or "application/octet-stream",
                content=content,
            )
        )

    try:
        docs = services.workflow.ingest_documents(
            db,
            business,
            payloads,
            high_volume_threshold=settings.high_volume_upload_threshold,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for doc in docs:
        if doc.status == "queued":
            services.workflow.queue_document(doc.id)

    db.expire_all()
    hydrated = [db.scalar(select(Document).where(Document.id == doc.id)) or doc for doc in docs]
    return UploadDocumentsResponse(message=tr(business.language, "document_uploaded"), documents=hydrated)


@router.get("/businesses/{business_id}/documents", response_model=list[DocumentRead])
def list_documents(
    business_id: str,
    db: Session = Depends(get_db),
) -> list[Document]:
    get_business_or_404(db, business_id)
    return db.scalars(
        select(Document).where(Document.business_id == business_id).order_by(Document.uploaded_at.desc())
    ).all()


@router.post("/documents/{document_id}/process")
def process_document(
    document_id: str,
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, str]:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    services.workflow.queue_document(document.id)
    return {"status": "queued"}


@router.post("/documents/{document_id}/rollback")
def rollback_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    current_doc = db.scalar(select(Document).where(Document.id == document_id))
    if not current_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    previous_doc = db.scalar(
        select(Document)
        .where(
            Document.business_id == current_doc.business_id,
            Document.filename == current_doc.filename,
            Document.version < current_doc.version,
        )
        .order_by(Document.version.desc())
    )
    if not previous_doc:
        raise HTTPException(status_code=404, detail="No previous version available.")

    previous_transactions = db.scalars(
        select(Transaction).where(Transaction.document_id == previous_doc.id)
    ).all()
    restored = 0
    for tx in previous_transactions:
        cloned = Transaction(
            business_id=tx.business_id,
            document_id=current_doc.id,
            tx_type=tx.tx_type,
            category=tx.category,
            description=tx.description,
            counterparty=tx.counterparty,
            reference_number=tx.reference_number,
            occurred_on=tx.occurred_on,
            amount=float(Decimal(str(tx.amount))),
            tax_amount=float(Decimal(str(tx.tax_amount))),
            currency=tx.currency,
            payment_method=tx.payment_method,
            confidence=0.95,
            needs_review=False,
            source="rollback",
            raw_payload_json=tx.raw_payload_json,
        )
        db.add(cloned)
        restored += 1
    current_doc.status = "rolled_back"
    current_doc.processed_at = datetime.now(timezone.utc)
    db.add(current_doc)
    db.commit()
    return {"restored_transactions": restored, "from_version": previous_doc.version, "to_version": current_doc.version}


@router.post("/businesses/{business_id}/transactions", response_model=TransactionRead, status_code=201)
def create_transaction(
    business_id: str,
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> Transaction:
    business = get_business_or_404(db, business_id)
    country_profile = get_country_profile(business.country, currency_override=business.base_currency)
    tx = services.transactions.create_manual(db, business, country_profile, payload)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/businesses/{business_id}/transactions", response_model=list[TransactionRead])
def list_transactions(
    business_id: str,
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> list[Transaction]:
    get_business_or_404(db, business_id)
    return services.transactions.list_for_business(db, business_id)


@router.patch("/transactions/{tx_id}", response_model=TransactionRead)
def update_transaction(
    tx_id: str,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> Transaction:
    tx = get_transaction_or_404(db, tx_id)
    updated = services.transactions.update(db, tx, payload)
    db.commit()
    db.refresh(updated)
    return updated


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(
    tx_id: str,
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> None:
    tx = get_transaction_or_404(db, tx_id)
    services.transactions.delete(db, tx)
    db.commit()
    return None


@router.post("/transactions/{tx_id}/corrections", response_model=TransactionRead)
def correct_transaction_category(
    tx_id: str,
    payload: CorrectionRequest,
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> Transaction:
    tx = get_transaction_or_404(db, tx_id)
    tx.category = payload.category
    tx.needs_review = False
    tx.confidence = max(tx.confidence, 0.95)
    services.categorization.apply_feedback(db, tx.business_id, tx, payload.category)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/businesses/{business_id}/notifications", response_model=list[NotificationRead])
def list_notifications(
    business_id: str,
    db: Session = Depends(get_db),
) -> list[Notification]:
    get_business_or_404(db, business_id)
    return db.scalars(
        select(Notification).where(Notification.business_id == business_id).order_by(Notification.created_at.desc())
    ).all()


@router.get("/businesses/{business_id}/snapshot", response_model=SnapshotResponse)
def financial_snapshot(
    business_id: str,
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, object]:
    business = get_business_or_404(db, business_id)
    return services.advisory.snapshot(db, business)


@router.get("/businesses/{business_id}/exports")
def export_transactions(
    business_id: str,
    export_format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> Response:
    get_business_or_404(db, business_id)
    transactions = services.transactions.list_for_business(db, business_id)
    if export_format == "csv":
        payload = services.reports.generate_csv(transactions)
        filename = "booklify_transactions.csv"
        media_type = "text/csv"
    else:
        payload = services.reports.generate_xlsx(transactions)
        filename = "booklify_transactions.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/businesses/{business_id}/chat", response_model=ChatResponse)
def chat(
    business_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, object]:
    business = get_business_or_404(db, business_id)
    country_profile = get_country_profile(business.country, currency_override=business.base_currency)
    response = services.chatbot.handle(db, business, country_profile, payload.message)
    db.commit()
    return response

