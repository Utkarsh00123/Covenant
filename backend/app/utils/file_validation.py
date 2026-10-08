import magic
import hashlib
from fastapi import UploadFile, HTTPException

async def validate_and_hash_pdf(file: UploadFile) -> str:
    """
    Validates that the uploaded file is genuinely a PDF using Magic Bytes.
    Returns the SHA-256 hash of the file for deduplication.
    """
    # Read the first 2048 bytes to determine file type
    file_head = await file.read(2048)
    
    # Reset the file cursor back to the beginning for future reading
    await file.seek(0)
    
    # Determine MIME type using python-magic
    mime_type = magic.from_buffer(file_head, mime=True)
    
    if mime_type != "application/pdf":
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Expected application/pdf, got {mime_type}."
        )
    
    # Generate SHA-256 hash of the entire file
    # We read in chunks to prevent memory exhaustion on large files
    sha256_hash = hashlib.sha256()
    while chunk := await file.read(8192):
        sha256_hash.update(chunk)
        
    # Reset cursor again for the extraction engine
    await file.seek(0)
    
    return sha256_hash.hexdigest()