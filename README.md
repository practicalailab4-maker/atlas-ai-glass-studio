# Atlas AI Glass Studio

**Atlas AI Glass Studio** is a local-first, AI-assisted Accounts Payable application built with Python, FastAPI, SQLite, HTML, and JavaScript.

V23 introduces a Liquid Glass dashboard for reviewing invoices, monitoring Accounts Payable activity, and recording payment information.

> **Project status:** Working prototype for learning and demonstrations. Not a production accounting or payment-processing system.

## Features

- **Liquid Glass dashboard:** Interactive Accounts Payable interface with charts, summaries, and invoice activity.
- **PDF invoice processing:** Upload text-based invoice PDFs for AI-assisted extraction.
- **AI extraction:** Identify vendor details, invoice numbers, dates, line items, and amounts using OpenAI.
- **Invoice validation:** Review invoice calculations and potential discrepancies.
- **Invoice workflow:** Review, approve, reject, and track invoice status.
- **Payment recording:** Mark an invoice as paid and record its payment date and reference.
- **Activity history:** Track invoice uploads, decisions, and payment-recording events.
- **Atlas assistant:** Accounts Payable summaries and optional ElevenLabs-powered voice features.
- **Excel export:** Export invoice information for further review.
- **Local SQLite storage:** Keep invoice records in a local database.

**Important:** Marking an invoice as paid records information in Atlas. It does **not** initiate a bank transfer, send funds, or independently verify that payment occurred.

## Technology

- Python and FastAPI
- SQLite
- OpenAI API
- ElevenLabs for optional voice features
- HTML, CSS, and JavaScript
- pypdf and openpyxl

## Run locally

### 1. Clone the repository

Clone this repository and open its project directory in a Terminal.

### 2. Create a virtual environment

On macOS or Linux:

    python3 -m venv .venv
    source .venv/bin/activate

On Windows:

    python -m venv .venv
    .venv\Scripts\activate

### 3. Install dependencies

    python -m pip install -r requirements.txt

### 4. Configure API credentials

Set your OpenAI API key in your local environment:

    export OPENAI_API_KEY="your-api-key"

Optional voice features may require an ElevenLabs API key and configured voice ID.

Never commit API keys, credentials, or private `.env` files.

### 5. Start Atlas

Run from the repository root:

    python -m uvicorn backend.main:app --reload --port 8000

Open the V23 dashboard:

**http://127.0.0.1:8000/glass-studio**

API documentation:

**http://127.0.0.1:8000/docs**

The application initializes its local SQLite database when it starts. Existing databases are updated with the V23 invoice columns when needed.

## Demonstration workflow

1. Start Atlas and open the Glass Studio dashboard.
2. Upload a fictional or redacted invoice PDF.
3. Review the extracted invoice information and validation results.
4. Inspect invoice details and activity history.
5. Change an invoice's review status.
6. If payment has occurred outside Atlas, record the payment date and reference.
7. Review the updated dashboard and invoice activity.

Use fictional or redacted data for public demonstrations.

## Data and privacy

Invoice PDFs, local SQLite databases, API credentials, and virtual environments are not intended for publication.

The repository contains application source code and sample-invoice generation scripts. Generate test invoices locally rather than committing private invoice documents.

### Optional: enable approve / reject

The Approve and Reject controls in the Review view are switched off by default,
so a demo can't change invoice decisions by accident. To turn them on, set this
before starting the server:

```bash
export ATLAS_ENABLE_REVIEW_DECISIONS=true
python -m uvicorn backend.main:app --reload --port 8000
```

Marking an invoice as paid only records the information. It does not move money.

## Build on it for your own business

Atlas is a small working example of AI acting as an extra helper in the back office. It is not a finished product. The parts you are most likely to change:

| To change… | Edit |
|---|---|
| What the AI reads from each invoice | `backend/invoice_processor.py` (the extraction instructions) and `backend/invoice_schema.py` (the fields) |
| What counts as a problem (totals, missing fields, your own rules) | `backend/invoice_validator.py`. This is plain code, with no AI involved. |
| How the assistant answers questions | `backend/ap_assistant.py` |
| Which issues get flagged for people | `backend/ap_issue_detector.py` |
| The dashboard | `frontend/glass_studio_v23.html` |

**Before you use it:**
- You need your own OpenAI API key. Extraction calls use your account and cost money.
- Use fictional or redacted invoices while you experiment. The demo data in this repo is artificial.
- The AI reads the invoice, but a person should still approve it. Keep that step.

## Limitations

- AI-generated invoice information requires human verification.
- Text-based PDFs work best; scanned PDFs may require OCR.
- Payment recording does not execute or verify payments.
- SQLite and local file storage are intended for prototyping.
- Authentication, access controls, and production security hardening are not included as a complete deployment solution.
- Some AI and voice functionality requires external API credentials and services.

## Project purpose

Atlas AI Glass Studio demonstrates how AI-assisted document processing, invoice validation, workflow tracking, analytics, and a modern interface can support Accounts Payable work.

**Built as a practical AI automation project and demonstration.**

## License

Released under the [MIT License](LICENSE). You are free to use, modify and build on this project, including for your own business.
