import re
from typing import List, Dict, Any

def run_keyword_baseline(document_text: str) -> List[Dict[str, Any]]:
    """
    A naive regex/keyword scanner representing legacy LegalTech software.
    We will use this to prove that our Hybrid AI Engine is mathematically superior 
    by calculating the difference in Recall and F1-Scores.
    """
    flags = []
    
    # Baseline Rule 1: Naive Liability Search
    # Using re.DOTALL because PDF extraction often inserts arbitrary \n mid-sentence.
    # This will still fail if the contract says "capped at 100 USD".
    if re.search(r"liability.*?not exceed.*?(one hundred dollars|\$100)", document_text, re.IGNORECASE | re.DOTALL):
        flags.append({
            "category": "LIABILITY_CAP",
            "severity": "CRITICAL",
            "must_contain_text": "liability not exceed $100", 
            "trigger": "Regex match on $100 liability"
        })
        
    # Baseline Rule 2: Naive Auto-Renewal Search
    # This will still fail if the contract says "shall endure for two years automatically".
    if re.search(r"renew.*?for.*?(24|twenty-four).*?months", document_text, re.IGNORECASE | re.DOTALL):
        flags.append({
            "category": "AUTO_RENEWAL",
            "severity": "HIGH",
            "must_contain_text": "renew for successive periods of twenty-four (24) months",
            "trigger": "Regex match on 24 months"
        })
        
    # Baseline Rule 3: Naive Payment Terms
    # Added to demonstrate coverage. Fails if the contract says "payable within three months".
    if re.search(r"net\s*90", document_text, re.IGNORECASE):
        flags.append({
            "category": "PAYMENT_TERMS",
            "severity": "MEDIUM",
            "must_contain_text": "Net 90",
            "trigger": "Regex match on Net 90"
        })
        
    return flags