import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from fastapi.responses import Response
from pydantic import BaseModel, Field
import sqlite3
import tempfile
import uuid
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import backend.ap_assistant
from fastapi import FastAPI, UploadFile, File, HTTPException
from starlette.concurrency import run_in_threadpool
from fastapi import FastAPI, HTTPException, Body
from backend.invoice_processor import process_invoice
from backend.excel_export import create_excel_workbook
from backend.database import DATA_DIR, list_invoices, get_invoice, update_invoice_status, mark_invoice_paid, initialize_database
from backend.ap_issue_detector import detect_ap_issues

from contextlib import asynccontextmanager
class InvoiceDecision(BaseModel):
    status: str
    reason: str = Field(default="", max_length=1000)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the local SQLite database when Atlas starts."""
    initialize_database()
    yield


app = FastAPI(
    title="Atlas AI Accounts Payable",
    version="0.1.0",
    lifespan=lifespan
)
app.mount(
    "/assets",
    StaticFiles(directory="frontend/assets"),
    name="assets"
)
INVOICE_DIR = DATA_DIR / "invoices"
INVOICE_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/")
def home():
    return {
        "name": "Atlas",
        "role": "AI Accounts Payable Employee",
        "status": "online",
        "message": "Atlas backend is running successfully!"
    }
@app.get("/invoices/export")
def download_invoice_register():
    excel_path = DATA_DIR / "exports" / "atlas_invoice_register.xlsx"

    create_excel_workbook()

    if not excel_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Invoice register Excel file not found"
        )

    return FileResponse(
        path=excel_path,
        filename="atlas_invoice_register.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



@app.get("/invoices/{invoice_id}/pdf")
def view_invoice_pdf(invoice_id: int):
    invoice = get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    pdf_path = Path(invoice["source_file"]).resolve()

    if not pdf_path.is_relative_to(DATA_DIR.resolve()):
        raise HTTPException(
            status_code=403,
            detail="PDF access not permitted"
        )

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Original PDF file not found"
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        content_disposition_type="inline"
    )
@app.get("/invoice-details")
def invoice_details_page():
    html_path = Path(__file__).resolve().parent.parent / "frontend" / "invoice_details.html"
    return FileResponse(html_path)
@app.get("/dashboard")
def dashboard():
    html_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    return FileResponse(html_path)


@app.get("/invoices")
def get_invoices():
    return list_invoices()


@app.get("/atlas/ap-briefing")
def atlas_ap_briefing():
    from datetime import date
    from decimal import Decimal, InvalidOperation

    invoices = list_invoices()
    today = date.today()

    pending = [
        invoice for invoice in invoices
        if invoice.get("status") == "needs_review"
    ]

    overdue = []
    totals_by_currency = {}

    for invoice in pending:
        due_date = invoice.get("due_date")

        if due_date:
            try:
                if date.fromisoformat(str(due_date)) < today:
                    overdue.append(invoice)
            except ValueError:
                pass

        currency = invoice.get("currency") or "Unknown"

        try:
            amount = Decimal(str(invoice.get("total") or "0"))
            totals_by_currency[currency] = (
                totals_by_currency.get(currency, Decimal("0")) + amount
            )
        except InvalidOperation:
            pass

    return {
        "as_of": today.isoformat(),
        "pending_review_count": len(pending),
        "overdue_pending_count": len(overdue),
        "pending_amounts_by_currency": {
            currency: str(amount)
            for currency, amount in totals_by_currency.items()
        },
               "message": (
            f"You have {len(pending)} invoices awaiting review, "
            f"including {len(overdue)} overdue invoices."
        ),
        "detected_ap_issues": detect_ap_issues(today=today),
    }
@app.post("/atlas/ap-mark-reviewed")
def atlas_ap_mark_reviewed():
    from backend.database import mark_ap_reviewed

    reviewed_at = mark_ap_reviewed()

    return {
        "success": True,
        "last_reviewed_at": reviewed_at,
        "message": (
            "AP activity marked as reviewed. "
            "Atlas will track new activity from this checkpoint."
        ),
    }
@app.get("/atlas/ap-changes")
def atlas_ap_changes():
    from backend.database import (
        get_last_ap_review,
        list_invoice_activity_since,
    )

    last_reviewed_at = get_last_ap_review()

    if last_reviewed_at is None:
        return {
            "last_reviewed_at": None,
            "message": (
                "No AP review checkpoint has been recorded yet. "
                "Mark the activity as reviewed to begin tracking changes."
            ),
            "new_uploads": 0,
            "status_changes": 0,
            "activities": [],
        }

    activities = [
    {
        "invoice_number": activity["invoice_number"],
        "vendor_name": activity["vendor_name"],
        "action": activity["action"],
        "created_at": activity["created_at"],
    }
    for activity in list_invoice_activity_since(last_reviewed_at)
]

    return {
        "last_reviewed_at": last_reviewed_at,
        "new_uploads": sum(
            activity["action"] == "uploaded"
            for activity in activities
        ),
        "status_changes": sum(
            activity["action"] == "status_changed"
            for activity in activities
        ),
        "activities": activities,
    }
@app.get("/atlas/daily-briefing")
def atlas_daily_briefing():
    from datetime import date

    ap = atlas_ap_briefing()
    changes = atlas_ap_changes()

    pending = ap["pending_review_count"]
    overdue = ap["overdue_pending_count"]
    uploads = changes["new_uploads"]
    status_changes = changes["status_changes"]

    issues = ap["detected_ap_issues"]

    high_priority_issues = [
        issue for issue in issues
        if issue.get("priority") == "high"
    ]

    priority_message = (
        f" Atlas has identified {len(high_priority_issues)} "
        f"high-priority {'issue' if len(high_priority_issues) == 1 else 'issues'}."
    )

    if high_priority_issues:
        top_issue = high_priority_issues[0]
        priority_message += (
            f" The first priority is invoice "
            f"{top_issue.get('invoice_number', 'unknown')}. "
            f"Recommended action: "
            f"{top_issue.get('recommended_action', 'Review the invoice.')}"
        )

    pending_label = "invoice" if pending == 1 else "invoices"
    overdue_label = "invoice" if overdue == 1 else "invoices"

    message = (
        f"Daily Accounts Payable briefing for {date.today().isoformat()}. "
        f"You have {pending} {pending_label} awaiting review, "
        f"including {overdue} overdue {overdue_label}. "
        f"Since your last review, there have been "
        f"{uploads} new invoice uploads and "
        f"{status_changes} status changes."
        f"{priority_message}"
    )

    return {
        "date": date.today().isoformat(),
        "message": message,
        "pending_review_count": pending,
        "overdue_pending_count": overdue,
        "new_uploads": uploads,
        "status_changes": status_changes,
        "detected_ap_issues": issues,
        "last_reviewed_at": changes["last_reviewed_at"],
    }
@app.get("/invoices/{invoice_id}")
def get_invoice_by_id(invoice_id: int):
    return get_invoice(invoice_id)

@app.patch("/invoices/{invoice_id}/status")
def change_invoice_status(invoice_id: int, decision: InvoiceDecision):
    if os.getenv("ATLAS_ENABLE_REVIEW_DECISIONS") != "true":
        raise HTTPException(
            status_code=403,
            detail="Invoice review decisions are disabled on this server"
        )

    status = decision.status

    if status == "rejected" and not decision.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    if status not in ("needs_review", "approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="Invalid invoice status"
        )

    invoice = get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found"
        )

    if invoice.get("status") == "paid":
        raise HTTPException(
            status_code=409,
            detail="Paid invoices cannot have their status changed"
        )

    if invoice.get("status") != "needs_review":
        raise HTTPException(
            status_code=409,
            detail="Only invoices needing review can be approved or rejected"
        )

    if status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="Review decisions must be approved or rejected"
        )

    updated = update_invoice_status(invoice_id, status, decision.reason)

    if not updated:
        raise HTTPException(
            status_code=409,
            detail="Invoice is no longer awaiting review"
        )

    return {"invoice_id": invoice_id, "status": status}

@app.post("/invoices/{invoice_id}/mark-paid")
def mark_invoice_paid_endpoint(
    invoice_id: int,
    payment_date: str,
    payment_reference: str,
):
    try:
        return mark_invoice_paid(
            invoice_id,
            payment_date,
            payment_reference,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
@app.post("/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF invoices are supported."
        )

    header = await file.read(5)

    if header != b"%PDF-":
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid PDF."
        )
    await file.seek(0)

    pdf_content = await file.read(10 * 1024 * 1024 + 1)

    if len(pdf_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="PDF file exceeds the 10 MB limit."
        )

    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False
    ) as temporary_file:
        temporary_file.write(pdf_content)
        temporary_path = Path(temporary_file.name)
    permanent_path = INVOICE_DIR / f"{uuid.uuid4().hex}.pdf"

    try:
        temporary_path.replace(permanent_path)
        invoice_id = await run_in_threadpool(process_invoice, str(permanent_path))
        invoice_details = get_invoice(invoice_id) or {}

        return {
            "filename": file.filename,
            "invoice_id": invoice_id,
            "vendor_name": invoice_details.get("vendor_name"),
            "invoice_number": invoice_details.get("invoice_number"),
            "total": invoice_details.get("total"),
            "currency": invoice_details.get("currency"),
            "validation_issues": invoice_details.get("validation_issues", []),
            "status": "needs_review",
            "message": "Atlas processed and saved the invoice successfully."

        }

    except sqlite3.IntegrityError:
        permanent_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail="This invoice already exists in Atlas."
        )
    except Exception:
        permanent_path.unlink(missing_ok=True)
        raise
    finally:
        temporary_path.unlink(missing_ok=True)


# Atlas AI employee voice — ElevenLabs
@app.post("/atlas/speak")
def atlas_speak(
    announcement: str = "",
    invoice_id: int | None = None,
    chat_text: str = "",
    payload: dict | None = Body(default=None),
):
    import requests

    if payload is not None:
        announcement = payload.get("announcement", announcement)
        invoice_id = payload.get("invoice_id", invoice_id)
        chat_text = payload.get("chat_text", chat_text)

    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")

    if not api_key or not voice_id:
        raise HTTPException(
            status_code=503,
            detail="Atlas voice is not configured."
        )

    if announcement == "chat_answer":
        message = chat_text.strip()

        if not message:
            raise HTTPException(
                status_code=400,
                detail="No Atlas chat answer was provided."
            )

        if len(message) > 3000:
            raise HTTPException(
                status_code=400,
                detail="Atlas chat answer is too long for speech."
            )
        from backend.speech_formatter import format_for_speech
        message = format_for_speech(message)
    elif announcement == "invoice_complete" and invoice_id is not None:
        invoice = get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        from decimal import Decimal, InvalidOperation
        from num2words import num2words

        number = str(invoice.get("invoice_number") or "unknown")
        letter_names = {
            "A": "ay", "B": "bee", "C": "see", "D": "dee",
            "E": "ee", "F": "eff", "G": "gee", "H": "aitch",
            "I": "eye", "J": "jay", "K": "kay", "L": "ell",
            "M": "em", "N": "en", "O": "oh", "P": "pee",
            "Q": "cue", "R": "are", "S": "ess", "T": "tee",
            "U": "you", "V": "vee", "W": "double you",
            "X": "ex", "Y": "why", "Z": "zee",
        }
        import re
        parts = re.findall(r"[A-Za-z]+|\d+", number)
        spoken_parts = []

        for part in parts:
            if part.isalpha():
                if part.isupper() and len(part) in (3, 4):
                    spoken_parts.extend(part)
                else:
                    spoken_parts.append(part)
            else:
                spoken_parts.extend(num2words(int(digit)) for digit in part)

        spoken_number = ". ".join(
            letter_names.get(part, part) for part in spoken_parts
        )

        vendor = str(invoice.get("vendor_name") or "unknown vendor")
        import re
        vendor = re.sub(
            r"\s+(?:Co\.?|LLC|Inc\.?|Ltd\.?)$",
            "",
            vendor,
            flags=re.IGNORECASE,
        )
        total = str(invoice.get("total") or "")
        currency = str(invoice.get("currency") or "").upper()

        spoken_amount = ""
        if total and currency:
            try:
                amount = Decimal(total.replace(",", ""))
                if amount.is_finite() and amount >= 0:
                    dollars = int(amount)
                    cents = int((amount - dollars) * 100 + Decimal("0.5"))

                    if currency == "EUR":
                        spoken_amount = f"{num2words(dollars)} euros"
                        if cents:
                            spoken_amount += f" and {num2words(cents)} cents"

                    elif currency == "GBP":
                        spoken_amount = f"{num2words(dollars)} pounds"
                        if cents:
                            spoken_amount += f" and {num2words(cents)} pence"

                    elif currency == "USD":
                        spoken_amount = f"{num2words(dollars)} dollars"
                        if cents:
                            spoken_amount += f" and {num2words(cents)} cents"
                    else:
                        spoken_amount = f"{num2words(dollars)} {currency}"
                        if cents:
                            spoken_amount += f" and {num2words(cents)} cents"
            except (InvalidOperation, ValueError):
                pass
        from datetime import date
        due_date = str(invoice.get("due_date") or "")
        if due_date:
            try:
                parsed_date = date.fromisoformat(due_date)
                spoken_day = num2words(parsed_date.day, to="ordinal")
                due_date = f"{parsed_date.strftime('%B')} {spoken_day}, {parsed_date.year}"
            except ValueError:
                pass

        message = (
            f"I've processed invoice {spoken_number} "
            f"from {vendor}. "
        )

        if spoken_amount:
            message += f"The total is {spoken_amount}. "

        if due_date:
            message += f"The due date is {due_date}. "

        issues = invoice.get("validation_issues") or []
        if issues:
            message += (
                f"I found {len(issues)} validation "
                "issues that need your attention."
            )
        else:
            message += "It's ready for your review."

    elif announcement == "ap_briefing":
        from decimal import Decimal

        briefing = atlas_ap_briefing()
        pending = briefing["pending_review_count"]
        overdue = briefing["overdue_pending_count"]
        amounts = briefing["pending_amounts_by_currency"]
        issues = briefing["detected_ap_issues"]

        high_count = sum(
            issue["priority"] == "high" for issue in issues
        )
        medium_count = sum(
            issue["priority"] == "medium" for issue in issues
        )
        low_count = sum(
            issue["priority"] == "low" for issue in issues
        )

        pending_word = "invoice" if pending == 1 else "invoices"
        overdue_word = "invoice" if overdue == 1 else "invoices"

        message = (
            "Here's your accounts payable briefing. "
            f"You currently have {pending} {pending_word} awaiting review, "
            f"including {overdue} overdue {overdue_word} awaiting review. "
        )

        if issues:
            priority_parts = []

            for label, count in (
                ("high-priority", high_count),
                ("medium-priority", medium_count),
                ("low-priority", low_count),
            ):
                if count:
                    count_word = "one" if count == 1 else str(count)
                    issue_word = "issue" if count == 1 else "issues"
                    priority_parts.append(
                        f"{count_word} {label} {issue_word}"
                    )

            message += (
                "Atlas has identified "
                + ", ".join(priority_parts)
                + ". "
            )
        if issues:
            top_issues = issues[:3]

            message += "The invoices requiring the earliest attention are: "

            for issue in top_issues:
                invoice_number = issue.get("invoice_number") or "Unknown"

                import re
                from num2words import num2words
                spoken_invoice_number = ". ".join(
                    (
                        letter.upper()
                        if letter.isalpha()
                        else num2words(int(letter))
                    )
                    for letter in re.findall(r"[A-Za-z]|\d", invoice_number)
                ) + "."
                vendor = issue.get("vendor") or "Unknown vendor"
                days = issue["days_past_due"]
                from num2words import num2words
                spoken_days = num2words(days)
                day_word = "day" if days == 1 else "days"

                message += (
                    f"Invoice {spoken_invoice_number} from {vendor}, "
                    f"{spoken_days} {day_word} overdue for review. "
                )
        if len(amounts) == 1 and "USD" in amounts:
            total = Decimal(amounts["USD"])
            from num2words import num2words

            dollars = int(total)
            cents = int((total - dollars) * 100)

            spoken_amount = f"{num2words(dollars)} dollars"

            if cents:
                spoken_amount += f" and {num2words(cents)} cents"

            message += (
                f"The total value of invoices awaiting review is "
                f"{spoken_amount}. "
                "This amount excludes invoices that have already "
                "been approved. "
            )

        if overdue:
            message += (
                "I recommend reviewing the most overdue invoices first, "
                "verifying their supporting documentation, and "
                "coordinating with the designated approvers. "
            )

        message += (
            "Invoice review status does not confirm payment status. "
            "The full list of detected issues and recommended actions "
            "is available in your Atlas dashboard."
        )

    elif announcement == "invoice_complete":
        message = "I've finished processing your invoice. It's ready for review."
    else:
        message = (
            "Hello! I'm Atlas, your AI Accounts Payable Employee. "
            "I'm ready to process your invoices. "
            "Please upload your invoice whenever you're ready, "
            "and I'll process it as soon as it's uploaded."
        )
    if announcement == "ap_briefing":
        from backend.speech_formatter import format_for_speech
        message = format_for_speech(message)
    try:
        result = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": message,
                "model_id": "eleven_flash_v2_5",
            },
            timeout=30,
        )
        result.raise_for_status()
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Atlas could not generate speech. Check ElevenLabs settings."
        )

    return Response(content=result.content, media_type="audio/mpeg")


# Atlas Accounts Payable Intelligence

class AtlasChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=4000)


class AtlasChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[AtlasChatMessage] = Field(
        default_factory=list,
        max_length=10
    )


@app.post("/api/assistant/chat")
def atlas_assistant_chat(request: AtlasChatRequest):
    from fastapi import HTTPException
    import logging

    try:
        answer = backend.ap_assistant.ask_atlas(
            question=request.question,
            history=[
                message.model_dump()
                for message in request.history
                if message.role in ("user", "assistant")
            ],
        )

        return {"answer": answer}

    except Exception:
        logging.exception("Atlas assistant request failed")
        raise HTTPException(
            status_code=503,
            detail="Atlas is temporarily unable to answer. Please try again."
        )

from pathlib import Path
from fastapi.responses import FileResponse

@app.get("/glass-studio")
def glass_studio():
    html_path = (
        Path(__file__).resolve().parent.parent
        / "frontend"
        / "glass_studio_v23.html"
    )
    return FileResponse(html_path)

# Preserve V22 as a dedicated rollback route.
@app.get("/glass-studio-v22")
def glass_studio_v22():
    html_path = (
        Path(__file__).resolve().parent.parent
        / "frontend"
        / "glass_studio_v22.html"
    )
    return FileResponse(html_path)
# V23 — chart refinement preview; V22 route remains unchanged.
@app.get("/glass-studio-v23")
def glass_studio_v23():
    html_path = (
        Path(__file__).resolve().parent.parent
        / "frontend"
        / "glass_studio_v23.html"
    )
    return FileResponse(html_path)
