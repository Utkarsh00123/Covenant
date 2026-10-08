import fitz  # PyMuPDF
import pdfplumber
import time
import structlog
from io import BytesIO
from app.schemas.extraction import TextBlock, ExtractedDocument
from app.services.ocr_engine import run_ocr_on_page

logger = structlog.get_logger(__name__)

def normalize_bbox(bbox: tuple, page_width: float, page_height: float) -> tuple:
    """
    Converts absolute pixel coordinates to percentages for Next.js frontend rendering.
    Formula: (coordinate / dimension) * 100
    """
    x0, y0, x1, y1 = bbox
    
    # Clamp values to ensure they don't exceed 100% or drop below 0%
    nx0 = max(0.0, min(100.0, (x0 / page_width) * 100))
    ny0 = max(0.0, min(100.0, (y0 / page_height) * 100))
    nx1 = max(0.0, min(100.0, (x1 / page_width) * 100))
    ny1 = max(0.0, min(100.0, (y1 / page_height) * 100))
    
    return (nx0, ny0, nx1, ny1)

async def parse_document(file_bytes: bytes, filename: str, is_invoice: bool = False) -> ExtractedDocument:
    """
    The main routing engine for document ingestion.
    """
    start_time = time.time()
    blocks = []
    needs_ocr = False
    
    # 1. Load the document into PyMuPDF from memory bytes
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        logger.error("pdf_open_failed", error=str(e))
        raise ValueError("Corrupted or unreadable PDF file.")

    total_pages = len(doc)
    
    # 2. Iterate through every page
    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        page_width = page.rect.width
        page_height = page.rect.height
        
        # PyMuPDF extracts text in 'blocks' (paragraphs)
        page_blocks = page.get_text("blocks")
        
        # Heuristic: Calculate total characters extracted digitally
        total_chars = sum(len(b[4].strip()) for b in page_blocks if b[6] == 0) # b[6]==0 means text block, not image
        
        # 3. OCR Fallback Router
        if total_chars < 50:
            logger.info("scanned_page_detected", page=page_num + 1)
            needs_ocr = True
            try:
                ocr_blocks = run_ocr_on_page(file_bytes, page_num + 1)
                for ob in ocr_blocks:
                    blocks.append(TextBlock(**ob))
            except Exception as ocr_err:
                logger.warning("ocr_page_fallback_failed", page=page_num + 1, error=str(ocr_err))
                raw = page.get_text().strip()
                if raw:
                    blocks.append(TextBlock(
                        page_number=page_num + 1,
                        text=raw,
                        bbox=(0.0, 0.0, 100.0, 100.0),
                        is_table=False
                    ))
            continue # Skip to next page
            
        # 4. Digital Text Extraction
        for b in page_blocks:
            # b contains: (x0, y0, x1, y1, "text", block_no, block_type)
            if b[6] == 0:  # Type 0 is text
                raw_text = b[4].strip()
                if not raw_text:
                    continue
                    
                # Clean up unicode ligatures and messy line breaks
                clean_text = raw_text.replace("\n", " ").replace("ﬁ", "fi").replace("ﬂ", "fl")
                
                normalized_coords = normalize_bbox((b[0], b[1], b[2], b[3]), page_width, page_height)
                
                blocks.append(TextBlock(
                    page_number=page_num + 1,
                    text=clean_text,
                    bbox=normalized_coords,
                    is_table=False
                ))
    
    # 5. Tabular Data Extraction (Specifically for Invoices)
    if is_invoice and not needs_ocr:
        logger.info("triggering_pdfplumber_for_tables")
        with pdfplumber.open(BytesIO(file_bytes)) as plumber_doc:
            for page_num, plumber_page in enumerate(plumber_doc.pages):
                tables = plumber_page.extract_tables()
                for table in tables:
                    # Convert 2D array table into a structured string for the LLM
                    table_str = "\n".join([" | ".join(str(cell) if cell else "" for cell in row) for row in table])
                    
                    if table_str.strip():
                        blocks.append(TextBlock(
                            page_number=page_num + 1,
                            text=f"[TABULAR DATA]:\n{table_str}",
                            bbox=(0.0, 0.0, 100.0, 100.0), # Simplification for tables
                            is_table=True
                        ))
    
    doc.close()
    
    processing_time = (time.time() - start_time) * 1000 # milliseconds
    
    return ExtractedDocument(
        filename=filename,
        total_pages=total_pages,
        blocks=blocks,
        needs_ocr_fallback=needs_ocr,
        processing_time_ms=processing_time
    )