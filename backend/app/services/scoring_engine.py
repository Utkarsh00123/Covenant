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

deviation_schema = {
    "type": "OBJECT",
    "properties": {
        "has_deviation": {
            "type": "BOOLEAN",
            "description": "True if the extracted clause contains unfavorable terms, risks, or meaningfully deviates from the baseline policy. False if compliant, balanced, or acceptable."
        },
        "severity": {
            "type": "STRING",
            "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "description": "The severity of the legal risk if has_deviation is True. Use LOW if has_deviation is False."
        },
        "reason": {
            "type": "STRING",
            "description": "A concise, 1-2 sentence legal explanation of the deviation, risk, or compliance."
        }
    },
    "required": ["has_deviation", "severity", "reason"]
}

async def evaluate_clause_risk(
    db: AsyncSession, 
    document_id: str | uuid.UUID, 
    extracted_clause: ExtractedClause,
    llm_structured_data: dict | None = None
) -> list[RiskFlag]:
    """
    The core Hybrid Engine Orchestrator:
    1. Retrieves baseline clause via vector distance (MATCH_SIMILARITY_FLOOR = 0.40).
    2. Runs deterministic arithmetic checks against structured data & text regex.
    3. Evaluates semantic deviation with Gemini 3.5 Flash Lite if no deterministic rules fire.
    4. Concurrently triggers surgical redline generation for all flagged risks.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    generated_flags: list[RiskFlag] = []
    
    doc_uuid = uuid.UUID(str(document_id)) if not isinstance(document_id, uuid.UUID) else document_id
    
    logger.info("evaluating_clause_risk_start", 
        clause_id=str(extracted_clause.id), 
        category=extracted_clause.category,
        text_snippet=extracted_clause.raw_text[:60]
    )

    # 1. Fetch semantic vector match from pgvector
    match_data = await find_semantic_match(db, extracted_clause.raw_text, extracted_clause.category)
    
    if not match_data:
        logger.info("no_baseline_matched_skipping_evaluation", category=extracted_clause.category)
        return generated_flags 
        
    standard_clause_id = uuid.UUID(match_data["standard_clause_id"])
    acceptable_ranges = match_data.get("acceptable_ranges", {})
    similarity_score = match_data.get("similarity_score")
    
    logger.info("vector_match_evaluated",
        category=extracted_clause.category,
        matched_title=match_data.get("title"),
        similarity_score=similarity_score
    )

    # 2. Run Deterministic Rules (Math/Thresholds/Categorical policies)
    rule_violations = evaluate_deterministic_rules(
        extracted_category=extracted_clause.category,
        extracted_text=extracted_clause.raw_text,
        acceptable_ranges=acceptable_ranges,
        llm_structured_data=llm_structured_data
    )
    
    for violation in rule_violations:
        flag = RiskFlag(
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
        generated_flags.append(flag)
        logger.info("deterministic_flag_generated", 
            category=extracted_clause.category,
            severity=violation["severity"], 
            reason=violation["reason"]
        )
        
    # 3. Dynamic Semantic Deviation Evaluation (Gemini 3.5 Flash Lite)
    # If no deterministic rules fired, ask Gemini to assess legal drift & policy compliance
    if not rule_violations:
        logger.info("initiating_semantic_deviation_check", 
            category=extracted_clause.category, 
            similarity=similarity_score
        )
        prompt = f"""
        Compare this contract clause against our corporate standard baseline policy.
        Category: {extracted_clause.category}
        Standard Baseline Policy: "{match_data['standard_text']}"
        Extracted Clause: "{extracted_clause.raw_text}"
        Corporate Risk Policy: "{match_data.get('risk_description', 'Avoid unfavorable, non-standard, or one-sided terms.')}"
        
        Analyze the legal drift, liability balance, and commercial risk.
        Determine whether the extracted clause deviates unfavorably from our policy, introduces one-sided burdens, lacks standard protections, or creates disadvantageous terms.
        
        Return JSON adhering to schema:
        - "has_deviation": true if there is material legal risk, one-sided terms, or policy deviation; false if compliant and acceptable.
        - "severity": "MEDIUM", "HIGH", or "CRITICAL" if has_deviation is true; "LOW" if false.
        - "reason": A concise, 1-2 sentence legal explanation.
        """
        
        try:
            response = await client.aio.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=deviation_schema,
                    temperature=0.1 
                )
            )
            analysis = json.loads(response.text)
            has_deviation = analysis.get("has_deviation", False)
            severity = analysis.get("severity", "LOW")
            reason = analysis.get("reason", "")
            
            logger.info("semantic_deviation_evaluated",
                category=extracted_clause.category,
                has_deviation=has_deviation,
                severity=severity,
                reason=reason,
                similarity_score=similarity_score
            )

            if has_deviation and severity != "LOW":
                flag = RiskFlag(
                    document_id=doc_uuid,
                    extracted_clause_id=extracted_clause.id,
                    standard_clause_id=standard_clause_id,
                    flag_type="SEMANTIC_DEVIATION",
                    severity=severity,
                    flag_reason=reason,
                    similarity_score=similarity_score,
                    ai_model_version="gemini-3.5-flash-lite",
                    evidence_text=extracted_clause.raw_text,
                    baseline_text=match_data["standard_text"]
                )
                generated_flags.append(flag)
                logger.info("semantic_flag_generated",
                    category=extracted_clause.category,
                    severity=severity,
                    reason=reason
                )

        except Exception as e:
            logger.error("gemini_deviation_analysis_failed", error=str(e), category=extracted_clause.category)
            # Safe fallback: if similarity is significantly different from baseline (<0.85), flag for review
            if similarity_score and similarity_score < 0.85:
                generated_flags.append(
                    RiskFlag(
                        document_id=doc_uuid,
                        extracted_clause_id=extracted_clause.id,
                        standard_clause_id=standard_clause_id,
                        flag_type="SEMANTIC_DEVIATION",
                        severity="HIGH",
                        flag_reason=f"Semantic intent deviates from standard corporate policy (Similarity: {similarity_score}).",
                        similarity_score=similarity_score,
                        ai_model_version="gemini-embedding-001-fallback",
                        evidence_text=extracted_clause.raw_text,
                        baseline_text=match_data["standard_text"]
                    )
                )
            
    # 4. Pipeline Concurrency: Generate Redlines in Parallel for all flags
    if generated_flags:
        logger.info("triggering_redline_engine", flag_count=len(generated_flags))
        
        redline_tasks = [
            generate_redline_for_flag(flag) 
            for flag in generated_flags 
            if flag.baseline_text
        ]
        
        if redline_tasks:
            completed_flags = await asyncio.gather(*redline_tasks, return_exceptions=True)
            valid_flags = [f for f in completed_flags if isinstance(f, RiskFlag)]
            
            # Map updated redline flags back
            updated_map = {f.id: f for f in valid_flags}
            generated_flags = [updated_map.get(flag.id, flag) for flag in generated_flags]
            logger.info("redlines_generated_successfully", count=len(valid_flags))
        
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
    
    if bounded_score == 0:
        risk_level = "LOW"
    elif bounded_score < 25:
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