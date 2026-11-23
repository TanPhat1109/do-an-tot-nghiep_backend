
import math
import time

from sqlalchemy.orm import Session

from models import Document, DocumentChunk
from services.embedding_service import embed_query


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float]
) -> float:
    """Tính Cosine Similarity giữa hai vector."""

    if len(vector_a) != len(vector_b):
        raise ValueError("Hai vector không cùng số chiều")

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))

    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)



def search_similar_chunks(
    db: Session,
    question: str,
    top_k: int = 3
) -> list[dict]:

    if not question or not question.strip():
        raise ValueError("Câu hỏi không được để trống")

    if top_k < 1:
        raise ValueError("top_k phải lớn hơn 0")

    # 1. Tạo embedding câu hỏi
    start = time.time()

    query_vector = embed_query(question)

    print(
        f"[RAG] Thời gian Jina Embedding: "
        f"{time.time() - start:.2f}s"
    )

    if len(query_vector) != 1024:
        raise ValueError("Vector không đúng 1024 chiều")

    # 2. Lấy dữ liệu từ MySQL
    start = time.time()

    rows = (
        db.query(DocumentChunk, Document)
        .join(
            Document,
            DocumentChunk.document_id == Document.id
        )
        .filter(Document.status == "processed")
        .all()
    )

    print(
        f"[RAG] Thời gian truy vấn MySQL: "
        f"{time.time() - start:.2f}s"
    )

    # 3. Tính cosine similarity
    start = time.time()

    results = []

    for chunk, document in rows:

        if not chunk.embedding:
            continue

        score = cosine_similarity(
            query_vector,
            chunk.embedding
        )

        results.append({
            "chunk_id": chunk.id,
            "document_id": document.id,
            "filename": document.filename,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "score": score
        })

    
    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # HIỂN THỊ KẾT QUẢ TÌM KIẾM ĐỂ KIỂM TRA
    print(f"\n[RAG] Tổng số chunks: {len(rows)}")
    print("[RAG] Top 5 kết quả:")

    for item in results[:5]:
        print(
            f"Document ID: {item['document_id']} | "
            f"Chunk: {item['chunk_index']} | "
            f"Similarity: {item['score']:.4f}"
        )
        print(f"Nội dung: {item['content'][:200]}")
        print("-" * 50)

    # Lọc theo ngưỡng similarity
    SIMILARITY_THRESHOLD = 0.65

    print(f"[RAG] Ngưỡng similarity: {SIMILARITY_THRESHOLD}")

    filtered_results = [
        item for item in results
        if item["score"] >= SIMILARITY_THRESHOLD
    ]

    print(f"[RAG] Số chunks đạt ngưỡng: {len(filtered_results)}")

    return filtered_results[:top_k]


    # Lọc theo ngưỡng similarity
    SIMILARITY_THRESHOLD = 0.65

    filtered_results = [
    item for item in results
    if item["score"] >= SIMILARITY_THRESHOLD
    ]

    return filtered_results[:top_k]

