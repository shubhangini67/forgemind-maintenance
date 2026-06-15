# System Architecture — SteelPlant Maintenance Wizard

## Problem Alignment

| Requirement | Implementation |
|-------------|----------------|
| LLM contextual reasoning | Gemini + LangGraph multi-agent orchestration |
| Knowledge integration | RAG over manuals, SOPs, failure reports (Qdrant) |
| Natural language interaction | Multi-turn chat with conversation history |
| Explainable recommendations | Citations, confidence scores, agent trace |
| Abnormality detection | Isolation Forest + dynamic thresholds |
| Failure prediction | XGBoost RUL model |
| Feedback loop | Feedback table + chat approval/correction |
| Real-time alerting | Alert engine on sensor ingest |

## Data Flow

1. **Sensor ingest** → PostgreSQL → ML pipeline → predictions + health scores → alerts
2. **User query** → LangGraph agents → RAG retrieval + ML context → structured response
3. **Documents** → chunk → embed (BGE-small) → Qdrant → hybrid search with reranking

## Agent Architecture

```
User Query
    │
    ▼
Document Agent (RAG)
    │
    ▼
Predictive Agent (RUL/Failure)
    │
    ▼
RCA Agent (LLM)
    │
    ▼
Spare Parts Agent (Inventory)
    │
    ▼
Planner Agent (Actions)
    │
    ▼
Alert Agent (Escalation)
    │
    ▼
Report Agent (Summary)
    │
    ▼
Synthesizer → Response + Citations
```

## Database ER (Core)

- `equipment` 1—N `sensor_data`, `maintenance_records`, `alerts`, `predictions`
- `users` N—1 `roles`
- `conversations` 1—N `conversation_messages`
- `spare_parts` ← `procurement_requests`
- `documents` → indexed in Qdrant (external)

## Assumptions & Limitations

- Synthetic sensor data simulates IoT (no live PLC connection)
- ML models trained on synthetic data; production would use plant historical data
- Gemini API optional; Ollama/rule-based fallback available
- PDF report generation via structured JSON (ReportLab available for extension)

## Tech Stack

- Frontend: Next.js 15, TypeScript, Tailwind, Recharts
- Backend: FastAPI, SQLAlchemy async, PostgreSQL
- AI: LangGraph, LangChain, Gemini
- ML: scikit-learn, XGBoost, Isolation Forest
- Vector DB: Qdrant
- Cache: Redis (configured, optional use)
