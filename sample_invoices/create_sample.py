from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

output = Path(__file__).resolve().parent / "northstar_invoice_001.pdf"

pdf = canvas.Canvas(str(output), pagesize=letter)

pdf.setFont("Helvetica-Bold", 18)
pdf.drawString(50, 740, "NORTHSTAR OFFICE SUPPLIES")

pdf.setFont("Helvetica", 11)
pdf.drawString(50, 710, "INVOICE")
pdf.drawString(50, 690, "Invoice Number: NS-2026-001")
pdf.drawString(50, 670, "Invoice Date: 2026-10-01")
pdf.drawString(50, 650, "Due Date: 2026-10-31")

pdf.drawString(50, 610, "Bill To: Acme Creative Studio")

pdf.drawString(50, 560, "Description")
pdf.drawString(320, 560, "Quantity")
pdf.drawString(420, 560, "Unit Price")
pdf.drawString(520, 560, "Amount")

pdf.drawString(50, 530, "Printer Paper")
pdf.drawString(330, 530, "10")
pdf.drawString(430, 530, "$8.00")
pdf.drawString(520, 530, "$80.00")

pdf.drawString(50, 505, "Ink Cartridges")
pdf.drawString(330, 505, "4")
pdf.drawString(430, 505, "$25.00")
pdf.drawString(520, 505, "$100.00")

pdf.drawString(420, 450, "Subtotal: $180.00")
pdf.drawString(420, 430, "Tax: $14.40")
pdf.drawString(420, 410, "Total: $194.40")

pdf.save()

print(f"Sample invoice created: {output}")