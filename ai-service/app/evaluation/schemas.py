"""Phase 13 — AI Evaluation Schemas."""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class EvaluationTestCase(BaseModel):
    id: str
    application: str = "owl"  # owl, hr-corner
    category: str
    question: str
    expected_capability: Optional[str] = None
    expected_tools: List[str] = Field(default_factory=list)
    expected_source_types: List[str] = Field(default_factory=list)  # lms, pdf, video, recommendation, none
    document_id: Optional[Union[int, str]] = None
    must_cite: bool = False
    must_not_contain: List[str] = Field(default_factory=list)
    security_expectation: Optional[str] = None  # blocked, refused, redirected, isolated
    expected_recommendation_category: Optional[str] = None
    negative_test: bool = False
    context_user_id: int = 123
    context_division: Optional[str] = None
    context_role: Optional[str] = None


class EvaluationResult(BaseModel):
    id: str
    category: str
    question: str
    status: str  # PASS, FAIL, ERROR
    tool_selection: bool = True
    retrieval: bool = True
    grounded: bool = True
    citation: bool = True
    hallucination: bool = False
    tenant_isolated: bool = True
    user_isolated: bool = True
    prompt_injection_blocked: bool = True
    latency_ms: float = 0.0
    actual_intent: Optional[str] = None
    actual_tools: List[str] = Field(default_factory=list)
    actual_source_types: List[str] = Field(default_factory=list)
    actual_message: str = ""
    error_category: Optional[str] = None
    severity: Optional[str] = None  # CRITICAL, HIGH, MEDIUM, LOW
    failure_details: Optional[str] = None


class FailureArtifact(BaseModel):
    evaluation_id: str
    category: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    question: str
    application: str
    expected_behavior: str
    actual_behavior: str
    tool_calls: List[str] = Field(default_factory=list)
    retrieved_sources: List[str] = Field(default_factory=list)
    citation: Optional[str] = None
    latency_ms: float = 0.0
    error_category: str
    root_cause: str
    recommended_fix: str


class Scorecard(BaseModel):
    tool_selection_accuracy: float = 0.0
    retrieval_recall: float = 0.0
    retrieval_precision: float = 0.0
    groundedness_rate: float = 0.0
    hallucination_rate: float = 0.0
    citation_accuracy: float = 0.0
    recommendation_filtering_accuracy: float = 1.0
    tenant_isolation_accuracy: float = 1.0
    user_isolation_accuracy: float = 1.0
    prompt_injection_protection_rate: float = 1.0


class AggregateEvaluationReport(BaseModel):
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    pass_rate: float = 0.0
    scorecard: Scorecard = Field(default_factory=Scorecard)
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    critical_failures: int = 0
    verdict: str = "PASS"  # PASS, PASS WITH WARNINGS, FAIL
    generated_at: str = ""
