import logging

from sqlalchemy import select

from app.services.ingestion import ingest_pdf_bytes, ingest_single_pdf, reindex_books
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="mka.reindex_books")
def reindex_books_task() -> dict:
    return reindex_books()


@celery_app.task(name="mka.ingest_single_pdf")
def ingest_single_pdf_task(pdf_path: str) -> dict:
    return ingest_single_pdf(pdf_path)


@celery_app.task(name="mka.ingest_document", bind=True, max_retries=3)
def ingest_document_task(self, document_id: str) -> dict:
    from app.db.database import SyncSessionLocal
    from app.db.models import Document
    from app.storage.supabase_provider import get_storage

    def _set_status(session, doc: Document, new_status: str, error: str | None = None) -> None:
        doc.indexing_status = new_status
        if error is not None:
            doc.indexing_error = error
        session.commit()

    with SyncSessionLocal() as session:
        result = session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None:
            logger.error("Document %s not found in DB", document_id)
            return {"error": "document_not_found"}

        user_id = doc.user_id
        filename = doc.original_filename
        storage_path = doc.storage_path

        try:
            _set_status(session, doc, "processing")

            storage = get_storage()
            pdf_bytes = storage.sync_download(storage_path)

            def status_callback(status: str) -> None:
                _set_status(session, doc, status)

            stats = ingest_pdf_bytes(
                pdf_bytes,
                filename,
                user_id=user_id,
                document_id=document_id,
                status_callback=status_callback,
            )

            doc.chunk_count = stats["chunks"]
            _set_status(session, doc, "indexed")

            return stats

        except Exception as exc:
            logger.exception("Failed to ingest document %s: %s", document_id, exc)
            _set_status(session, doc, "error", error=str(exc))
            raise self.retry(exc=exc, countdown=30)
