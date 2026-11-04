from pydantic import BaseModel
from typing import Optional


class InvoiceLineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    amount: float


class InvoiceData(BaseModel):
    vendor_name: str
    invoice_number: str
    invoice_date: str
    due_date: Optional[str] = None
    bill_to: Optional[str] = None
    currency: str = "USD"
    line_items: list[InvoiceLineItem]
    subtotal: float
    discount: float = 0.0
    tax: float
    total: float