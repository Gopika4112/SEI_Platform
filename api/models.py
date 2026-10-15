from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any

class IngestRequest(BaseModel):
    github_url: str
    branch: Optional[str] = None

class IngestResponse(BaseModel):
    job_id: str
    status: str
    stats: Optional[Dict[str, int]] = None

class QueryRequest(BaseModel):
    question: str
    repo_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    eval_score: float
    eval_feedback: Optional[str] = None
    intent: str
