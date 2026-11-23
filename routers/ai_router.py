
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import traceback

import auth
import models

from database import get_db
from services.ai_service import ask_ai


router = APIRouter(
    prefix="/api/ai",
    tags=["AI Chatbot"]
)


# ==============================
# REQUEST SCHEMA
# ==============================

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


# ==============================
# RESPONSE SCHEMA
# ==============================

class SourceResponse(BaseModel):
    document_id: int
    filename: str
    chunk_id: int
    chunk_index: int
    similarity: float
    content: str


class ChatResponse(BaseModel):
    success: bool
    conversation_id: int
    question: str
    answer: str
    sources: list[SourceResponse] = Field(default_factory=list)


# ==============================
# TEST AI API
# ==============================

@router.post("/test")
def test_ai(
    question: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        answer, sources = ask_ai(
            question=question,
            db=db
        )

        return {
            "success": True,
            "answer": answer,
            "sources": sources
        }

    except Exception:
        print("\n===== AI TEST ERROR =====")
        traceback.print_exc()

        raise HTTPException(
            status_code=502,
            detail="Không thể kết nối dịch vụ AI."
        )


# CHAT WITH AI + RAG

@router.post("/chat", response_model=ChatResponse)
def chat_with_ai(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):

    try:
        # 1. Kiểm tra cuộc trò chuyện

        conversation = None

        if request.conversation_id is not None:
            conversation = (
                db.query(models.Conversation)
                .filter(
                    models.Conversation.id == request.conversation_id,
                    models.Conversation.user_id == current_user.id
                )
                .first()
            )

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Không tìm thấy cuộc trò chuyện."
                )

        # 2. Lấy lịch sử chat

        history = []

        if conversation:
            messages = (
                db.query(models.Message)
                .filter(
                    models.Message.conversation_id == conversation.id
                )
                .order_by(models.Message.id.desc())
                .limit(10)
                .all()
            )

            messages.reverse()

            history = [
                {
                    "role": (
                        "user"
                        if message.sender_type == models.SenderType.user
                        else "assistant"
                    ),
                    "content": message.content
                }
                for message in messages
            ]

        # 3. Gọi AI + RAG

        answer, sources = ask_ai(
            question=request.question,
            history=history,
            db=db
        )

        # 4. Tạo cuộc trò chuyện mới

        if conversation is None:
            conversation = models.Conversation(
                user_id=current_user.id,
                title=request.question[:255]
            )

            db.add(conversation)
            db.flush()

        # 5. Lưu câu hỏi

        user_message = models.Message(
            conversation_id=conversation.id,
            sender_type=models.SenderType.user,
            content=request.question
        )

        # 6. Lưu câu trả lời

        bot_message = models.Message(
            conversation_id=conversation.id,
            sender_type=models.SenderType.bot,
            content=answer
        )

        db.add(user_message)
        db.add(bot_message)

        db.commit()

        return ChatResponse(
            success=True,
            conversation_id=conversation.id,
            question=request.question,
            answer=answer,
            sources=sources
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        print("\n===== CHATBOT ERROR =====")
        traceback.print_exc()

        raise HTTPException(
            status_code=502,
            detail="Chatbot đang gặp sự cố. Vui lòng thử lại."
        )
