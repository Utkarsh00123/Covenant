from typing import List
from app.schemas.extraction import TextBlock

def chunk_text_blocks(blocks: List[TextBlock], max_chars: int = 12000, overlap_chars: int = 1000) -> List[str]:
    """
    Combines text blocks into chunks of `max_chars`.
    Uses an overlap to ensure clauses split across pages are not lost.
    """
    chunks = []
    current_chunk = ""
    
    for block in blocks:
        if len(current_chunk) + len(block.text) > max_chars:
            # Save the current chunk
            chunks.append(current_chunk)
            # Start the new chunk with the overlap from the end of the previous chunk
            current_chunk = current_chunk[-overlap_chars:] + " \n " + block.text
        else:
            current_chunk += " \n " + block.text
            
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks