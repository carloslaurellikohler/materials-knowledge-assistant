import argparse

from app.services.ingestion import reindex_books


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reindex closed corpus from backend/livros into Qdrant")
    parser.add_argument("--limit", type=int, default=None, help="Max number of PDFs to process")
    parser.add_argument("--offset", type=int, default=0, help="Skip initial N PDFs from sorted list")
    parser.add_argument("--batch-size", type=int, default=128, help="Qdrant upsert batch size")
    parser.add_argument("--recreate", action="store_true", help="Recreate collection before indexing")
    parser.add_argument(
        "--checkpoint-file",
        type=str,
        default=".reindex/checkpoint.json",
        help="Checkpoint JSON path for resume support",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--quiet", action="store_true", help="Disable progress logs")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = reindex_books(
        limit=args.limit,
        offset=args.offset,
        batch_size=args.batch_size,
        recreate=args.recreate,
        checkpoint_file=args.checkpoint_file,
        resume=args.resume,
        verbose=not args.quiet,
    )
    print(result)
