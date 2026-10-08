import structlog
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from tenacity import retry, wait_exponential, stop_after_attempt

from app.core.config import settings

logger = structlog.get_logger(__name__)

class RedlineScore(BaseModel):
    risk_mitigation_score: int = Field(..., ge=1, le=5, description="1-5 score on how well the rewrite neutralized the legal risk.")
    preservation_score: int = Field(..., ge=1, le=5, description="1-5 score on how well the rewrite preserved original entities and tone.")
    overall_quality_score: int = Field(..., ge=1, le=5, description="Overall viability of the edit.")
    judge_reasoning: str = Field(..., description="A brief explanation of why these scores were given.")

JUDGE_PROMPT = """
You are an impartial Senior Corporate Counsel grading an AI legal assistant.
You will be provided with:
1. The original risky clause.
2. The AI's suggested redline.
3. The baseline standard it was aiming for.

Grade the AI's redline strictly on the 1-5 scale requested in the schema.
"""

# 1. Isolate the API call so tenacity can see the exceptions and retry
@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def _call_gemini_judge(user_content: str) -> dict:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=JUDGE_PROMPT,
            response_mime_type="application/json",
            response_schema=RedlineScore,
            temperature=0.0,
            automatic_function_calling={"disable": True}  # 2. Fix the AFC warning
        )
    )
    return response.parsed.model_dump()


async def grade_redline(original: str, redline: str, baseline: str) -> dict:
    """Uses Gemini as an automated evaluator for generative text."""
    user_content = f"ORIGINAL:\n{original}\n\nAI REDLINE:\n{redline}\n\nTARGET BASELINE:\n{baseline}"
    
    try:
        # Tenacity will retry this up to 3 times if Google returns a 503
        return _call_gemini_judge(user_content)
        
    except Exception as e:
        logger.error("llm_judge_failed", error=str(e))
        # Fallback only triggers if ALL retries fail
        return {
            "risk_mitigation_score": 0,
            "preservation_score": 0,
            "overall_quality_score": 0,
            "judge_reasoning": f"Evaluation failed: {str(e)}"
        }
