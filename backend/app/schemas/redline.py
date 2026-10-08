from pydantic import BaseModel, Field
from typing import List, Literal

class DiffOperation(BaseModel):
    """Schema for individual redline edits."""
    operation: Literal["insert", "delete", "replace"] = Field(
        description="The type of edit. Must be exactly 'insert', 'delete', or 'replace'."
    )
    text: str = Field(
        description="The exact text string being inserted, deleted, or replaced."
    )

class RedlineSuggestion(BaseModel):
    """Schema enforcing the exact output structure for the Counterfactual Engine."""
    suggested_rewrite: str = Field(
        description="The surgically edited clause. Preserve original tone and capitalized terms. Only change what is necessary to mitigate the risk."
    )
    plain_english_explanation: str = Field(
        description="A 1-to-2 sentence explanation of WHY this edit was made and how it protects the user. Use simple, non-legal language."
    )
    redline_diff: List[DiffOperation] = Field(
        description="A sequential list of the exact edits made to transform the original text into the suggested rewrite."
    )