import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped["Role"] = relationship(back_populates="users")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    feedback_entries: Mapped[list["Feedback"]] = relationship(back_populates="user")


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    criticality: Mapped[int] = mapped_column(Integer, default=3)
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    install_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="operational")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sensor_readings: Mapped[list["SensorData"]] = relationship(back_populates="equipment")
    maintenance_records: Mapped[list["MaintenanceRecord"]] = relationship(back_populates="equipment")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="equipment")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="equipment")
    health_scores: Mapped[list["EquipmentHealthScore"]] = relationship(back_populates="equipment")
    failure_history: Mapped[list["FailureHistory"]] = relationship(back_populates="equipment")
    logbook_entries: Mapped[list["LogbookEntry"]] = relationship(back_populates="equipment")
    delay_logs: Mapped[list["DelayLog"]] = relationship(back_populates="equipment")


class SensorData(Base):
    __tablename__ = "sensor_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    temperature: Mapped[float | None] = mapped_column(Float)
    vibration: Mapped[float | None] = mapped_column(Float)
    pressure: Mapped[float | None] = mapped_column(Float)
    motor_current: Mapped[float | None] = mapped_column(Float)
    health_indicator: Mapped[float | None] = mapped_column(Float)
    raw_data: Mapped[dict | None] = mapped_column(JSON, default=dict)

    equipment: Mapped["Equipment"] = relationship(back_populates="sensor_readings")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    maintenance_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    performed_by: Mapped[str | None] = mapped_column(String(255))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_hours: Mapped[float | None] = mapped_column(Float)
    cost: Mapped[float | None] = mapped_column(Float)
    outcome: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)

    equipment: Mapped["Equipment"] = relationship(back_populates="maintenance_records")


class FailureHistory(Base):
    __tablename__ = "failure_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    failure_type: Mapped[str] = mapped_column(String(100))
    fault_code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    downtime_hours: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolution: Mapped[str | None] = mapped_column(Text)

    equipment: Mapped["Equipment"] = relationship(back_populates="failure_history")


class SparePart(Base):
    __tablename__ = "spare_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_type: Mapped[str | None] = mapped_column(String(100))
    quantity_available: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=5)
    unit_cost: Mapped[float | None] = mapped_column(Float)
    supplier: Mapped[str | None] = mapped_column(String(255))
    lead_time_days: Mapped[int] = mapped_column(Integer, default=14)


class ProcurementRequest(Base):
    __tablename__ = "procurement_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spare_part_id: Mapped[int] = mapped_column(ForeignKey("spare_parts.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    urgency: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50))
    equipment_type: Mapped[str | None] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(500))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    level: Mapped[AlertLevel] = mapped_column(Enum(AlertLevel, native_enum=False), index=True)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus, native_enum=False), default=AlertStatus.OPEN)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100))
    risk_level: Mapped[RiskLevel | None] = mapped_column(Enum(RiskLevel, native_enum=False))
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    equipment: Mapped["Equipment"] = relationship(back_populates="alerts")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    failure_probability: Mapped[float] = mapped_column(Float)
    degradation_score: Mapped[float] = mapped_column(Float)
    remaining_useful_life_hours: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, native_enum=False))
    model_version: Mapped[str] = mapped_column(String(50))
    features_used: Mapped[dict | None] = mapped_column(JSON, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="predictions")


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    sensor_type: Mapped[str] = mapped_column(String(50))
    anomaly_score: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[dict | None] = mapped_column(JSON, default=dict)


class EquipmentHealthScore(Base):
    __tablename__ = "equipment_health_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    health_score: Mapped[float] = mapped_column(Float)
    degradation_trend: Mapped[str | None] = mapped_column(String(50))
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, native_enum=False))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="health_scores")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(back_populates="conversation")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"))
    query: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(50), index=True)
    fault_type: Mapped[str | None] = mapped_column(String(100), index=True)
    rating: Mapped[int | None] = mapped_column(Integer)
    correction: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(String(255))
    approved: Mapped[bool | None] = mapped_column(Boolean)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="feedback_entries")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    content: Mapped[dict] = mapped_column(JSON)
    generated_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationHistory(Base):
    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))
    channel: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LogbookEntry(Base):
    __tablename__ = "logbook_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    entry_type: Mapped[str] = mapped_column(String(50))  # alert, diagnosis, schedule, report, feedback, ...
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    observed_by: Mapped[str | None] = mapped_column(String(255))
    source_event: Mapped[str | None] = mapped_column(String(80), index=True)
    source_id: Mapped[int | None] = mapped_column(Integer, index=True)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="logbook_entries")


class DelayLog(Base):
    __tablename__ = "delay_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    delay_hours: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    fault_code: Mapped[str | None] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    equipment: Mapped["Equipment"] = relationship(back_populates="delay_logs")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class EquipmentDependency(Base):
    """Process / utility dependency edges for failure cascade modelling."""

    __tablename__ = "equipment_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upstream_equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    downstream_equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    dependency_type: Mapped[str] = mapped_column(String(50), default="process_flow")
    impact_weight: Mapped[float] = mapped_column(Float, default=0.8)
    production_share_pct: Mapped[float] = mapped_column(Float, default=50.0)
    description: Mapped[str | None] = mapped_column(Text)

    upstream: Mapped["Equipment"] = relationship(foreign_keys=[upstream_equipment_id])
    downstream: Mapped["Equipment"] = relationship(foreign_keys=[downstream_equipment_id])


class FailureScenarioRun(Base):
    """Persisted failure scenario simulation for audit and learning."""

    __tablename__ = "failure_scenario_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    failure_mode: Mapped[str] = mapped_column(String(80))
    assume_no_spare: Mapped[bool] = mapped_column(Boolean, default=False)
    defer_maintenance_days: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    equipment: Mapped["Equipment"] = relationship()
    user: Mapped["User | None"] = relationship()
