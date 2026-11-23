
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class SenderType(str, enum.Enum):
    user = "user"
    bot = "bot"


# =========================
# USER
# =========================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    role = Column(
        SAEnum(UserRole, values_callable=_enum_values, name="user_role"),
        nullable=False,
        default=UserRole.user,
    )

    created_at = Column(DateTime, default=utcnow, nullable=False)

    conversations = relationship(
        "Conversation",
        back_populates="owner",
        cascade="all, delete-orphan",
    )


# =========================
# CONVERSATION
# =========================

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(
        String(255),
        default="Cuộc trò chuyện mới",
        nullable=False,
    )

    created_at = Column(DateTime, default=utcnow, nullable=False)

    updated_at = Column(
    DateTime,
    default=utcnow,
    onupdate=utcnow,
    nullable=False
)

    owner = relationship("User", back_populates="conversations")

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


# =========================
# MESSAGE
# =========================

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_type = Column(
        SAEnum(SenderType, values_callable=_enum_values, name="sender_type"),
        nullable=False,
    )

    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )


# =========================
# DOCUMENT - TÀI LIỆU
# =========================


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # Ánh xạ filename trong Python vào cột title trong MySQL
    filename = Column(
        "title",
        String(255),
        nullable=False
    )

    file_path = Column(
        String(255),
        nullable=False
    )

    file_type = Column(
        String(50),
        nullable=True
    )

    # Ánh xạ uploaded_by_user_id vào cột uploaded_by
    uploaded_by_user_id = Column(
        "uploaded_by",
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # MySQL hiện chỉ chấp nhận:
    # pending, processed, error
    status = Column(
        String(30),
        default="pending",
        nullable=False
    )

    created_at = Column(
        DateTime,
        nullable=False
    )

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )



# =========================
# DOCUMENT CHUNK - ĐOẠN VĂN BẢN
# =========================

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunk",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index = Column(Integer, nullable=False)

    content = Column(Text, nullable=False)

    # Vector embedding Jina AI - 1024 chiều
    embedding = Column(JSON, nullable=False)

    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False,
    )

    document = relationship(
        "Document",
        back_populates="chunks",
    )
