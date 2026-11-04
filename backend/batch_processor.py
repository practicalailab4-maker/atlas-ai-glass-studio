import sqlite3
from pathlib import Path


from backend.database import DATA_DIR, DATABASE_PATH
from backend.invoice_processor import process_invoice

BATCH_DIR = DATA_DIR / "batch_invoices"

def already_processed(pdf_path: Path) -> bool:
    with sqlite3.connect(DATABASE_PATH) as connection:
        row = connection.execute(
            "SELECT 1 FROM invoices WHERE source_file = ? LIMIT 1",
            (str(pdf_path),)
        ).fetchone()
        return row is not None

def process_batch(limit: int | None = None):
    pdf_files = sorted(BATCH_DIR.rglob("*.pdf"))

    if limit is not None:
        pdf_files = pdf_files[:limit]


    print(f"Atlas found {len(pdf_files)} PDF invoices.")
    successful = 0
    failed = 0
    duplicates = 0
    for pdf_path in pdf_files:
        print(f"Processing: {pdf_path.name}")
        if already_processed(pdf_path):
            duplicates += 1
            continue
        try:
            invoice_id = process_invoice(str(pdf_path))
            successful += 1
            print(f"Saved invoice ID: {invoice_id}")
        except sqlite3.IntegrityError:
            duplicates += 1
            print(f"Duplicate skipped: {pdf_path.name}")
        except Exception as error:
            failed += 1
            print(f"Failed: {pdf_path.name} — {error}")

    print(f"Batch complete: {successful} saved, {duplicates} duplicates, {failed} failed.")