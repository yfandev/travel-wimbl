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

class Fact(BaseModel):
    """An extracted claim: one value, the page it came from, and a verbatim quote that code checks on that page."""
    kind: str
    value: str
    amount: float | None = None
    currency: str | None = None
    url: str
    title: str = ""
    quote: str = ""
    observed_at: str
    source: str = "You.com Research"
    official: bool = False
    cache_hit: bool = False
    verified: bool = False
    check: str = "not checked"

class TicketAdvice(BaseModel):
    """The tickets child's reading of the facts. Its model output is advice; it never sets a fact's verified flag."""
    official_source_url: str
    recommended_channel: str
    unofficial_sources: list[str]
    price_is_live: bool
    risks: list[str]
    model: str | None = None

class PriceLine(BaseModel):
    """One package line item. An amount is the advertised price copied from its source with the sentence it came from;
    it is never estimated, converted or claimed as live inventory."""
    item: Literal["tickets", "flight", "hotel"]
    label: str
    status: Literal["advertised", "not_published", "not_searched"]
    amount: float | None = None
    currency: str | None = None
    quantity: int = 1
    unit: str = ""
    subtotal: float | None = None
    url: str | None = None
    title: str = ""
    quote: str = ""
    observed_at: str | None = None
    via: str = ""
    official: bool = False
    note: str = ""
    sources_checked: list[str] = Field(default_factory=list)

class PriceTotal(BaseModel):
    """Computed sum of the priced line items in the trip currency. complete is True only when every line is priced."""
    currency: str
    amount: float | None
    priced: int
    lines: int
    complete: bool
    other_currencies: dict[str, float] = Field(default_factory=dict)
    label: str = "advertised price, not live inventory"

class TripCandidate(BaseModel):
    title: str
    destination: str
    event: str
    dates: str | None = None
    estimated_total: float | None = None
    currency: str = "USD"
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    ticket_advice: TicketAdvice | None = None
    line_items: list[PriceLine] = Field(default_factory=list)
    price_total: PriceTotal | None = None
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
