import re
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)

def _extract_renewal_months(text_lower: str, data: Dict[str, Any]) -> Optional[int]:
    """Extracts renewal duration in months from structured data or regex."""
    if data.get("renewal_period_months") is not None:
        try:
            return int(data["renewal_period_months"])
        except (ValueError, TypeError):
            pass

    # Word-based year patterns
    if "two year" in text_lower or "2 year" in text_lower or "2-year" in text_lower or "two (2) year" in text_lower:
        return 24
    if "three year" in text_lower or "3 year" in text_lower or "3-year" in text_lower or "three (3) year" in text_lower:
        return 36
    if "five year" in text_lower or "5 year" in text_lower or "5-year" in text_lower:
        return 60
    if "one year" in text_lower or "1 year" in text_lower or "1-year" in text_lower or "one (1) year" in text_lower or "twelve (12) month" in text_lower:
        return 12

    # Regex for years: e.g. "for an additional 2 years", "periods of 3 years"
    year_match = re.search(r"(?:renew(?:al|s|ed)?\s+(?:for\s+)?(?:successive\s+)?(?:terms?\s+of\s+)?(?:additional\s+)?(\d+)\s*(?:years?|yrs?))", text_lower)
    if year_match:
        return int(year_match.group(1)) * 12

    # Regex for months: e.g. "renew for 24 months", "periods of 18 months"
    month_match = re.search(r"(?:renew(?:al|s|ed)?\s+(?:for\s+)?(?:successive\s+)?(?:terms?\s+of\s+)?(?:additional\s+)?(\d+)\s*months?)", text_lower)
    if month_match:
        return int(month_match.group(1))

    # General month pattern in text
    gen_month = re.search(r"(\d+)\s*months?", text_lower)
    if gen_month and ("renew" in text_lower or "successive" in text_lower or "term" in text_lower):
        return int(gen_month.group(1))

    return None

def _extract_notice_days(text_lower: str, data: Dict[str, Any]) -> Optional[int]:
    """Extracts cancellation / termination notice period in days."""
    if data.get("notice_period_days") is not None:
        try:
            return int(data["notice_period_days"])
        except (ValueError, TypeError):
            pass

    # e.g., "written notice of 90 days", "at least 60 days prior notice", "30 days' advance notice"
    notice_match = re.search(r"(\d+)\s*(?:business\s+)?days?(?:'|\s+written|\s+prior|\s+advance)?(?:\s+written)?\s*notice", text_lower)
    if notice_match:
        return int(notice_match.group(1))

    notice_alt = re.search(r"notice\s+of\s+(?:at\s+least\s+)?(\d+)\s*days", text_lower)
    if notice_alt:
        return int(notice_alt.group(1))

    return None

def _extract_payment_days(text_lower: str, data: Dict[str, Any]) -> Optional[int]:
    """Extracts payment terms in days (e.g. Net 30, 45 days)."""
    if data.get("payment_terms_days") is not None:
        try:
            return int(data["payment_terms_days"])
        except (ValueError, TypeError):
            pass

    net_match = re.search(r"net\s*(\d+)", text_lower)
    if net_match:
        return int(net_match.group(1))

    due_match = re.search(r"(?:within|in|due)\s*(\d+)\s*(?:calendar\s+|business\s+)?days", text_lower)
    if due_match:
        return int(due_match.group(1))

    return None

