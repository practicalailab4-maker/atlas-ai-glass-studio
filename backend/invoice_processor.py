from pathlib import Path
from pypdf import PdfReader
from backend.database import save_invoice

from backend.invoice_validator import validate_invoice

def extract_pdf_text(pdf_path: str) -> str:
    """Extract readable text from a PDF invoice."""

    path = Path(pdf_path)

    if not path.is_file():
        raise FileNotFoundError(f"Invoice not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("Atlas only accepts PDF files.")

    reader = PdfReader(path)

    if not reader.pages:
        raise ValueError("The PDF contains no pages.")

    page_texts = []

    for page in reader.pages:
        text = page.extract_text() or ""
        page_texts.append(text)

    extracted_text = "\n\n".join(page_texts).strip()

    if not extracted_text:
        raise ValueError(
            "No readable text found. This invoice may be a scanned PDF."
        )

    return extracted_text

from backend.ai_client import get_openai_client
from backend.invoice_schema import InvoiceData


def extract_invoice_data(pdf_path: str) -> InvoiceData:
    """Use OpenAI to extract structured invoice fields."""

    invoice_text = extract_pdf_text(pdf_path)

    client = get_openai_client()

    response = client.responses.parse(
        model="gpt-4.1-mini",
        instructions=(
            "You are Atlas, an AI Accounts Payable Employee. "
            "Extract invoice information accurately. "
            "Never invent missing information. "
            "Use YYYY-MM-DD for dates and ISO currency codes. "
            "Extract monetary amounts as numbers without currency symbols. "
            "Extract any invoice-level discount as a positive monetary amount. "
            "Use 0 for the discount when no discount is shown. "
            "Preserve the invoice's stated totals rather than correcting them. "
            "Return the extracted information using the provided schema."
        ),
        input=invoice_text,
        text_format=InvoiceData,
    )

    if response.output_parsed is None:
        raise ValueError("Atlas could not extract invoice data.")

    return response.output_parsed

def process_invoice(pdf_path: str) -> int:
    """Extract, validate, and save an invoice."""

    invoice = extract_invoice_data(pdf_path)
    issues = validate_invoice(invoice)

    invoice_id = save_invoice(
        invoice,
        source_file=pdf_path,
        status="needs_review",
        validation_issues=issues,
    )

    return invoice_id