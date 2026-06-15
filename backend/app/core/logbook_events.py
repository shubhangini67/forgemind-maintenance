"""Typed maintenance logbook events — single source of truth for auto-logging."""

from enum import StrEnum


class LogbookEventSource(StrEnum):
    ALERT = "alert"
    DIAGNOSIS = "diagnose"
    SCHEDULER = "scheduler"
    REPORT = "report"
    FEEDBACK = "feedback"
    CHAT = "chat"
    MANUAL = "manual"
    SYSTEM = "system"


class LogbookEventType(StrEnum):
    ALERT_CREATED = "alert.created"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"
    DIAGNOSIS_COMPLETED = "diagnosis.completed"
    MAINTENANCE_SCHEDULED = "maintenance.scheduled"
    REPORT_GENERATED = "report.generated"
    FEEDBACK_SUBMITTED = "feedback.submitted"
    AI_ANALYSIS = "ai.analysis"
    MANUAL_ENTRY = "manual.entry"


# Display category shown in UI badges / filters
EVENT_ENTRY_TYPE: dict[LogbookEventType, str] = {
    LogbookEventType.ALERT_CREATED: "alert",
    LogbookEventType.ALERT_ACKNOWLEDGED: "alert",
    LogbookEventType.ALERT_RESOLVED: "alert",
    LogbookEventType.DIAGNOSIS_COMPLETED: "diagnosis",
    LogbookEventType.MAINTENANCE_SCHEDULED: "schedule",
    LogbookEventType.REPORT_GENERATED: "report",
    LogbookEventType.FEEDBACK_SUBMITTED: "feedback",
    LogbookEventType.AI_ANALYSIS: "ai_analysis",
    LogbookEventType.MANUAL_ENTRY: "observation",
}

AUTO_EVENT_SOURCES = frozenset({
    LogbookEventType.ALERT_CREATED,
    LogbookEventType.ALERT_ACKNOWLEDGED,
    LogbookEventType.ALERT_RESOLVED,
    LogbookEventType.DIAGNOSIS_COMPLETED,
    LogbookEventType.MAINTENANCE_SCHEDULED,
    LogbookEventType.REPORT_GENERATED,
    LogbookEventType.FEEDBACK_SUBMITTED,
    LogbookEventType.AI_ANALYSIS,
})
