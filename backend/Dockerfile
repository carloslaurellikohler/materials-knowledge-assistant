FROM python:3.12-slim

RUN groupadd -g 1000 app && useradd -m -u 1000 -g 1000 app

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir --root-user-action=ignore -e .
COPY app ./app
COPY reindex_corpus.py .

USER app

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
