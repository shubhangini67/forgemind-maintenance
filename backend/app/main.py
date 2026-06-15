from contextlib import asynccontextmanager

import asyncio

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import auth, documents, equipment, operations, wizard
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.bootstrap import bootstrap_application
from app.db.init_db import close_db, init_db
from app.db.session import get_db

settings = get_settings()
setup_logging(settings.debug)
logger = get_logger(__name__)


async def _background_bootstrap() -> None:
    """Heavy seed/train/index work — runs after the port is open so the
    platform (Render) detects a live port immediately instead of timing out."""
    try:
        await bootstrap_application()
        logger.info("bootstrap_complete")
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("bootstrap_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_application")
    await init_db()
    # Bind the HTTP port right away; defer the slow ML training + RAG indexing
    # to a background task so deploys go live fast and never hit the port-scan
    # timeout. Data/endpoints fill in within a minute or two of going live.
    bootstrap_task = asyncio.create_task(_background_bootstrap())
    yield
    bootstrap_task.cancel()
    await close_db()
    logger.info("shutdown_complete")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app|http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(equipment.router, prefix=settings.api_prefix)
app.include_router(wizard.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(operations.router, prefix=settings.api_prefix)


@app.get("/health")
async def health(test_llm: bool = False):
    from app.services.ml.predictive_engine import get_pm_engine
    from app.services.rag.knowledge_engine import get_rag_engine

    pm = get_pm_engine()
    try:
        rag_mode = get_rag_engine().mode
    except Exception:
        rag_mode = "unknown"

    groq_status: dict = {
        "configured": bool(settings.groq_api_key),
        "model": settings.groq_model,
        "provider_note": "Uses Groq API (llama), not xAI Grok",
    }
    if test_llm and settings.groq_api_key:
        from app.services.llm_service import llm_service

        try:
            groq_status.update(await asyncio.wait_for(llm_service.ping_groq(), timeout=8.0))
        except asyncio.TimeoutError:
            groq_status.update({"ok": False, "error": "Groq API timeout (>8s)"})

    return {
        "status": "healthy",
        "service": settings.app_name,
        "deploy": settings.deploy_summary,
        "groq": groq_status,
        "vector_store_active": rag_mode,
        "ml_models": pm.train_metrics or {"status": "loaded"},
    }


@app.get(f"{settings.api_prefix}/public/plant-status")
async def public_plant_status(db: AsyncSession = Depends(get_db)):
    """Aggregate plant metrics for the login page — no authentication required."""
    from app.services.equipment_service import get_dashboard_summary
    from app.services.ml.predictive_engine import get_pm_engine

    dash = await get_dashboard_summary(db)
    pm = get_pm_engine()
    models_online = ["XGBoost", "Isolation Forest", "LangGraph"]
    if not pm.train_metrics:
        models_online = ["LangGraph"]

    critical_assets = sum(
        1 for item in (dash.high_risk_equipment or []) if item.get("risk_level") == "critical"
    )

    return {
        "plant_assets": dash.total_equipment,
        "active_alerts": dash.open_alerts,
        "critical_assets": critical_assets or dash.critical_alerts,
        "average_health": dash.avg_health_score,
        "models_online": models_online,
        "live": True,
    }
