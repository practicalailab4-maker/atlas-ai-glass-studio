from datetime import date

from backend.database import list_invoices


def detect_ap_issues(today: date | None = None) -> list[dict]:
    """Detect actionable AP issues using recorded invoice facts."""

    today = today or date.today()
    issues = []

    for invoice in list_invoices():
        if invoice.get("status") != "needs_review":
            continue

        due_date_text = invoice.get("due_date")
        if not due_date_text:
            continue

        try:
            due_date = date.fromisoformat(due_date_text)
        except (TypeError, ValueError):
            continue

        if due_date >= today:
            continue

        days_past_due = (today - due_date).days

        if days_past_due > 60:
            priority = "high"
        elif days_past_due >= 15:
            priority = "medium"
        else:
            priority = "low"

        issues.append({
            "type": "overdue_review",
            "priority": priority,
            "invoice_id": invoice["id"],
            "invoice_number": invoice.get("invoice_number"),
            "vendor": invoice.get("vendor_name"),
            "amount": invoice.get("total"),
            "currency": invoice.get("currency"),
            "due_date": due_date_text,
            "days_past_due": (today - due_date).days,
            "status": invoice["status"],
            "finding": "Invoice needs review and its due date has passed.",
            "business_risk": (
                "Delayed review may affect payment processing. "
                "Payment status is not confirmed."
            ),
            "recommended_action": (
                "Verify invoice details and supporting documents, "
                "then route through the authorized approval process."
            ),
            "responsible_role": "Accounts Payable or designated approver",
        })
    # Show the most overdue invoices first.
    issues.sort(
        key=lambda issue: issue["days_past_due"],
        reverse=True
    )

    return issues