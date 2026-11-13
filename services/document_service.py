
from pathlib import Path

from pypdf import PdfReader
from docx import Document as DocxDocument
from sqlalchemy.orm import Session

from models import Document, DocumentChunk
from services.embedding_service import embed_passage


# =================================
# 1. ĐỌC NỘI DUNG TÀI LIỆU
# =================================

def extract_text(file_path: str) -> str:
    path = Path(file_path)
    extension = path.suffix.lower()

    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")

    if extension == ".pdf":
        reader = PdfReader(str(path))
        pages = []

        for page in reader.pages:
            content = page.extract_text() or ""
            if content.strip():
                pages.append(content)

        return "\n".join(pages)

    elif extension == ".docx":
        doc = DocxDocument(str(path))

        paragraphs = [
            p.text for p in doc.paragraphs
            if p.text.strip()
        ]

        return "\n".join(paragraphs)

    elif extension == ".txt":
        return path.read_text(encoding="utf-8")

    else:
        raise ValueError("Chỉ hỗ trợ PDF, DOCX và TXT")


# =================================
# 2. CHIA VĂN BẢN THÀNH CHUNKS
# =================================

def split_text(
    text: str,
    chunk_size: int = 2000,
    overlap: int = 300
) -> list[str]:

    text = " ".join(text.split())

    if not text:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap phải nhỏ hơn chunk_size")

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


# =================================
# 3. TẠO EMBEDDING VÀ LƯU MYSQL
# =================================

def ingest_document(
    db: Session,
    file_path: str,
    uploaded_by_user_id: int | None = None
):
    path = Path(file_path).resolve()

    # Đọc nội dung
    text = extract_text(str(path))

    if not text.strip():
        raise ValueError("Tài liệu không có nội dung văn bản")

    # Chia chunks
    chunks = split_text(text)

    if not chunks:
        raise ValueError("Không tạo được chunks từ tài liệu")

    try:
        # Tạo bản ghi tài liệu
        document = Document(
            filename=path.name,
            file_path=str(path),
            file_type=path.suffix.lower().replace(".", ""),
            uploaded_by_user_id=uploaded_by_user_id,
            status="pending"
        )

        db.add(document)
        db.flush()

        # Tạo embedding và lưu từng chunk
        for index, chunk in enumerate(chunks):

            print(
                f"Đang tạo embedding: "
                f"{index + 1}/{len(chunks)}"
            )

            vector = embed_passage(chunk)

            if len(vector) != 1024:
                raise ValueError(
                    f"Embedding không đúng 1024 chiều: {len(vector)}"
                )

            document_chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                embedding=vector
            )

            db.add(document_chunk)

        document.status = "processed"

        db.commit()
        db.refresh(document)

        return {
            "document_id": document.id,
            "filename": document.filename,
            "total_chunks": len(chunks),
            "status": document.status
        }

    except Exception:
        db.rollback()
        raise
