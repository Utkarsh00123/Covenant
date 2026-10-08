from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any

class LineItem(BaseModel):
    description: str = Field(default="")
    quantity: float = Field(default=1.0)
    unit_price: float = Field(default=0.0)
    total_price: float = Field(default=0.0)

class InvoiceAnalysis(BaseModel):
    """The master schema for extracting data from a vendor invoice."""
    vendor_name: str = Field(default="Unknown Vendor")
    invoice_number: Optional[str] = None
    issue_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    due_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    payment_terms_days: Optional[int] = Field(None, description="e.g., 30 for Net 30")
    subtotal: float = Field(default=0.0)
    tax_amount: float = Field(default=0.0)
    total_amount: float = Field(default=0.0)
    line_items: List[LineItem] = Field(
        default_factory=list,
        description="The individual products or services billed in this invoice."
    )

    @field_validator("line_items", mode="before")
    @classmethod
    def normalize_line_items(cls, v: Any) -> List[Any]:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []