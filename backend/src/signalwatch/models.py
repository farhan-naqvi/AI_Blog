from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

ShortText = Annotated[str, Field(min_length=1, max_length=500)]
ClaimText = Annotated[str, Field(min_length=1, max_length=500)]
EvidenceRole = Literal[
    "Primary announcement",
    "Documentation",
    "Repository",
    "Research paper",
    "Independent confirmation",
    "Discovery signal",
]


class EventType(StrEnum):
    RELEASE = "Release"
    RESEARCH = "Research"
    REGULATION = "Regulation"
    SECURITY = "Security"
    PARTNERSHIP = "Partnership"
    FUNDING = "Funding"
    OTHER = "Other"


class Category(StrEnum):
    MODELS = "Models"
    RESEARCH = "Research"
    DEVELOPER_TOOLS = "Developer tools"
    INFRASTRUCTURE = "Infrastructure"
    AGENTS = "Agents"
    SECURITY = "Security"
    ROBOTICS = "Robotics"
    REGULATION = "Regulation"
    OTHER = "Other"


EVENT_TYPE_ALIASES = {
    "release": EventType.RELEASE,
    "model release": EventType.RELEASE,
    "software release": EventType.RELEASE,
    "research": EventType.RESEARCH,
    "paper": EventType.RESEARCH,
    "policy": EventType.REGULATION,
    "regulation": EventType.REGULATION,
    "security": EventType.SECURITY,
    "vulnerability": EventType.SECURITY,
    "partnership": EventType.PARTNERSHIP,
    "funding": EventType.FUNDING,
    "other": EventType.OTHER,
}
CATEGORY_ALIASES = {
    "model": Category.MODELS,
    "models": Category.MODELS,
    "research": Category.RESEARCH,
    "developer tool": Category.DEVELOPER_TOOLS,
    "developer tools": Category.DEVELOPER_TOOLS,
    "developer tooling": Category.DEVELOPER_TOOLS,
    "open source": Category.DEVELOPER_TOOLS,
    "infrastructure": Category.INFRASTRUCTURE,
    "ai infrastructure": Category.INFRASTRUCTURE,
    "agents": Category.AGENTS,
    "ai agents": Category.AGENTS,
    "security": Category.SECURITY,
    "ai security": Category.SECURITY,
    "security vulnerability": Category.SECURITY,
    "robotics": Category.ROBOTICS,
    "regulation": Category.REGULATION,
    "policy": Category.REGULATION,
    "other": Category.OTHER,
}


def _enum_alias(value: Any, aliases: dict[str, StrEnum]) -> Any:
    if isinstance(value, str):
        cleaned = " ".join(value.replace("_", " ").replace("-", " ").split())
        return aliases.get(cleaned.casefold(), cleaned)
    return value


def _optional_text(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = " ".join(value.split())
        return cleaned or None
    return value


def _bounded_text_list(value: Any, limit: int) -> Any:
    if not isinstance(value, list):
        return value
    result: list[Any] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            item = " ".join(item.split())
            if not item:
                continue
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
        result.append(item)
        if len(result) == limit:
            break
    return result


class FactualExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_type: EventType
    organisation: str | None = Field(default=None, max_length=200)
    product: str | None = Field(default=None, max_length=200)
    release_date: date | None = None
    category: Category
    factual_summary: str = Field(min_length=20, max_length=900)
    confirmed_claims: list[ClaimText] = Field(default_factory=list, max_length=8)
    reported_claims: list[ClaimText] = Field(default_factory=list, max_length=8)
    limitations: list[ClaimText] = Field(default_factory=list, max_length=6)

    @field_validator("event_type", mode="before")
    @classmethod
    def normalize_event_type(cls, value: Any) -> Any:
        return _enum_alias(value, EVENT_TYPE_ALIASES)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: Any) -> Any:
        return _enum_alias(value, CATEGORY_ALIASES)

    @field_validator("organisation", "product", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        return _optional_text(value)

    @field_validator("release_date", mode="before")
    @classmethod
    def normalize_release_date(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            try:
                return date.fromisoformat(cleaned)
            except ValueError:
                try:
                    return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date()
                except ValueError:
                    return cleaned
        return value

    @field_validator("confirmed_claims", "reported_claims", "limitations", mode="before")
    @classmethod
    def normalize_factual_lists(cls, value: Any, info) -> Any:
        limits = {"confirmed_claims": 8, "reported_claims": 8, "limitations": 6}
        return _bounded_text_list(value, limits[info.field_name])


class DevelopmentAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    why_it_matters: str = Field(min_length=20, max_length=900)
    what_changed: str | None = Field(default=None, max_length=900)
    affected_groups: list[ShortText] = Field(default_factory=list, max_length=8)
    watch_next: list[ShortText] = Field(default_factory=list, max_length=8)
    importance_label: Literal["Major", "Notable", "Incremental"] = "Incremental"
    importance_reasons: list[ShortText] = Field(default_factory=list, max_length=6)

    @field_validator("what_changed", mode="before")
    @classmethod
    def normalize_optional_change(cls, value: Any) -> Any:
        return _optional_text(value)

    @field_validator("affected_groups", "watch_next", "importance_reasons", mode="before")
    @classmethod
    def normalize_analysis_lists(cls, value: Any, info) -> Any:
        limits = {"affected_groups": 8, "watch_next": 8, "importance_reasons": 6}
        return _bounded_text_list(value, limits[info.field_name])


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


class ReleaseMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    repository: str = Field(min_length=3, max_length=200)
    organisation: str = Field(min_length=1, max_length=100)
    release_tag: str = Field(min_length=1, max_length=120)
    release_title: str = Field(min_length=1, max_length=300)
    published_date: date | None = None
    prerelease: bool = False
    official_repository_release: bool = False


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
    release_metadata: ReleaseMetadata | None = None

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

    event_type: EventType
    organisation: str | None = Field(default=None, max_length=200)
    product: str | None = Field(default=None, max_length=200)
    release_date: date | None = None
    category: Category
    headline: str = Field(min_length=8, max_length=240)
    confirmed_claims: list[ShortText] = Field(default_factory=list, max_length=12)
    reported_claims: list[ShortText] = Field(default_factory=list, max_length=12)
    limitations: list[ShortText] = Field(default_factory=list, max_length=10)
    summary: str = Field(min_length=40, max_length=1600)
    why_it_matters: str = Field(min_length=20, max_length=1400)
    what_changed: str | None = Field(default=None, max_length=1400)
    who_affected: str = Field(default="", max_length=800)
    watch_next: str = Field(default="", max_length=800)
    confidence_reasons: list[ShortText] = Field(default_factory=list, max_length=8)
    importance_reasons: list[ShortText] = Field(default_factory=list, max_length=8)
    importance_label: Literal["Major", "Notable", "Incremental"]
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=12)

    @field_validator("event_type", mode="before")
    @classmethod
    def normalize_final_event_type(cls, value: Any) -> Any:
        return _enum_alias(value, EVENT_TYPE_ALIASES)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_final_category(cls, value: Any) -> Any:
        return _enum_alias(value, CATEGORY_ALIASES)

    @field_validator("release_date")
    @classmethod
    def release_date_is_not_future(cls, value: date | None) -> date | None:
        if value and value > datetime.now(UTC).date():
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
