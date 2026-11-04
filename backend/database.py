import sqlite3
from pathlib import Path


from importlib import import_module

from backend.invoice_schema import InvoiceData
from backend.invoice_validator import money

# Store the database in a local data folder
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "atlas.db"


def initialize_database():
    """Create the Atlas database and invoices table."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_name TEXT NOT NULL,
                invoice_number TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                due_date TEXT,
                bill_to TEXT,
                currency TEXT NOT NULL,
                subtotal TEXT NOT NULL,
                tax TEXT NOT NULL,
                total TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'needs_review',
                source_file TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(vendor_name, invoice_number)
            )
        """)


        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoice_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                quantity TEXT NOT NULL,
                unit_price TEXT NOT NULL,
                amount TEXT NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
                    ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoice_validation_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                issue_message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
                    ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoice_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
                    ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS ap_review_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_reviewed_at TEXT
            )
        """)
        # Add V22 columns to new and existing databases.
        existing_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(invoices)")
        }

        required_columns = {
            "discount": "TEXT NOT NULL DEFAULT '0.00'",
            "paid_at": "TEXT",
            "payment_reference": "TEXT",
        }

        for column_name, column_definition in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE invoices ADD COLUMN "
                    f"{column_name} {column_definition}"
                )

        connection.commit()

        from backend.invoice_schema import InvoiceData
from backend.invoice_validator import money


def save_invoice(
    invoice: InvoiceData,
    source_file: str,
    status: str = "needs_review",
    validation_issues: list[str] | None = None,
) -> int:
    """Save an extracted invoice and return its database ID."""

    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO invoices (
                vendor_name, invoice_number, invoice_date,
                due_date, bill_to, currency,
                subtotal, discount, tax, total, status, source_file
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice.vendor_name,
                invoice.invoice_number,
                invoice.invoice_date,
                invoice.due_date,
                invoice.bill_to,
                invoice.currency,
                str(money(invoice.subtotal)),
                str(money(invoice.discount)),
                str(money(invoice.tax)),
                str(money(invoice.total)),
                status,
                source_file,
            ),
        )

        invoice_id = cursor.lastrowid

        for item in invoice.line_items:
            connection.execute(
                """
                INSERT INTO invoice_line_items (
                    invoice_id, description, quantity,
                    unit_price, amount
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    item.description,
                    str(item.quantity),
                    str(money(item.unit_price)),
                    str(money(item.amount)),
                ),
            )
        for issue in validation_issues or []:
            connection.execute(
                """
                INSERT INTO invoice_validation_issues (
                    invoice_id, issue_message
                )
                VALUES (?, ?)
                """,
                (invoice_id, issue),
            )
        connection.execute(
            """
            INSERT INTO invoice_activity (invoice_id, action, details)
            VALUES (?, ?, ?)
            """,
            (invoice_id, "uploaded", f"Invoice uploaded from {source_file}")
        )
        connection.commit()



    excel_export = import_module("backend.excel_export")
    excel_export.create_excel_workbook()

    return invoice_id

def list_invoices():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
    """
    SELECT
        invoices.*,
        (
            SELECT COUNT(*)
            FROM invoice_validation_issues
            WHERE invoice_validation_issues.invoice_id = invoices.id
        ) AS validation_issue_count
    FROM invoices
    ORDER BY invoices.id DESC
    """
).fetchall()

        return [dict(row) for row in rows]

def get_invoice(invoice_id: int):
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()



        if row is None:
            return None

        invoice = dict(row)

        issues = connection.execute(
            """
            SELECT issue_message
            FROM invoice_validation_issues
            WHERE invoice_id = ?
            ORDER BY id
            """,
            (invoice_id,),
        ).fetchall()

        invoice["validation_issues"] = [
            issue["issue_message"] for issue in issues
        ]
        activities = connection.execute(
            """
            SELECT action, details, created_at
            FROM invoice_activity
            WHERE invoice_id = ?
            ORDER BY id DESC
            """,
            (invoice_id,),
        ).fetchall()

        invoice["activity_history"] = [
            dict(activity) for activity in activities
        ]
        return invoice



def update_invoice_status(invoice_id: int, status: str, reason: str = ""):
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            """
            UPDATE invoices
            SET status = ?
            WHERE id = ?
            AND status = 'needs_review'
            """,
            (status, invoice_id)
        )

        if cursor.rowcount > 0:
            connection.execute(
                """
                INSERT INTO invoice_activity (invoice_id, action, details)
                VALUES (?, ?, ?)
                """,
                (invoice_id, "status_changed", f"Status changed to {status}" + (f" | Reason: {reason.strip()}" if reason.strip() else ""))
            )

        connection.commit()
        return cursor.rowcount > 0


def mark_invoice_paid(
    invoice_id: int,
    payment_date: str,
    payment_reference: str,
):
    from datetime import date

    # Validate before changing the database.
    try:
        date.fromisoformat(payment_date)
    except ValueError:
        raise ValueError("Payment date must be YYYY-MM-DD")

    payment_reference = payment_reference.strip()
    if not payment_reference:
        raise ValueError("Payment reference is required")

    with sqlite3.connect(DATABASE_PATH) as connection:
        # Prevent two requests from paying the same invoice.
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            "SELECT status FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()

        if row is None:
            raise LookupError("Invoice not found")

        if row[0] == "paid":
            raise ValueError("Invoice is already marked as paid")

        if row[0] != "approved":
            raise ValueError("Only approved invoices can be marked as paid")

        connection.execute(
            """
            UPDATE invoices
            SET status = 'paid',
                paid_at = ?,
                payment_reference = ?
            WHERE id = ?
            """,
            (payment_date, payment_reference, invoice_id),
        )

        connection.execute(
            """
            INSERT INTO invoice_activity (invoice_id, action, details)
            VALUES (?, ?, ?)
            """,
            (
                invoice_id,
                "marked_paid",
                f"Payment date: {payment_date}; "
                f"Reference: {payment_reference}",
            ),
        )

    return {
        "invoice_id": invoice_id,
        "status": "paid",
        "paid_at": payment_date,
        "payment_reference": payment_reference,
    }


def list_invoice_activity_since(since: str) -> list[dict]:
    """Return invoice activity recorded after a UTC timestamp."""

    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                a.id,
                a.invoice_id,
                a.action,
                a.details,
                a.created_at,
                i.invoice_number,
                i.vendor_name
            FROM invoice_activity AS a
            JOIN invoices AS i ON i.id = a.invoice_id
            WHERE a.created_at > ?
            ORDER BY a.created_at DESC, a.id DESC
            """,
            (since,),
        ).fetchall()

    return [dict(row) for row in rows]
def get_last_ap_review() -> str | None:
    """Return the last AP review timestamp, if one exists."""

    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        row = connection.execute(
            """
            SELECT last_reviewed_at
            FROM ap_review_state
            WHERE id = 1
            """
        ).fetchone()

    return row[0] if row else None
def mark_ap_reviewed() -> str:
    """Save the current UTC time as the latest AP review checkpoint."""

    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            INSERT INTO ap_review_state (id, last_reviewed_at)
            VALUES (1, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                last_reviewed_at = excluded.last_reviewed_at
            """
        )

        row = connection.execute(
            """
            SELECT last_reviewed_at
            FROM ap_review_state
            WHERE id = 1
            """
        ).fetchone()

        connection.commit()

    return row[0]