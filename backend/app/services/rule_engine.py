import structlog
from typing import List, Dict, Any
import re

logger = structlog.get_logger(__name__)

def _parse_first_int(text: str) -> int | None:
    """Helper fallback to extract the first integer from text if structured data is missing."""
    match = re.search(r"\b(\d+)\b", text)
    return int(match.group(1)) if match else None

def evaluate_deterministic_rules(
    extracted_category: str, 
    extracted_text: str, 
    acceptable_ranges: Dict[str, Any],
    llm_structured_data: Dict[str, Any] | None = None
) -> List[Dict[str, Any]]:
    """
    Executes deterministic checks against extracted data based on standard baselines.
    Prioritizes typed fields from Gemini structured outputs, falling back to text parsing.
    """
    flags: List[Dict[str, Any]] = []
    
    if not acceptable_ranges:
        return flags

    data = llm_structured_data or {}
    text_lower = extracted_text.lower()

    # RULE 1: Auto-Renewal Limits
    if extracted_category == "AUTO_RENEWAL":
        max_months = acceptable_ranges.get("max_renewal_months", 12)
        
        # 1. Primary: Read parsed integer from Gemini structured extraction
        renewal_months = data.get("renewal_period_months")
        
        # 2. Fallback: Parse common patterns if LLM structured field was empty
        if renewal_months is None:
            if "two year" in text_lower or "2 year" in text_lower:
                renewal_months = 24
            elif "three year" in text_lower or "3 year" in text_lower:
                renewal_months = 36
            else:
                renewal_months = _parse_first_int(text_lower)

        if renewal_months is not None and renewal_months > max_months:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "HIGH",
                "reason": f"Renewal period ({renewal_months} months) exceeds the acceptable maximum of {max_months} months."
            })

    # RULE 2: Liability Caps
    elif extracted_category == "LIABILITY_CAP":
        unlimited_allowed = acceptable_ranges.get("unlimited_allowed", False)
        
        if not unlimited_allowed:
            # 1. Primary: Evaluate boolean flag from structured extraction
            is_capped = data.get("is_liability_capped")
            
            # 2. Fallback: Check for standard exclusionary phrasing in text
            if is_capped is None:
                has_limiting_phrases = any(p in text_lower for p in ["in no event shall", "limited to", "aggregate liability", "shall not exceed"])
                is_capped = has_limiting_phrases

            if not is_capped:
                flags.append({
                    "flag_type": "DETERMINISTIC_RULE",
                    "severity": "CRITICAL",
                    "reason": "Liability appears to be uncapped, violating the standard policy."
                })

    # RULE 3: Payment Terms Stretch
    elif extracted_category == "PAYMENT_TERMS":
        max_days = acceptable_ranges.get("max_payment_days", acceptable_ranges.get("min_payment_days", 30))
        
        # 1. Primary: Read extracted payment term days
        payment_days = data.get("payment_terms_days")
        
        # 2. Fallback: Extract numeric value following 'net' or 'days'
        if payment_days is None:
            net_match = re.search(r"net\s*(\d+)", text_lower)
            if net_match:
                payment_days = int(net_match.group(1))
            else:
                day_match = re.search(r"(\d+)\s*days", text_lower)
                if day_match:
                    payment_days = int(day_match.group(1))

        if payment_days is not None and payment_days > max_days:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "MEDIUM",
                "reason": f"Payment terms ({payment_days} days) exceed standard policy of Net {max_days}."
            })

    return flags