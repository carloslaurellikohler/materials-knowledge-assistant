from app.services.ingestion import ingest_single_pdf, reindex_books
from app.workers.celery_app import celery_app


@celery_app.task(name="mka.reindex_books")
def reindex_books_task() -> dict:
    return reindex_books()


@celery_app.task(name="mka.ingest_single_pdf")
def ingest_single_pdf_task(pdf_path: str) -> dict:
    return ingest_single_pdf(pdf_path)
