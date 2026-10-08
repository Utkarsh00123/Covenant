import structlog
from typing import Union
from pydantic import ValidationError
from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.contract import ContractAnalysis
from app.schemas.invoice import InvoiceAnalysis
from app.schemas.extraction import ExtractedDocument

logger = structlog.get_logger(__name__)

# Initialize the native Google GenAI client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Define our system prompts
CONTRACT_SYSTEM_PROMPT = """
You are a rigorous, highly accurate legal extraction engine.
Your job is to read the provided text from a commercial agreement and extract the requested fields.
CRITICAL RULES:
1. For clauses, extract the text VERBATIM. Do not paraphrase.
2. If a field is not present in the text, return null. Do not guess.
3. Classify clauses strictly into the provided categories.
"""

INVOICE_SYSTEM_PROMPT = """
You are a highly accurate financial data extraction engine.
Extract the vendor details, amounts, and line items from the provided invoice text.
CRITICAL RULES:
1. Ensure all numeric amounts are extracted as pure floats (e.g., 1500.50, not "$1,500.50").
2. Match line item totals to the invoice subtotal.
"""

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
    if document_type.lower() == "invoice":
        response_model = InvoiceAnalysis
        system_prompt = INVOICE_SYSTEM_PROMPT
    else:
        response_model = ContractAnalysis
        system_prompt = CONTRACT_SYSTEM_PROMPT
        
    model_choice = "gemini-3.8-flash"

    try:
        # Native structured output generation with response_schema
        response = await client.aio.models.generate_content(
            model=model_choice,
            contents=f"Extract the structured data from the following document text:\n\n{full_text}",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=response_model,
                temperature=0.1,
            ),
        )
        
        # response.parsed holds the instantiated Pydantic model
        if response.parsed:
            parsed_data = response.parsed
        else:
            parsed_data = response_model.model_validate_json(response.text)
        
        logger.info("llm_extraction_successful", model=model_choice)
        return parsed_data
        
    except ValidationError as e:
        logger.error("pydantic_validation_failed", error=str(e))
        raise ValueError("The AI model returned malformed data that violated the schema.")
    except Exception as e:
        logger.error("gemini_api_error", error=str(e))
        raise RuntimeError(f"Failed to communicate with the extraction model: {str(e)}")