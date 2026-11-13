
from database import SessionLocal
from services.retrieval_service import search_similar_chunks


db = SessionLocal()

try:
    question = "Trường Cao đẳng Kỹ thuật Cao Thắng thành lập ngày tháng năm nào?"

    results = search_similar_chunks(
        db=db,
        question=question,
        top_k=3
    )

    print("\n===== KẾT QUẢ TÌM KIẾM RAG =====")

    if not results:
        print("Không tìm thấy tài liệu nào.")
    else:
        for index, item in enumerate(results, start=1):
            print(f"\n--- KẾT QUẢ {index} ---")
            print("Tài liệu:", item["filename"])
            print("Chunk:", item["chunk_index"])
            print("Similarity:", round(item["score"], 4))
            print("Nội dung:", item["content"])

except Exception as e:
    print("LỖI:", repr(e))

finally:
    db.close()
