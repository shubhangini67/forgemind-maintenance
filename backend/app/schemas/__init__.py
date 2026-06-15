from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None
    email: str | None = None
    role: str | None = None


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str = Field(min_length=6)
    role_name: str = "engineer"


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role_name: str
    is_active: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class EquipmentBase(BaseModel):
    equipment_code: str
    name: str
    equipment_type: str
    location: str
    criticality: int = 3
    manufacturer: str | None = None
    status: str = "operational"


class EquipmentResponse(EquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    install_date: datetime | None = None


class SensorDataCreate(BaseModel):
    equipment_id: int
    temperature: float | None = None
    vibration: float | None = None
    pressure: float | None = None
    motor_current: float | None = None
    health_indicator: float | None = None


class SensorDataResponse(SensorDataCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    level: str
    status: str
    title: str
    message: str
    source: str
    risk_level: str | None
    created_at: datetime


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    failure_probability: float
    degradation_score: float
    remaining_useful_life_hours: float | None
    risk_level: str
    explanation: str | None
    created_at: datetime


class HealthScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    health_score: float
    degradation_trend: str | None
    risk_level: str
    computed_at: datetime


class MaintenanceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    maintenance_type: str
    description: str
    performed_at: datetime
    outcome: str | None


class SparePartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_number: str
    name: str
    quantity_available: int
    lead_time_days: int
    reorder_level: int
    unit_cost: float | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatMessageWithId(ChatMessage):
    id: int
    created_at: datetime | None = None
    follow_ups: list[str] = []


class ConversationSummary(BaseModel):
    id: int
    title: str | None
    equipment_id: int | None
    updated_at: datetime | None
    message_count: int
    preview: str | None = None


class ConversationDetail(BaseModel):
    id: int
    equipment_id: int | None
    title: str | None
    messages: list[ChatMessageWithId]


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    equipment_id: int | None = None
    page_context: str | None = None
    branch_from_message_id: int | None = None
    deep_analysis: bool = False
    user_role: str = "engineer"


class Citation(BaseModel):
    source: str
    document_type: str
    excerpt: str
    score: float


class AgentThoughtStep(BaseModel):
    agent: str
    label: str
    status: str = "complete"
    detail: str
    phase: str | None = None
    timestamp: str | None = None
    confidence: float | None = None
    data: dict[str, Any] = {}


class ReasoningDocument(BaseModel):
    source: str
    document_type: str = "document"
    excerpt: str = ""
    score: float = 0.0


class ReasoningStep(BaseModel):
    step: int
    agent: str
    label: str
    phase: str
    status: str = "complete"
    timestamp: str
    confidence: float | None = None
    summary: str
    output: dict[str, Any] = {}
    citations: list[Citation] = []
    documents: list[ReasoningDocument] = []


class AIReasoningPanel(BaseModel):
    query_intent: str | None = None
    routing_mode: str | None = None
    agent_plan: list[str] = []
    agent_trace: list[str] = []
    steps: list[ReasoningStep] = []
    total_steps: int = 0
    citations: list[Citation] = []
    llm_provider: str | None = None
    structured_summary: dict[str, Any] = {}


class ChatResponse(BaseModel):
    conversation_id: int
    message: str
    user_message_id: int | None = None
    assistant_message_id: int | None = None
    agent_trace: list[str]
    agent_thoughts: list[AgentThoughtStep] = []
    reasoning_panel: AIReasoningPanel | None = None
    llm_provider: str = "unknown"
    agent_type: str = "diagnostic"
    follow_up_suggestions: list[str] = []
    citations: list[Citation] = []
    structured_output: dict[str, Any] = {}


class DiagnosisRequest(BaseModel):
    equipment_id: int
    symptoms: str
    fault_codes: list[str] = []
    incident_description: str | None = None


class DiagnosisResponse(BaseModel):
    equipment_id: int
    equipment_code: str | None = None
    probable_causes: list[dict[str, Any]]
    root_cause_analysis: str
    ai_summary: str = ""
    confidence_score: float
    risk_level: str
    remaining_useful_life_hours: float | None = None
    failure_probability: float | None = None
    immediate_actions: list[str] = []
    short_term_actions: list[str] = []
    long_term_actions: list[str] = []
    monitoring_plan: str | None = None
    citations: list[Citation] = []
    agent_thoughts: list[dict[str, Any]] = []
    agent_trace: list[str] = []
    reasoning_panel: AIReasoningPanel | None = None
    follow_up_suggestions: list[str] = []
    llm_provider: str | None = None
    spare_stock: int | None = None
    lead_time_days: int | None = None
    procurement_risk: str | None = None
    business_impact_inr: int | None = None
    risk_escalated: bool = False
    escalation_reason: str | None = None
    critical_spare_part: str | None = None


class FeedbackCreate(BaseModel):
    conversation_id: int | None = None
    equipment_id: int | None = None
    report_id: int | None = None
    query: str | None = None
    recommendation: str | None = None
    source_type: str | None = Field(default=None, description="chat | diagnose | report")
    fault_type: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    correction: str | None = None
    outcome: str | None = None
    approved: bool | None = None


class FeedbackStatsResponse(BaseModel):
    feedback_events: int
    recommendation_accuracy_pct: float
    most_corrected_fault_type: str | None
    helpful_count: int
    not_helpful_count: int
    recent_corrections: list[str] = []


class ReportRequest(BaseModel):
    report_type: str = "maintenance"
    equipment_id: int | None = None
    title: str | None = None


class PdfExportRequest(BaseModel):
    report_type: str = Field(description="alert | priority | diagnosis | maintenance_plan | scenario | executive")
    equipment_id: int | None = None
    alert_id: int | None = None
    title: str | None = None
    payload: dict[str, Any] | None = None


class ReportResponse(BaseModel):
    id: int
    report_type: str
    title: str
    content: dict[str, Any]
    created_at: datetime


class LogbookEntryResponse(BaseModel):
    id: int
    equipment_id: int
    equipment_code: str
    entry_type: str
    source_event: str | None = None
    title: str
    description: str
    observed_by: str | None = None
    auto_generated: bool = False
    source_id: int | None = None
    metadata_json: dict[str, Any] = {}
    created_at: datetime


class LogbookSummaryResponse(BaseModel):
    total_entries: int
    auto_generated: int
    manual_entries: int
    by_type: dict[str, int]
    by_event: dict[str, int]
    coverage_pct: float
    recent: list[LogbookEntryResponse] = []


class DashboardSummary(BaseModel):
    total_equipment: int
    open_alerts: int
    critical_alerts: int
    avg_health_score: float
    high_risk_equipment: list[dict[str, Any]]
    recent_alerts: list[AlertResponse]
    bottleneck_equipment: list[dict[str, Any]]
    early_warnings: list[dict[str, Any]] = []
    recent_delay_logs: list[dict[str, Any]] = []
    data_sources: dict[str, str] = {}
