import difflib
import re
from typing import List, Dict

def generate_word_level_diff(original: str, redline: str) -> List[Dict[str, str]]:
    """
    Compares two strings word-by-word and generates a structured array of operations
    for the Next.js Track Changes UI.
    
    Output format: 
    [
        {"operation": "equal", "text": "The liability shall "},
        {"operation": "delete", "text": "not "},
        {"operation": "insert", "text": "only "},
        {"operation": "equal", "text": "be capped at..."}
    ]
    """
    if not original and not redline:
        return []
    if not original:
        return [{"operation": "insert", "text": redline}]
    if not redline:
        return [{"operation": "delete", "text": original}]

    # Regex tokenization: splits by whitespace while retaining words and delimiters
    # Keeps punctuation attached to words without collapsing newlines/indentation
    a_tokens = re.findall(r'\S+|\s+', original)
    b_tokens = re.findall(r'\S+|\s+', redline)
    
    matcher = difflib.SequenceMatcher(None, a_tokens, b_tokens)
    diff_output: List[Dict[str, str]] = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            diff_output.append({
                "operation": "equal",
                "text": "".join(a_tokens[i1:i2])
            })
        elif tag == 'replace':
            diff_output.append({
                "operation": "delete",
                "text": "".join(a_tokens[i1:i2])
            })
            diff_output.append({
                "operation": "insert",
                "text": "".join(b_tokens[j1:j2])
            })
        elif tag == 'delete':
            diff_output.append({
                "operation": "delete",
                "text": "".join(a_tokens[i1:i2])
            })
        elif tag == 'insert':
            diff_output.append({
                "operation": "insert",
                "text": "".join(b_tokens[j1:j2])
            })
            
    return diff_output