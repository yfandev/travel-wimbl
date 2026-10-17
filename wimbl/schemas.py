from typing import Literal
from pydantic import BaseModel, Field

class TripRequest(BaseModel):
    interest: str = Field(min_length=2, max_length=80)
    origin: str = Field(default="SFO", min_length=3, max_length=80)
    budget: float = Field(default=2500, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    days: int = Field(default=4, ge=1, le=21)
    dates: str | None = None
    traveler_context: str | None = Field(default=None, max_length=1000)

class Evidence(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source: str = "You.com"
    retrieved_at: str
    verified: bool = False
    page_age: str | None = None
    provider_request_id: str | None = None
    cache_hit: bool = False

class TripCandidate(BaseModel):
    title: str
    destination: str
    event: str
    dates: str | None = None
    estimated_total: float | None = None
    currency: str = "USD"
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    status: Literal["candidate", "verified", "needs_review", "rejected"] = "candidate"

class VerificationFinding(BaseModel):
    severity: Literal["info", "warning", "error"]
    code: str
    message: str

class TripResult(BaseModel):
    run_id: str
    interest: str
    status: Literal["verified", "needs_review", "no_results", "error"]
    acceptance_criteria: list[str]
    candidates: list[TripCandidate]
    findings: list[VerificationFinding]
    controller_decision: Literal["stop", "replan", "escalate"]
    steps: list[str]
