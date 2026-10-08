from pydantic import BaseModel
from typing import List, Tuple

class TextBlock(BaseModel):
    """Represents a single paragraph or block of text extracted from a PDF."""
    page_number: int
    text: str
    # Bounding box as normalized percentages: [x0, y0, x1, y1]
    bbox: Tuple[float, float, float, float] 
    is_table: bool = False

class ExtractedDocument(BaseModel):
    """The complete payload returned by our hybrid extraction engine."""
    filename: str
    total_pages: int
    blocks: List[TextBlock]
    needs_ocr_fallback: bool
    processing_time_ms: float