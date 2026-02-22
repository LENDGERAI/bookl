from __future__ import annotations

from dataclasses import dataclass

from booklify.core.config import Settings
from booklify.core.security import SecurityService
from booklify.services.advisory import AdvisoryService
from booklify.services.categorization import CategorizationService
from booklify.services.chatbot import ChatbotService
from booklify.services.extraction import ExtractionService
from booklify.services.notifications import NotificationService
from booklify.services.queue import QueueService
from booklify.services.reports import ReportService
from booklify.services.storage import StorageService
from booklify.services.transactions import TransactionService
from booklify.services.workflows import WorkflowService


@dataclass(slots=True)
class ServiceContainer:
    queue: QueueService
    storage: StorageService
    extraction: ExtractionService
    categorization: CategorizationService
    notifications: NotificationService
    security: SecurityService
    advisory: AdvisoryService
    transactions: TransactionService
    workflow: WorkflowService
    reports: ReportService
    chatbot: ChatbotService

    def shutdown(self) -> None:
        self.queue.shutdown()


def build_services(settings: Settings) -> ServiceContainer:
    queue = QueueService(mode=settings.queue_mode, workers=settings.queue_workers)
    storage = StorageService()
    extraction = ExtractionService()
    categorization = CategorizationService()
    notifications = NotificationService()
    security = SecurityService(settings.encryption_key)
    advisory = AdvisoryService()
    transactions = TransactionService(categorization, notifications)
    workflow = WorkflowService(queue, storage, extraction, categorization, notifications, security)
    reports = ReportService()
    chatbot = ChatbotService(transactions, advisory)
    return ServiceContainer(
        queue=queue,
        storage=storage,
        extraction=extraction,
        categorization=categorization,
        notifications=notifications,
        security=security,
        advisory=advisory,
        transactions=transactions,
        workflow=workflow,
        reports=reports,
        chatbot=chatbot,
    )

