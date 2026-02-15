from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class CPGChunk(BaseModel):
    """
    The core data model for a medical guideline chunk.
    Matches the 'NotebookLM' philosophy of keeping source and context inseparable.
    """
    chunk_id: str = Field(..., description="Unique hash of the content")
    content: str = Field(..., description="The actual text or markdown table")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Includes page_num, source_file, and layout_type (text/table)"
    )

class RetrievalHit(BaseModel):
    """Result from the hybrid search + reranking pipeline."""
    content: str
    score: float  # Re-ranked score
    source: str
    page: Optional[int]
    layout_type: str = "text"