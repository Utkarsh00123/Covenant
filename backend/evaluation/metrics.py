import structlog
import re
from typing import List, Dict, Any

logger = structlog.get_logger(__name__)

def normalize_text(text: str) -> str:
    """
    Strips arbitrary formatting, newlines, and double spaces from PDF/LLM outputs 
    to prevent cosmetic formatting from ruining the evaluation metrics.
    """
    if not text:
        return ""
    return re.sub(r'\s+', ' ', str(text)).strip().lower()

def calculate_classification_metrics(predictions: List[Dict[str, Any]], ground_truths: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates Precision, Recall, and F1-Score for the risk extraction pipeline.
    """
    tp = 0
    fp = 0
    fn = 0
    
    # We track hits to ensure we don't double-count ground truths
    matched_truths = set()
    
    for pred in predictions:
        match_found = False
        for i, truth in enumerate(ground_truths):
            if i in matched_truths:
                continue
                
            # 1. Strict Category and Severity Matching
            if pred.get("category") == truth.get("category") and pred.get("severity") == truth.get("severity"):
                
                # 2. Robust Evidence Text Matching
                pred_text = normalize_text(pred.get("evidence_text", ""))
                truth_text = normalize_text(truth.get("must_contain_text", ""))
                
                if truth_text in pred_text:
                    tp += 1
                    matched_truths.add(i)
                    match_found = True
                    break
                    
        if not match_found:
            # AI hallucinated a risk, misclassified severity, or extracted the wrong text entirely
            fp += 1 
            
    # Any ground truth risks that were never caught by a prediction are False Negatives
    fn = len(ground_truths) - len(matched_truths)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4)
    }