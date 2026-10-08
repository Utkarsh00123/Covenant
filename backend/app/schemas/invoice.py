from pydantic import BaseModel, Field
from typing import List, Optional

class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total_price: float

class InvoiceAnalysis(BaseModel):
    """The master schema for extracting data from a vendor invoice."""
    vendor_name: str
    invoice_number: Optional[str] = None
    issue_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    due_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    payment_terms_days: Optional[int] = Field(None, description="e.g., 30 for Net 30")
    subtotal: float
    tax_amount: float
    total_amount: float
    line_items: List[LineItem] = Field(
        description="The individual products or services billed in this invoice."
    )