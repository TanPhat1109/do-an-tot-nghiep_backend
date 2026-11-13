
from database import SessionLocal
from services.document_service import ingest_document

db = SessionLocal()

try:
    file_path = r"D:\DATN\Back_end\test.txt"

    result = ingest_document(
        db=db,
        file_path=file_path
    )

    print("\n===== KẾT QUẢ NẠP TÀI LIỆU =====")
    print("Document ID:", result["document_id"])
    print("Tên file:", result["filename"])
    print("Số chunks:", result["total_chunks"])
    print("Trạng thái:", result["status"])

except Exception as e:
    db.rollback()
    print("Lỗi:", e)

finally:
    db.close()
