from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Document, Report, User
from app.schemas import PdfExportRequest, ReportRequest, ReportResponse
from app.services.rag.knowledge_engine import get_rag_engine, load_text_file
from app.services.reports.pdf_content_builder import build_pdf_content, normalize_pdf_content
from app.services.reports.pdf_service import render_report_pdf
from app.services.reports.report_service import generate_report

router = APIRouter(tags=["documents", "reports"])

DOCS_DIR = Path(__file__).resolve().parents[4] / "data" / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/documents")
async def list_documents(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Document).order_by(Document.id.desc()))
    return [
        {
            "id": d.id,
            "title": d.title,
            "document_type": d.document_type,
            "equipment_type": d.equipment_type,
            "indexed": d.indexed,
        }
        for d in result.scalars().all()
    ]


@router.get("/documents/{document_id}/content")
async def get_document_content(document_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(404, "File not found on disk")
    text = load_text_file(path)
    rag = get_rag_engine()
    chunks = rag.hybrid_search(doc.title, limit=8, equipment_type=doc.equipment_type) if doc.indexed else []
    return {
        "id": doc.id,
        "title": doc.title,
        "document_type": doc.document_type,
        "content": text[:12000],
        "chunks": chunks,
    }


@router.get("/reports/{report_id}")
async def get_report(report_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return ReportResponse(
        id=report.id,
        report_type=report.report_type,
        title=report.title,
        content=report.content,
        created_at=report.created_at,
    )


@router.get("/reports/{report_id}/pdf")
async def download_report_pdf(report_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    content = normalize_pdf_content(
        report.content or {},
        report_type=report.report_type,
        title=report.title,
    )
    pdf_bytes = render_report_pdf(report.title, content)
    filename = f"report_{report_id}_{report.report_type}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reports/pdf/export")
async def export_report_pdf(
    request: PdfExportRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        content = await build_pdf_content(
            db,
            report_type=request.report_type,
            equipment_id=request.equipment_id,
            alert_id=request.alert_id,
            payload=request.payload,
            title=request.title,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    title = content["report_meta"]["title"]
    pdf_bytes = render_report_pdf(title, content)
    safe_type = request.report_type.replace("_", "-")
    code = (content.get("asset") or {}).get("code", "plant")
    filename = f"tata_{safe_type}_{code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports")
async def list_reports(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Report).order_by(Report.created_at.desc()).limit(20))
    return [
        {
            "id": r.id,
            "report_type": r.report_type,
            "title": r.title,
            "equipment_id": r.equipment_id,
            "created_at": r.created_at,
        }
        for r in result.scalars().all()
    ]


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    document_type: str = "manual",
    equipment_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    dest = DOCS_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)

    doc = Document(
        title=file.filename,
        document_type=document_type,
        equipment_type=equipment_type,
        file_path=str(dest),
        indexed=False,
    )
    db.add(doc)
    await db.flush()

    text = load_text_file(dest)
    rag = get_rag_engine()
    chunks = rag.index_document(doc.id, doc.title, text, document_type, equipment_type)
    doc.indexed = True
    await db.flush()
    return {"document_id": doc.id, "chunks_indexed": chunks}


@router.post("/documents/index-all")
async def index_all_documents(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Document).where(Document.indexed == False))  # noqa: E712
    docs = result.scalars().all()
    rag = get_rag_engine()
    indexed = 0
    for doc in docs:
        text = load_text_file(Path(doc.file_path))
        rag.index_document(doc.id, doc.title, text, doc.document_type, doc.equipment_type)
        doc.indexed = True
        indexed += 1
    await db.flush()
    return {"indexed": indexed}


@router.post("/reports/generate", response_model=ReportResponse)
async def create_report(
    request: ReportRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        report = await generate_report(db, request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Report generation failed: {exc}") from exc
    return ReportResponse(
        id=report.id,
        report_type=report.report_type,
        title=report.title,
        content=report.content,
        created_at=report.created_at,
    )
