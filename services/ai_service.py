
import requests
import config

from sqlalchemy.orm import Session
from services.retrieval_service import search_similar_chunks


# ==========================================
# SYSTEM PROMPT
# ==========================================

SYSTEM_PROMPT = f"""
Bạn là trợ lý AI tư vấn thông tin cho {config.SCHOOL_NAME}.

QUY TẮC:
1. Trả lời bằng tiếng Việt tự nhiên, dễ hiểu và lịch sự.
2. Ưu tiên tuyệt đối thông tin trong tài liệu tham khảo.
3. Không tự bịa thông tin, số liệu hoặc địa chỉ.
4. Khi tài liệu có câu trả lời, phải trả lời trực tiếp.
5. Không được nói không tìm thấy nếu tài liệu đã chứa thông tin trả lời.
6. Nếu tài liệu không có thông tin, hãy nói:
"Tôi chưa tìm thấy thông tin này trong tài liệu hiện có."
7. Không sử dụng kiến thức bên ngoài để thay thế tài liệu.
8. Không tự nhận mình là cán bộ hoặc nhân viên trường.
"""


# ==========================================
# AI CHAT WITH RAG
# ==========================================

def ask_ai(
    question: str,
    history: list[dict] | None = None,
    db: Session | None = None
) -> tuple[str, list[dict]]:

    # 1. RETRIEVAL

    results = []

    if db is not None:
        results = search_similar_chunks(
            db=db,
            question=question,
            top_k=3
        )
        print("TOTAL RESULTS:", len(results))

# In toàn bộ kết quả trước khi lọc
        for item in results:
         print(
        f"File: {item['filename']} | "
        f"Chunk: {item['chunk_index']} | "
        f"Similarity: {item['score']:.4f}"
    )
        

    # 2. LỌC KẾT QUẢ

    MIN_SIMILARITY = 0.65

    relevant_results = [
        item for item in results
        if item["score"] >= MIN_SIMILARITY
    ]

    print("\n===== RAG DEBUG =====")
    print("Question:", question)

    for item in results:
        print(
            f"Chunk {item['chunk_index']} "
            f"- Similarity: {item['score']:.4f}"
        )

    print("Relevant chunks:", len(relevant_results))

    # 3. TẠO SOURCES

    sources = []

    for item in relevant_results:
        sources.append({
            "document_id": item["document_id"],
            "filename": item["filename"],
            "chunk_id": item["chunk_id"],
            "chunk_index": item["chunk_index"],
            "similarity": round(item["score"], 4),
            "content": item["content"]
        })

    # 4. TẠO CONTEXT

    context_parts = []

    for index, item in enumerate(relevant_results, start=1):
        context_parts.append(
            f"""
Tài liệu {index}: {item['filename']}

Nội dung:
{item['content']}
"""
        )

    context = "\n".join(context_parts)

    # 5. TẠO SYSTEM MESSAGE

    system_content = SYSTEM_PROMPT

    if context:
        system_content += f"""

===== TÀI LIỆU THAM KHẢO =====

{context}

===== KẾT THÚC TÀI LIỆU =====

HƯỚNG DẪN:
- Đọc kỹ toàn bộ tài liệu tham khảo.
- Tìm câu hoặc đoạn chứa thông tin trả lời.
- Trả lời trực tiếp, ngắn gọn và chính xác.
- Nếu hỏi địa chỉ, hãy trích xuất chính xác địa chỉ từ tài liệu.
- Không bỏ qua thông tin chỉ vì câu hỏi dùng cách diễn đạt khác.
"""
    else:
        system_content += """

Không có tài liệu đủ độ tương đồng để trả lời câu hỏi.
Không được suy đoán.
Hãy thông báo chưa tìm thấy thông tin trong tài liệu hiện có.
"""

    # 6. TẠO MESSAGES

    messages = [
        {
            "role": "system",
            "content": system_content
        }
    ]

    if history:
        for item in history:
            role = item["role"]

            if role in ("user", "assistant"):
                messages.append({
                    "role": role,
                    "content": item["content"]
                })

    messages.append({
        "role": "user",
        "content": question
    })

    # 7. OPENROUTER

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "DATN Q&A RAG System"
    }

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1000
    }

    # 8. GỬI REQUEST

    try:
        response = requests.post(
            f"{config.OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=90
        )

        if response.status_code != 200:
            print(
                "OpenRouter Error:",
                response.status_code,
                response.text
            )

            raise RuntimeError(
                "OpenRouter API request failed."
            )

       
        data = response.json()

        print("\n===== OPENROUTER DEBUG =====")
        print("Response:", data)

        choices = data.get("choices", [])

        if not choices:
            raise RuntimeError(
                f"OpenRouter không trả về choices: {data}"
            )

        message = choices[0].get("message") or {}
        content = message.get("content")

        # Xử lý content dạng danh sách
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
                and item.get("type") == "text"
            )

        if not isinstance(content, str) or not content.strip():
            print("EMPTY CONTENT:", content)
            print("FINISH REASON:", choices[0].get("finish_reason"))
            print("MESSAGE:", message)

            raise RuntimeError(
                "OpenRouter trả về nội dung rỗng."
            )

        answer = content.strip()

        print("AI ANSWER:", answer)
        print("============================")

        return answer, sources

    except requests.RequestException as error:
        print("OpenRouter Connection Error:", repr(error))
        raise RuntimeError("Không thể kết nối OpenRouter.")
