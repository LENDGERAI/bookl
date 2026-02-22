from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "business_created": "Business profile created successfully.",
        "document_uploaded": "Document uploaded and queued for processing.",
        "duplicate_document": "Duplicate document detected and skipped.",
        "processing_failed": "Document processing failed.",
        "upload_limit_error": "Upload limit exceeded.",
        "chat_unknown": "I can help with transactions, summaries, reminders, and insights.",
        "chat_add_success": "Transaction added.",
        "chat_update_success": "Transaction updated.",
        "chat_delete_success": "Transaction deleted.",
        "snapshot_ready": "Financial snapshot generated.",
        "low_confidence": "This transaction needs review due to low confidence.",
        "high_upload_volume": "High upload volume detected.",
        "tax_liability_warning": "Estimated tax liability requires attention.",
    },
    "fr": {
        "business_created": "Profil d'entreprise cree avec succes.",
        "document_uploaded": "Document televerse et mis en file de traitement.",
        "duplicate_document": "Document en double detecte et ignore.",
        "processing_failed": "Le traitement du document a echoue.",
        "upload_limit_error": "Limite de televersement depassee.",
        "chat_unknown": "Je peux aider avec les transactions, les resumes et les rappels.",
        "chat_add_success": "Transaction ajoutee.",
        "chat_update_success": "Transaction mise a jour.",
        "chat_delete_success": "Transaction supprimee.",
        "snapshot_ready": "Apercu financier genere.",
        "low_confidence": "Cette transaction doit etre verifiee (faible confiance).",
        "high_upload_volume": "Volume eleve de televersements detecte.",
        "tax_liability_warning": "La charge fiscale estimee requiert votre attention.",
    },
}


def tr(language: str, key: str, **kwargs: object) -> str:
    selected = language.lower() if language else "en"
    template = MESSAGES.get(selected, MESSAGES["en"]).get(key) or MESSAGES["en"].get(key, key)
    return template.format(**kwargs)

