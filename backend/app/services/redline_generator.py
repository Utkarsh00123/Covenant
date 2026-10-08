import structlog
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.redline import RedlineSuggestion
from app.utils.diff_generator import generate_word_level_diff
from app.models.clause import RiskFlag
from tenacity import retry, wait_exponential, stop_after_attempt

logger = structlog.get_logger(__name__)

REDLINE_SYSTEM_PROMPT = """
You are an expert commercial attorney. Your task is to rewrite a risky contractual clause to make it commercially reasonable and safe for your client.
CRITICAL RULES:
1. Act as a SURGICAL EDITOR. Do not rewrite the entire paragraph if you only need to change a few words.
2. Preserve all original definitions, capitalized terms, and the overall tone.
3. Bring the clause into alignment with the provided "Standard Baseline".
4. Provide a 1-to-2 sentence, plain-English explanation of why this change protects the client.
"""

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def generate_redline_for_flag(flag: RiskFlag) -> RiskFlag:
    """
    Takes a RiskFlag, queries Gemini 3.8 Flash to generate a redline, computes the diff, 
    and attaches the data back to the flag object.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    logger.info("generating_redline", flag_id=str(flag.id), severity=flag.severity)
    
    # Construct the highly specific user prompt
    user_prompt = f"""
    ORIGINAL RISKY CLAUSE:
    "{flag.evidence_text}"
    
    STANDARD BASELINE (WHAT IT SHOULD LOOK LIKE):
    "{flag.baseline_text}"
    
    IDENTIFIED RISK REASON:
    {flag.flag_reason}
    
    Please provide the suggested redline edit and the plain-English explanation.
    """
    
    try:
        # We use gemini-3.8-flash for surgical text editing at massive scale
        response = await client.aio.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=REDLINE_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=RedlineSuggestion,  # Pass the Pydantic class directly
                temperature=0.2  # Slight creativity allowed for prose rewriting, kept low for safety
            )
        )
        
        # The new Google GenAI SDK automatically parses the JSON into the Pydantic object
        redline_data = response.parsed
        
        # Calculate the word-level diff in Python (Deterministic)
        diff_array = generate_word_level_diff(
            original=flag.evidence_text, 
            redline=redline_data.suggested_rewrite
        )
        
        # Attach the generated data to our SQLAlchemy model
        flag.suggested_redline = redline_data.suggested_rewrite
        flag.plain_english_explanation = redline_data.plain_english_explanation
        flag.redline_diff = diff_array
        
        return flag
        
    except Exception as e:
        logger.error("gemini_redline_generation_failed", error=str(e), flag_id=str(flag.id))
        # Fallback Strategy: If the LLM fails, we simply propose swapping in the exact standard baseline
        flag.suggested_redline = flag.baseline_text
        flag.plain_english_explanation = "Automated AI rewrite failed. Reverting to standard company baseline template."
        flag.redline_diff = generate_word_level_diff(flag.evidence_text, flag.baseline_text)
        return flag