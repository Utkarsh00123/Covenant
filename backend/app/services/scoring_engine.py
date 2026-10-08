import uuid
import json
import asyncio
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types

from app.core.config import settings
from app.services.clause_matcher import find_semantic_match
from app.services.rule_engine import evaluate_deterministic_rules
from app.services.redline_generator import generate_redline_for_flag
from app.models.clause import RiskFlag, ExtractedClause

logger = structlog.get_logger(__name__)
client = genai.Client(api_key=settings.GEMINI_API_KEY)

deviation_schema = {
    "type": "OBJECT",
    "properties": {
        "severity": {
            "type": "STRING",
            "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "description": "The severity of the legal risk"
        },
        "reason": {
            "type": "STRING",
            "description": "A concise, 1-2 sentence legal explanation of how the extracted text deviates from the baseline"
        }
    },
    "required": ["severity", "reason"]
}

async def evaluate_clause_risk(
    db: AsyncSession, 
    document_id: str | uuid.UUID, 
    extracted_clause: ExtractedClause,
    llm_structured_data: dict | None = None
) -> list[RiskFlag]:
    """
    The core Hybrid Engine Orchestrator:
    1. Retrieves baseline clause via vector distance (Option B: RETRIEVAL_DOCUMENT).
    2. Runs deterministic arithmetic checks against structured data.
    3. Evaluates semantic deviation with Gemini 3.8 Flash if no deterministic rules fire.
    4. Concurrently triggers surgical redline generation for all flagged risks.
    """
    generated_flags: list[RiskFlag] = []
    
    doc_uuid = uuid.UUID(str(document_id)) if not isinstance(document_id, uuid.UUID) else document_id
    
    # 1. Fetch semantic vector match from pgvector
    match_data = await find_semantic_match(db, extracted_clause.raw_text, extracted_clause.category)
    
    if not match_data:
        return generated_flags 
        
    standard_clause_id = uuid.UUID(match_data["standard_clause_id"])
    acceptable_ranges = match_data.get("acceptable_ranges", {})
    similarity_score = match_data.get("similarity_score")
    
    # 2. Run Deterministic Rules (Math/Thresholds)
    rule_violations = evaluate_deterministic_rules(
        extracted_category=extracted_clause.category,
        extracted_text=extracted_clause.raw_text,
        acceptable_ranges=acceptable_ranges,
        llm_structured_data=llm_structured_data
    )
    
    for violation in rule_violations:
        generated_flags.append(
            RiskFlag(
                document_id=doc_uuid,
                extracted_clause_id=extracted_clause.id,
                standard_clause_id=standard_clause_id,
                flag_type=violation["flag_type"],
                severity=violation["severity"],
                flag_reason=violation["reason"],
                similarity_score=similarity_score,
                ai_model_version="rule-engine-v1",
                evidence_text=extracted_clause.raw_text,
                baseline_text=match_data["standard_text"]
            )
        )
        
    # 3. Dynamic Semantic Deviation Evaluation (Gemini 3.8 Flash)
    if match_data.get("is_deviant") and not rule_violations:
        prompt = f"""
        Compare this contract clause against our standard baseline policy.
        Baseline: "{match_data['standard_text']}"
        Extracted Clause: "{extracted_clause.raw_text}"
        Corporate Risk Rule: "{match_data.get('risk_description', 'Avoid unfavorable terms.')}"
        
        Analyze the legal drift. Return a JSON object with the severity and a concise reason.
        """
        
        try:
            response = await client.aio.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=deviation_schema,
                    temperature=0.1 
                )
            )
            analysis = json.loads(response.text)
            
            generated_flags.append(
                RiskFlag(
                    document_id=doc_uuid,
                    extracted_clause_id=extracted_clause.id,
                    standard_clause_id=standard_clause_id,
                    flag_type="SEMANTIC_DEVIATION",
                    severity=analysis.get("severity", "HIGH"),
                    flag_reason=analysis.get("reason"),
                    similarity_score=similarity_score,
                    ai_model_version="gemini-3.8-flash",
                    evidence_text=extracted_clause.raw_text,
                    baseline_text=match_data["standard_text"]
                )
            )
        except Exception as e:
            logger.error("gemini_3_8_flash_analysis_failed", error=str(e))
            generated_flags.append(
                RiskFlag(
                    document_id=doc_uuid,
                    extracted_clause_id=extracted_clause.id,
                    standard_clause_id=standard_clause_id,
                    flag_type="SEMANTIC_DEVIATION",
                    severity="HIGH",
                    flag_reason=f"Semantic intent deviates from standard policy (Similarity: {similarity_score}).",
                    similarity_score=similarity_score,
                    ai_model_version="gemini-embedding-001-fallback",
                    evidence_text=extracted_clause.raw_text,
                    baseline_text=match_data["standard_text"]
                )
            )
            
    # 4. Pipeline Concurrency: Generate Redlines in Parallel
    if generated_flags:
        logger.info("triggering_redline_engine", flag_count=len(generated_flags))
        
        # Only dispatch LLM redlines if a standard baseline is present for comparison
        redline_tasks = [
            generate_redline_for_flag(flag) 
            for flag in generated_flags 
            if flag.baseline_text
        ]
        
        if redline_tasks:
            # Executes all network calls in parallel event-loop tasks
            completed_flags = await asyncio.gather(*redline_tasks, return_exceptions=False)
            
            # Map updated redline flags back
            updated_map = {f.id: f for f in completed_flags}
            generated_flags = [updated_map.get(flag.id, flag) for flag in generated_flags]
        
    return generated_flags


def calculate_document_risk_score(flags: list[RiskFlag]) -> dict:
    """
    Calculates a bounded composite score based on weighted flag severities.
    Formula: min(100, Sum(weights))
    """
    weights = {
        "CRITICAL": 35,
        "HIGH": 20,
        "MEDIUM": 10,
        "LOW": 5
    }
    
    total_score = 0
    flag_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    
    for flag in flags:
        weight = weights.get(flag.severity, 0)
        total_score += weight
        if flag.severity in flag_counts:
            flag_counts[flag.severity] += 1
            
    bounded_score = min(100, total_score)
    
    if bounded_score < 25:
        risk_level = "LOW"
    elif bounded_score < 60:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"
        
    return {
        "numeric_score": bounded_score,
        "risk_level": risk_level,
        "summary": flag_counts
    }