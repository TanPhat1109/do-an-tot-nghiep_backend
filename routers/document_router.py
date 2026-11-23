import auth
import models
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from services.document_service import ingest_document

from fastapi import status
from sqlalchemy.orm import joinedload 

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

# Thư mục lưu file upload
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Chỉ cho phép PDF, DOCX, TXT
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Giới hạn dung lượng: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    original_filename = file.filename or ""

    # 1. Kiểm tra tên và định dạng
    if not original_filename:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng chọn file"
        )

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Chỉ hỗ trợ file PDF, DOCX và TXT"
        )

    # 2. Đọc file và kiểm tra dung lượng
    content = file.file.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="File không có nội dung"
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File vượt quá dung lượng tối đa 10 MB"
        )

    # 3. Tạo tên file duy nhất, tránh ghi đè
    safe_filename = Path(original_filename).name
    stored_filename = f"{uuid4().hex}_{safe_filename}"
    saved_path = UPLOAD_DIR / stored_filename

    try:
        # 4. Lưu file
        saved_path.write_bytes(content)

        # 5. Trích xuất, chia chunks và tạo embedding
        result = ingest_document(
          db=db,
          file_path=str(saved_path),
          uploaded_by_user_id=current_user.id
)

        return {
            "success": True,
            "message": "Upload và xử lý tài liệu thành công",
            "original_filename": original_filename,
            "document_id": result["document_id"],
            "filename": result["filename"],
            "total_chunks": result["total_chunks"],
            "status": result["status"]
        }

    except Exception as e:
        db.rollback()

        # Xóa file nếu xử lý thất bại
        if saved_path.exists():
            saved_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"Không thể xử lý tài liệu: {str(e)}"
        )

# =========================
# LẤY DANH SÁCH TÀI LIỆU
# =========================

@router.get("/")
def get_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    documents = (
        db.query(models.Document)
        .order_by(models.Document.created_at.desc())
        .all()
    )

    return {
        "success": True,
        "total": len(documents),
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "status": doc.status,
                "created_at": doc.created_at.isoformat()
                if doc.created_at else None,
                "total_chunks": len(doc.chunks),
            }
            for doc in documents
        ]
    }


# =========================
# XÓA TÀI LIỆU
# =========================

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy tài liệu"
        )

    try:
        file_path = Path(document.file_path)

        # Xóa tài liệu trong database.
        # Cascade sẽ xóa các document_chunks liên quan.
        db.delete(document)
        db.commit()

        # Xóa file vật lý sau khi database đã xóa thành công.
        if file_path.exists():
            file_path.unlink()

        return {
            "success": True,
            "message": "Đã xóa tài liệu thành công",
            "document_id": document_id
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Không thể xóa tài liệu: {str(e)}"
        )