def evaluate_deterministic_rules(
    extracted_category: str, 
    extracted_text: str, 
    acceptable_ranges: Dict[str, Any],
    llm_structured_data: Dict[str, Any] | None = None
) -> List[Dict[str, Any]]:
    """
    Executes deterministic checks against extracted contract clauses.
    Validates numbers, thresholds, and strict legal requirements against company standard policy.
    """
    flags: List[Dict[str, Any]] = []
    
    if not acceptable_ranges:
        logger.debug("no_acceptable_ranges_provided", category=extracted_category)
        return flags

    data = llm_structured_data or {}
    text_lower = extracted_text.lower()

    # -------------------------------------------------------------------------
    # RULE 1: AUTO_RENEWAL
    # -------------------------------------------------------------------------
    if extracted_category == "AUTO_RENEWAL":
        max_months = acceptable_ranges.get("max_renewal_months", 12)
        min_notice = acceptable_ranges.get("min_notice_days", 30)
        max_notice = acceptable_ranges.get("max_notice_days", 90)

        renewal_months = _extract_renewal_months(text_lower, data)
        if renewal_months is not None and renewal_months > max_months:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "HIGH",
                "reason": f"Renewal period ({renewal_months} months) exceeds corporate standard of max {max_months} months, causing potential vendor lock-in."
            })

        notice_days = _extract_notice_days(text_lower, data)
        if notice_days is not None:
            if notice_days > max_notice:
                flags.append({
                    "flag_type": "DETERMINISTIC_RULE",
                    "severity": "HIGH",
                    "reason": f"Cancellation notice period ({notice_days} days) exceeds maximum {max_notice} days, creating a renewal trap."
                })
            elif notice_days < min_notice:
                flags.append({
                    "flag_type": "DETERMINISTIC_RULE",
                    "severity": "MEDIUM",
                    "reason": f"Cancellation notice period ({notice_days} days) is shorter than required minimum of {min_notice} days."
                })

    # -------------------------------------------------------------------------
    # RULE 2: LIABILITY_CAP
    # -------------------------------------------------------------------------
    elif extracted_category == "LIABILITY_CAP":
        unlimited_allowed = acceptable_ranges.get("unlimited_allowed", False)
        
        # Check for explicit uncapped / unlimited phrasing
        uncapped_patterns = [
            "unlimited liability",
            "shall not be limited",
            "no limitation on liability",
            "no limitation of liability",
            "without limitation as to amount",
            "without limitation of liability",
            "not subject to any liability cap",
            "no cap on liability"
        ]
        has_uncapped = any(p in text_lower for p in uncapped_patterns)

        # Check for one-sided liability cap
        one_sided = (
            ("customer's liability shall not be limited" in text_lower or "client's liability shall not be limited" in text_lower) or
            ("vendor's liability shall be limited" in text_lower and "customer" in text_lower and not ("each party" in text_lower or "either party" in text_lower))
        )

        is_capped = data.get("is_liability_capped")

        if not unlimited_allowed and has_uncapped:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "CRITICAL",
                "reason": "Liability is explicitly uncapped or unlimited, exposing the company to catastrophic commercial damage."
            })
        elif one_sided:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "CRITICAL",
                "reason": "One-sided liability limitation detected: Customer liability is uncapped while Vendor liability is strictly capped."
            })
        elif is_capped is False and not unlimited_allowed:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "CRITICAL",
                "reason": "Liability appears to be uncapped, in direct violation of standard company policy."
            })

    # -------------------------------------------------------------------------
    # RULE 3: PAYMENT_TERMS
    # -------------------------------------------------------------------------
    elif extracted_category == "PAYMENT_TERMS":
        min_payment_days = acceptable_ranges.get("min_payment_days", 30)
        max_late_fee = acceptable_ranges.get("max_late_fee_percent", 1.5)

        payment_days = _extract_payment_days(text_lower, data)
        if payment_days is not None:
            if payment_days < min_payment_days:
                flags.append({
                    "flag_type": "DETERMINISTIC_RULE",
                    "severity": "MEDIUM",
                    "reason": f"Payment terms ({payment_days} days) are shorter than the standard minimum of Net {min_payment_days}."
                })
            elif payment_days > 60:
                flags.append({
                    "flag_type": "DETERMINISTIC_RULE",
                    "severity": "MEDIUM",
                    "reason": f"Payment window ({payment_days} days) exceeds standard commercial terms of Net 30/60."
                })

        # Check predatory late fees
        fee_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:per\s+month|monthly|interest|late)", text_lower)
        if fee_match:
            try:
                fee = float(fee_match.group(1))
                if fee > max_late_fee:
                    flags.append({
                        "flag_type": "DETERMINISTIC_RULE",
                        "severity": "MEDIUM",
                        "reason": f"Late payment interest of {fee}% per month exceeds standard policy maximum of {max_late_fee}%."
                    })
            except ValueError:
                pass

    # -------------------------------------------------------------------------
    # RULE 4: TERMINATION_CONVENIENCE
    # -------------------------------------------------------------------------
    elif extracted_category == "TERMINATION_CONVENIENCE":
        requires_mutual = acceptable_ranges.get("requires_mutual", True)
        max_notice = acceptable_ranges.get("max_notice_days", 60)

        # Check for unilateral termination for convenience
        unilateral_vendor = (
            ("vendor may terminate" in text_lower or "company may terminate" in text_lower or "provider may terminate" in text_lower) and
            not ("either party" in text_lower or "each party" in text_lower or "mutual" in text_lower or "customer may terminate" in text_lower or "client may terminate" in text_lower)
        )
        if requires_mutual and unilateral_vendor:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "HIGH",
                "reason": "Unilateral termination for convenience right detected. Standard policy mandates mutual termination rights."
            })

        notice_days = _extract_notice_days(text_lower, data)
        if notice_days is not None and notice_days > max_notice:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "MEDIUM",
                "reason": f"Termination notice period ({notice_days} days) exceeds standard maximum of {max_notice} days."
            })

    # -------------------------------------------------------------------------
    # RULE 5: INDEMNIFICATION
    # -------------------------------------------------------------------------
    elif extracted_category == "INDEMNIFICATION":
        mutual_required = acceptable_ranges.get("mutual_required", True)

        # Unilateral indemnification
        unilateral_customer = (
            ("customer shall indemnify" in text_lower or "client shall indemnify" in text_lower or "buyer shall indemnify" in text_lower) and
            not ("each party" in text_lower or "mutual" in text_lower or "vendor shall indemnify" in text_lower or "provider shall indemnify" in text_lower or "seller shall indemnify" in text_lower)
        )
        if mutual_required and unilateral_customer:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "HIGH",
                "reason": "One-sided indemnification obligation detected. Standard policy requires mutual indemnification."
            })

        # Overly broad consequential / punitive damages in indemnity
        if any(d in text_lower for d in ["consequential damages", "punitive damages", "indirect damages", "loss of profits"]) and "indemnif" in text_lower:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "HIGH",
                "reason": "Indemnity scope extends to indirect, punitive, or consequential damages, creating severe financial risk."
            })

    # -------------------------------------------------------------------------
    # RULE 6: CONFIDENTIALITY
    # -------------------------------------------------------------------------
    elif extracted_category == "CONFIDENTIALITY":
        max_years = acceptable_ranges.get("max_years", 3)

        # Check perpetual survival for non-trade secret information
        is_perpetual = any(p in text_lower for p in ["in perpetuity", "perpetual obligation", "shall survive indefinitely", "indefinite period"])
        if is_perpetual:
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "MEDIUM",
                "reason": f"Perpetual confidentiality restriction exceeds the company standard maximum duration of {max_years} years."
            })

        years_match = re.search(r"(\d+)\s*(?:years?|yrs?)", text_lower)
        if years_match:
            try:
                yrs = int(years_match.group(1))
                if yrs > max_years:
                    flags.append({
                        "flag_type": "DETERMINISTIC_RULE",
                        "severity": "MEDIUM",
                        "reason": f"Confidentiality duration ({yrs} years) exceeds the acceptable maximum of {max_years} years."
                    })
            except ValueError:
                pass

    # -------------------------------------------------------------------------
    # RULE 7: GOVERNING_LAW
    # -------------------------------------------------------------------------
    elif extracted_category == "GOVERNING_LAW":
        acceptable_states = [s.lower() for s in acceptable_ranges.get("acceptable_states", ["delaware", "new york", "california"])]

        # Check foreign jurisdictions
        foreign_forums = ["england", "wales", "singapore", "hong kong", "cayman", "germany", "france", "switzerland", "india", "japan"]
        if any(f in text_lower for f in foreign_forums):
            flags.append({
                "flag_type": "DETERMINISTIC_RULE",
                "severity": "MEDIUM",
                "reason": "Non-domestic / foreign governing law jurisdiction detected, drastically increasing dispute litigation expense."
            })

    logger.info(
        "deterministic_rules_evaluated",
        category=extracted_category,
        flags_count=len(flags),
        reasons=[f["reason"] for f in flags]
    )

    return flags