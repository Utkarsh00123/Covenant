import json
import structlog
from typing import Union
from fastapi import HTTPException
from pydantic import ValidationError
from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.contract import ContractAnalysis
from app.schemas.invoice import InvoiceAnalysis
from app.schemas.extraction import ExtractedDocument

logger = structlog.get_logger(__name__)

# Define our system prompts
CONTRACT_SYSTEM_PROMPT = """
You are a rigorous, highly accurate legal extraction engine.
Your job is to read the provided text from a commercial agreement and extract the requested fields.
CRITICAL RULES:
1. For clauses, extract the text VERBATIM. Do not paraphrase.
2. If a field is not present in the text, return null or empty list. Do not guess.
3. Classify clauses into the provided categories (e.g., LIABILITY_CAP, AUTO_RENEWAL, INDEMNIFICATION, TERMINATION_CONVENIENCE, PAYMENT_TERMS, CONFIDENTIALITY, GOVERNING_LAW, UNKNOWN).
"""

INVOICE_SYSTEM_PROMPT = """
You are a highly accurate financial data extraction engine.
Extract the vendor details, amounts, and line items from the provided invoice text.
CRITICAL RULES:
1. Ensure all numeric amounts are extracted as pure floats (e.g., 1500.50, not "$1,500.50").
2. Match line item totals to the invoice subtotal.
"""

def clean_json_text(raw: str) -> str:
    """Strips markdown code fences and cleans leading/trailing whitespace."""
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def dereference_schema(schema: dict) -> dict:
    """
    Inlines Pydantic v2 $defs and $ref references so the schema
    strictly conforms to google.genai.types.Schema requirements.
    """
    defs = schema.pop("$defs", {})
    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref_key = node["$ref"].split("/")[-1]
                target = dict(defs.get(ref_key, {}))
                return resolve(target)
            if "allOf" in node and len(node["allOf"]) == 1 and "$ref" in node["allOf"][0]:
                ref_key = node["allOf"][0]["$ref"].split("/")[-1]
                target = dict(defs.get(ref_key, {}))
                return resolve(target)
            return {k: resolve(v) for k, v in node.items()}
        elif isinstance(node, list):
            return [resolve(x) for x in node]
        return node
    return resolve(schema)

async def extract_structured_data(
    extracted_doc: ExtractedDocument, 
    document_type: str = "contract"
) -> Union[ContractAnalysis, InvoiceAnalysis]:
    """
    Takes parsed text blocks and runs them through Google GenAI Structured Outputs.
    Returns validated Pydantic models.
    """
    logger.info("starting_llm_extraction", doc_type=document_type)
    
    # Flatten text for the LLM
    full_text = "\n".join([block.text for block in extracted_doc.blocks])
    
    # Determine schemas and prompts
    is_invoice = (document_type.lower() == "invoice")
    response_model = InvoiceAnalysis if is_invoice else ContractAnalysis
    system_prompt = INVOICE_SYSTEM_PROMPT if is_invoice else CONTRACT_SYSTEM_PROMPT
    model_choice = "gemini-3.5-flash"

    # Dereference Pydantic JSON schema to remove $defs / allOf for google.genai compliance
    clean_schema = dereference_schema(response_model.model_json_schema())

    # Initialize client dynamically within the active event loop
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Default fallback models in case of unrecoverable upstream failures
    def create_fallback(err_detail: str = "empty_or_failed"):
        fallback = InvoiceAnalysis(
            vendor_name="Unidentified Vendor",
            subtotal=0.0,
            tax_amount=0.0,
            total_amount=0.0,
            line_items=[]
        ) if is_invoice else ContractAnalysis(parties=[], key_clauses=[])
        setattr(fallback, "_extraction_error", err_detail)
        return fallback

    # If document has virtually no extracted text, return clean default model directly
    if not full_text.strip():
        logger.warning("empty_document_text_detected, returning default extraction")
        return create_fallback("empty_document_text")

    response = None
    last_err_msg = ""
    # Retry once on temporary 503 high-demand spikes
    for attempt in range(2):
        try:
            response = await client.aio.models.generate_content(
                model=model_choice,
                contents=f"Extract the structured data from the following document text:\n\n{full_text}",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=clean_schema,
                    temperature=0.1,
                ),
            )
            break
        except Exception as e:
            last_err_msg = f"{type(e).__name__}: {str(e)}"
            logger.warning("gemini_call_attempt_failed", attempt=attempt + 1, error=last_err_msg)
            err_lower = str(e).lower()
            if "429" in err_lower or "resource_exhausted" in err_lower or "quota" in err_lower:
                logger.error("gemini_quota_exhausted_during_extraction", error=last_err_msg)
                raise HTTPException(
                    status_code=429,
                    detail="Google Gemini API Quota Exhausted (Error 429: RESOURCE_EXHAUSTED). You have exceeded your free tier daily quota for gemini-3.5-flash. Please retry when your quota resets."
                )
            if attempt == 1:
                logger.error("all_gemini_attempts_exhausted", error=last_err_msg)
                return create_fallback(last_err_msg)

    if not response:
        return create_fallback(last_err_msg or "no_response_from_gemini")

    # 1. Check if native parsed model is available
    try:
        if response.parsed and isinstance(response.parsed, response_model):
            logger.info("llm_extraction_successful_via_parsed", model=model_choice)
            return response.parsed
    except Exception as e:
        logger.warning("response_parsed_inspection_failed", error=str(e))

    # 2. Parse from response.text with markdown cleaning
    raw_text = clean_json_text(response.text or "{}")
    try:
        parsed_data = response_model.model_validate_json(raw_text)
        logger.info("llm_extraction_successful_via_json", model=model_choice)
        return parsed_data
    except (ValidationError, Exception) as val_err:
        logger.warning("direct_pydantic_validation_warning", error=str(val_err))
        
        # 3. Attempt loose dictionary parsing
        try:
            data_dict = json.loads(raw_text)
            if isinstance(data_dict, dict):
                parsed_data = response_model.model_validate(data_dict)
                logger.info("llm_extraction_successful_via_dict_validate", model=model_choice)
                return parsed_data
        except Exception as dict_err:
            logger.warning("loose_dict_parsing_failed", error=str(dict_err))

    # 4. Graceful fallback so document upload never crashes with 422
    logger.info("returning_graceful_fallback_model")
    return create_fallback()