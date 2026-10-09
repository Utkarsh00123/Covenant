import structlog
from google import genai
from google.genai import types
from tenacity import retry, wait_exponential, stop_after_attempt
from app.core.config import settings

logger = structlog.get_logger(__name__)

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def generate_embedding(text: str, category: str = None, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prepared_text = f"Clause Type: {category.upper()}; Text: {text.strip()}" if category else text.strip()

    try:
        response = await client.aio.models.embed_content(
            model='gemini-embedding-001',
            contents=prepared_text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=768
            )
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.error("gemini_embedding_failed", error=str(e))
        err_lower = str(e).lower()
        if "429" in err_lower or "resource_exhausted" in err_lower or "quota" in err_lower:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail="Google Gemini API Quota Exhausted (429 RESOURCE_EXHAUSTED). You have exceeded your free tier daily quota for gemini-3.1-flash-lite. Please retry when your quota resets."
            )
        raise RuntimeError(f"Failed to generate vector: {str(e)}")