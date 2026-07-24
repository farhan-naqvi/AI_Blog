from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

ShortText = Annotated[str, Field(min_length=1, max_length=500)]
EvidenceRole = Literal[
    "Primary announcement",
    "Documentation",
    "Repository",
    "Research paper",
    "Independent confirmation",
    "Discovery signal",
]


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    base_url: AnyHttpUrl
    source_type: str
    retrieval_method: str
    connector_key: str
    is_primary_source: bool
    reliability_level: Literal["High", "Medium", "Low"]
    poll_interval_minutes: int
    rate_limit_per_hour: int
    active: bool = True
    etag: str | None = None
    last_modified: str | None = None
    connector_config: dict = Field(default_factory=dict)


class CollectedItem(BaseModel):
    source_id: str
    source_identifier: str | None = Field(default=None, max_length=500)
    url: AnyHttpUrl
    canonical_url: AnyHttpUrl | None = None
    title: str = Field(min_length=3, max_length=500)
    published_at: datetime | None = None
    excerpt: str = Field(default="", max_length=1200)
    event_type_hint: str | None = Field(default=None, max_length=80)
    language: str = Field(default="en", max_length=12)
    content_hash: str = Field(min_length=64, max_length=64)
    title_hash: str = Field(min_length=64, max_length=64)

    @field_validator("published_at")
    @classmethod
    def publication_date_is_plausible(cls, value: datetime | None) -> datetime | None:
        comparable = value.replace(tzinfo=UTC) if value and value.tzinfo is None else value
        if comparable and comparable > datetime.now(UTC):
            raise ValueError("publication date cannot be in the future")
        return value


class EvidenceReference(BaseModel):
    source_item_id: str
    url: AnyHttpUrl
    role: EvidenceRole
    claim_indexes: list[int] = Field(default_factory=list, max_length=30)


class ExtractedDevelopment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_type: ShortText
    organisation: str | None = Field(default=None, max_length=200)
    product: str | None = Field(default=None, max_length=200)
    release_date: datetime | None = None
    category: ShortText
    headline: str = Field(min_length=8, max_length=240)
    confirmed_claims: list[ShortText] = Field(min_length=1, max_length=12)
    reported_claims: list[ShortText] = Field(default_factory=list, max_length=12)
    limitations: list[ShortText] = Field(default_factory=list, max_length=10)
    summary: str = Field(min_length=40, max_length=1600)
    why_it_matters: str = Field(min_length=20, max_length=1400)
    what_changed: str = Field(min_length=20, max_length=1400)
    who_affected: str = Field(min_length=5, max_length=800)
    watch_next: str = Field(min_length=5, max_length=800)
    confidence_reasons: list[ShortText] = Field(min_length=1, max_length=8)
    importance_reasons: list[ShortText] = Field(min_length=1, max_length=8)
    importance_label: Literal["Major", "Notable", "Incremental"]
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=12)

    @field_validator("release_date")
    @classmethod
    def release_date_is_not_future(cls, value: datetime | None) -> datetime | None:
        comparable = value.replace(tzinfo=UTC) if value and value.tzinfo is None else value
        if comparable and comparable > datetime.now(UTC):
            raise ValueError("release date cannot be in the future")
        return value

    @model_validator(mode="after")
    def confirmed_claims_have_evidence(self) -> "ExtractedDevelopment":
        supported = {index for ref in self.evidence for index in ref.claim_indexes}
        missing = set(range(len(self.confirmed_claims))) - supported
        if missing:
            raise ValueError(f"confirmed claims without evidence: {sorted(missing)}")
        return self


class VerificationDecision(BaseModel):
    verification_status: Literal["Verified", "Developing", "Held"]
    confidence_label: Literal["High", "Medium", "Low"]
    publication_status: Literal["Published", "Held", "Rejected"]
    reasons: list[str] = Field(min_length=1, max_length=10)
    exception_type: str | None = None


class LinkedinDraftOutput(BaseModel):
    content: str = Field(min_length=80, max_length=3000)
    angle: Literal["Technical", "Strategic", "Career or learning"]


class ReportOutput(BaseModel):
    title: str = Field(min_length=8, max_length=200)
    summary: str = Field(min_length=40, max_length=1200)
    body: str = Field(min_length=100, max_length=12000)
    development_ids: list[str] = Field(min_length=3, max_length=20)
