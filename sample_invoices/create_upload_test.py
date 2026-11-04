from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

output = Path(__file__).resolve().parent / "upload_test_invoice_002.pdf"

pdf = canvas.Canvas(str(output), pagesize=letter)

pdf.setFont("Helvetica-Bold", 18)
pdf.drawString(50, 740, "SUMMIT BUSINESS SUPPLIES")

pdf.setFont("Helvetica", 11)
pdf.drawString(50, 710, "INVOICE")
pdf.drawString(50, 690, "Invoice Number: SUM-2026-002")
pdf.drawString(50, 670, "Invoice Date: 2026-10-15")
pdf.drawString(50, 650, "Due Date: 2026-11-14")

pdf.drawString(50, 610, "Bill To: Acme Creative Studio")

pdf.drawString(50, 560, "Description")
pdf.drawString(320, 560, "Quantity")
pdf.drawString(420, 560, "Unit Price")
pdf.drawString(520, 560, "Amount")

pdf.drawString(50, 530, "Desk Organizers")
pdf.drawString(330, 530, "3")
pdf.drawString(430, 530, "$20.00")
pdf.drawString(520, 530, "$60.00")

pdf.drawString(50, 505, "USB Cables")
pdf.drawString(330, 505, "5")


pdf.drawString(430, 505, "$8.00")
pdf.drawString(520, 505, "$40.00")

pdf.drawString(420, 450, "Subtotal: $100.00")
pdf.drawString(420, 430, "Tax: $8.00")
pdf.drawString(420, 410, "Total: $108.00")

pdf.save()

print(f"Workflow test invoice created: {output}")