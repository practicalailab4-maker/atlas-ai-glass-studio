from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from backend.invoice_schema import InvoiceData


def money(value: float) -> Decimal:
    """Convert a monetary value to two decimal places."""
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def validate_invoice(invoice: InvoiceData) -> list[str]:
    """Return a list of invoice calculation problems."""

    issues = []
    calculated_subtotal = Decimal("0.00")

    if invoice.due_date:
        try:
            invoice_date = date.fromisoformat(invoice.invoice_date)
            due_date = date.fromisoformat(invoice.due_date)

            if due_date < invoice_date:
                issues.append(
                    f"Due date {invoice.due_date} is earlier than "
                    f"invoice date {invoice.invoice_date}"
                )
        except ValueError:
            issues.append("Invalid invoice date or due date format")

    for index, item in enumerate(invoice.line_items, start=1):
        expected_amount = money(
            Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
        )

        actual_amount = money(item.amount)

        if expected_amount != actual_amount:
            issues.append(
                f"Line {index} ({item.description}): "
                f"expected {expected_amount}, found {actual_amount}"
            )

        calculated_subtotal += actual_amount

    if calculated_subtotal != money(invoice.subtotal):
        issues.append(
            f"Subtotal mismatch: expected {calculated_subtotal}, "
            f"found {money(invoice.subtotal)}"
        )

    expected_total = money(
        Decimal(str(invoice.subtotal))
        - Decimal(str(invoice.discount))
        + Decimal(str(invoice.tax))
    )

    if expected_total != money(invoice.total):
        issues.append(
            f"Total mismatch: expected {expected_total}, "
            f"found {money(invoice.total)}"
        )

    return issues