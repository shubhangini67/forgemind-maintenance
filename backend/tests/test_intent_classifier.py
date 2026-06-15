from app.services.agents.intent_classifier import (
    ASSET_RANKING,
    BUSINESS_IMPACT,
    CONVERSATIONAL,
    DIAGNOSTIC,
    FAILURE_SIMULATION,
    INVENTORY,
    MAINTENANCE_PLANNING,
    RESPONSE_TEMPLATE_BY_INTENT,
    SOP,
    classify_chat_intent,
    conversational_answer,
    is_conversational_intent,
)


def test_date_is_conversational():
    assert classify_chat_intent("What is today's date?") == CONVERSATIONAL


def test_asset_ranking_intent():
    assert classify_chat_intent("Rank all assets by remaining useful life") == ASSET_RANKING
    assert RESPONSE_TEMPLATE_BY_INTENT[ASSET_RANKING] == "asset_ranking"


def test_business_impact_intent():
    assert classify_chat_intent("How much production loss if BF-001 fails now?") == BUSINESS_IMPACT
    assert RESPONSE_TEMPLATE_BY_INTENT[BUSINESS_IMPACT] == "business_impact"


def test_critical_spares_intent():
    assert classify_chat_intent("Which spare parts are critical?") == INVENTORY


def test_failure_simulation_intent():
    assert classify_chat_intent("What happens if maintenance is delayed 7 days?") == FAILURE_SIMULATION


def test_diagnostic_query():
    assert classify_chat_intent("Analyze degradation and root cause for BF-001") == DIAGNOSTIC


def test_sop_query():
    assert classify_chat_intent("What is the SOP for bearing inspection?") == SOP


def test_planning_query():
    assert classify_chat_intent("Generate a 7-day maintenance plan") == MAINTENANCE_PLANNING


def test_risk_delay_is_simulation():
    assert classify_chat_intent("What is the operational risk if we delay maintenance?") == FAILURE_SIMULATION
