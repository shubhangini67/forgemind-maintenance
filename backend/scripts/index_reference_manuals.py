"""Index reference manuals from hackathon data pack into RAG."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import Document
from app.services.rag.knowledge_engine import get_rag_engine, load_text_file


MANUALS = [
    ("manuals/blast_furnace_motor_manual.txt", "Blast Furnace Main Drive Motor Manual", "manual", "blast_furnace_blower"),
    ("manuals/ccm_segment_bearing_sop.txt", "CCM Segment Bearing SOP", "sop", "caster_drive"),
]


async def index_manuals() -> None:
    docs_dir = Path(__file__).resolve().parents[2] / "data" / "documents"
    rag = get_rag_engine()
    async with AsyncSessionLocal() as db:
        for rel, title, dtype, etype in MANUALS:
            path = docs_dir / rel
            if not path.exists():
                print(f"Skip missing: {path}")
                continue
            exists = await db.scalar(select(Document).where(Document.title == title))
            if exists and exists.indexed:
                print(f"Already indexed: {title}")
                continue
            if not exists:
                doc = Document(title=title, document_type=dtype, equipment_type=etype, file_path=str(path), indexed=False)
                db.add(doc)
                await db.flush()
            else:
                doc = exists
            text = load_text_file(path)
            rag.index_document(doc.id, title, text, dtype, etype)
            doc.indexed = True
            print(f"Indexed: {title} ({len(text)} chars)")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(index_manuals())
