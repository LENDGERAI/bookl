from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from booklify.main import create_app


@pytest.fixture()
def client() -> TestClient:
    db_file = Path("/workspace/booklify.db")
    if db_file.exists():
        db_file.unlink()
    shutil.rmtree("/workspace/uploads", ignore_errors=True)
    shutil.rmtree("/workspace/exports", ignore_errors=True)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _create_business(client: TestClient, *, country: str = "AU", language: str = "en") -> str:
    response = client.post(
        "/api/v1/businesses",
        json={"name": "Freelance Studio", "country": country, "language": language},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_upload_snapshot_and_exports(client: TestClient) -> None:
    business_id = _create_business(client, country="AU", language="en")
    csv_payload = (
        "date,type,description,vendor,invoice_number,amount,tax,currency,payment_method\n"
        "2026-01-10,income,Monthly consulting retainer,Acme Corp,INV-1001,3000.00,300.00,AUD,bank transfer\n"
        "2026-01-11,expense,Officeworks stationery,Officeworks,RCP-9001,120.00,12.00,AUD,card\n"
    )

    upload_response = client.post(
        f"/api/v1/businesses/{business_id}/documents/upload",
        files=[("files", ("jan.csv", csv_payload, "text/csv"))],
    )
    assert upload_response.status_code == 200, upload_response.text
    uploaded_docs = upload_response.json()["documents"]
    assert len(uploaded_docs) == 1
    assert uploaded_docs[0]["status"] in {"queued", "processing", "processed", "review_required"}

    tx_response = client.get(f"/api/v1/businesses/{business_id}/transactions")
    assert tx_response.status_code == 200
    transactions = tx_response.json()
    assert len(transactions) == 2
    assert {row["tx_type"] for row in transactions} == {"income", "expense"}

    snapshot = client.get(f"/api/v1/businesses/{business_id}/snapshot")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["net_profit"] == "2880.00"
    assert payload["currency"] == "AUD"
    assert len(payload["advisory"]) >= 1

    csv_export = client.get(f"/api/v1/businesses/{business_id}/exports?export_format=csv")
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["content-type"]
    assert "TransactionID" in csv_export.text

    xlsx_export = client.get(f"/api/v1/businesses/{business_id}/exports?export_format=xlsx")
    assert xlsx_export.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in xlsx_export.headers["content-type"]
    assert len(xlsx_export.content) > 250


def test_duplicate_detection_creates_alert(client: TestClient) -> None:
    business_id = _create_business(client, country="US", language="en")
    csv_payload = (
        "date,type,description,vendor,invoice_number,amount,tax,currency,payment_method\n"
        "2026-02-01,expense,Stripe fee,Stripe,STR-1,40.00,0.00,USD,card\n"
    )

    first = client.post(
        f"/api/v1/businesses/{business_id}/documents/upload",
        files=[("files", ("fees.csv", csv_payload, "text/csv"))],
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/businesses/{business_id}/documents/upload",
        files=[("files", ("fees_copy.csv", csv_payload, "text/csv"))],
    )
    assert second.status_code == 200

    alerts = client.get(f"/api/v1/businesses/{business_id}/notifications")
    assert alerts.status_code == 200
    kinds = [item["kind"] for item in alerts.json()]
    assert "duplicate_document" in kinds


def test_chatbot_can_add_update_delete_and_summarize(client: TestClient) -> None:
    business_id = _create_business(client, country="FR", language="fr")

    add = client.post(
        f"/api/v1/businesses/{business_id}/chat",
        json={"message": "add expense 50 category Marketing from Meta ads"},
    )
    assert add.status_code == 200
    add_data = add.json()
    assert add_data["actions"][0].startswith("created:")
    tx_id = add_data["transactions"][0]["id"]

    update = client.post(
        f"/api/v1/businesses/{business_id}/chat",
        json={"message": f"update transaction {tx_id} amount 75 category Travel"},
    )
    assert update.status_code == 200
    assert update.json()["actions"][0] == f"updated:{tx_id}"

    summary = client.post(
        f"/api/v1/businesses/{business_id}/chat",
        json={"message": "show snapshot"},
    )
    assert summary.status_code == 200
    assert "Net profit" in summary.json()["reply"]

    delete = client.post(
        f"/api/v1/businesses/{business_id}/chat",
        json={"message": f"remove transaction {tx_id}"},
    )
    assert delete.status_code == 200
    assert delete.json()["actions"][0] == f"deleted:{tx_id}"

    listed = client.get(f"/api/v1/businesses/{business_id}/transactions")
    assert listed.status_code == 200
    assert listed.json() == []


def test_correction_feedback_improves_future_categorization(client: TestClient) -> None:
    business_id = _create_business(client, country="US", language="en")
    first_tx = client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        json={
            "tx_type": "expense",
            "description": "Cloudfoo platform bill",
            "amount": "120.00",
            "tax_amount": "0.00",
            "currency": "USD",
        },
    )
    assert first_tx.status_code == 201
    tx_id = first_tx.json()["id"]

    correction = client.post(
        f"/api/v1/transactions/{tx_id}/corrections",
        json={"category": "Software"},
    )
    assert correction.status_code == 200

    second_tx = client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        json={
            "tx_type": "expense",
            "description": "Cloudfoo monthly renewal",
            "amount": "80.00",
            "tax_amount": "0.00",
            "currency": "USD",
        },
    )
    assert second_tx.status_code == 201
    assert second_tx.json()["category"] == "Software"

