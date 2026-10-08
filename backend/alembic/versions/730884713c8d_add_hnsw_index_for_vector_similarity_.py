"""Add HNSW index for vector similarity search

Revision ID: <YOUR_HASH>
Revises: <PREVIOUS_HASH>
Create Date: 2026-09-10
"""
from typing import Sequence, Union
from alembic import op

revision: str = '730884713c8d'
down_revision: Union[str, None] = '41ad3443776f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # m=16 and ef_construction=128 are optimized for high-recall legal search 
    # on 768-dimensional Gemini vectors. 
    # vector_cosine_ops is used because Gemini vectors are unit-normalized.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_standard_clauses_embedding 
        ON standard_clauses 
        USING hnsw (embedding vector_cosine_ops) 
        WITH (m = 16, ef_construction = 128);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_extracted_clauses_embedding 
        ON extracted_clauses 
        USING hnsw (embedding vector_cosine_ops) 
        WITH (m = 16, ef_construction = 128);
        """
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_standard_clauses_embedding;")
    op.execute("DROP INDEX IF EXISTS idx_extracted_clauses_embedding;")