from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import auth
import models
from database import get_db


router = APIRouter(
    prefix="/api/conversations",
    tags=["Quản lý hội thoại"]
)


# ==============================
# SCHEMAS
# ==============================

class ConversationCreate(BaseModel):
    title: str = Field(
        default="Cuộc trò chuyện mới",
        min_length=1,
        max_length=255
    )


class ConversationUpdate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255
    )


# ==============================
# HELPER
# ==============================

def get_user_conversation(
    conversation_id: int,
    current_user: models.User,
    db: Session
):
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id
        )
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy cuộc trò chuyện."
        )

    return conversation


# ==============================
# 1. LẤY DANH SÁCH HỘI THOẠI
# ==============================

@router.get("/")
def get_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    conversations = (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == current_user.id)
        .order_by(models.Conversation.updated_at.desc())
        .all()
    )

    return [
        {
            "id": item.id,
            "title": item.title,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "message_count": len(item.messages)
        }
        for item in conversations
    ]


# ==============================
# 2. TẠO HỘI THOẠI MỚI
# ==============================

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    conversation = models.Conversation(
        user_id=current_user.id,
        title=request.title.strip() or "Cuộc trò chuyện mới"
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return {
        "success": True,
        "message": "Tạo cuộc trò chuyện thành công.",
        "conversation_id": conversation.id,
        "title": conversation.title
    }


# ==============================
# 3. XEM NỘI DUNG HỘI THOẠI
# ==============================

@router.get("/{conversation_id}")
def get_conversation_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    conversation = get_user_conversation(
        conversation_id,
        current_user,
        db
    )

    messages = (
        db.query(models.Message)
        .filter(
            models.Message.conversation_id == conversation.id
        )
        .order_by(models.Message.id.asc())
        .all()
    )

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [
            {
                "id": message.id,
                "sender_type": (
                    message.sender_type.value
                    if hasattr(message.sender_type, "value")
                    else message.sender_type
                ),
                "content": message.content,
                "created_at": message.created_at
            }
            for message in messages
        ]
    }


# ==============================
# 4. ĐỔI TÊN HỘI THOẠI
# ==============================

@router.put("/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    request: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    conversation = get_user_conversation(
        conversation_id,
        current_user,
        db
    )

    title = request.title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Tên cuộc trò chuyện không được để trống."
        )

    conversation.title = title
    conversation.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conversation)

    return {
        "success": True,
        "message": "Đổi tên cuộc trò chuyện thành công.",
        "conversation_id": conversation.id,
        "title": conversation.title
    }


# ==============================
# 5. XÓA HỘI THOẠI
# ==============================

@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    conversation = get_user_conversation(
        conversation_id,
        current_user,
        db
    )

    db.delete(conversation)
    db.commit()

    return {
        "success": True,
        "message": "Xóa cuộc trò chuyện thành công."
    }