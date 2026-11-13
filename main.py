from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from routers.ai_router import router as ai_router
from services.ai_service import ask_ai
from routers.document_router import router as document_router


import auth
import config
import models
import schemas
from database import Base, engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tạo bảng nếu chưa có (về sau nên chuyển sang Alembic)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Q&A RAG System API",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True}
)

app.include_router(ai_router)
app.include_router(document_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/auth/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký!")

    new_user = models.User(
        full_name=user_data.full_name,
        email=user_data.email,
        password_hash=auth.hash_password(user_data.password),
        role=models.UserRole.user,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:  # hai request đăng ký cùng email cùng lúc
        db.rollback()
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký!")
    db.refresh(new_user)
    return new_user


@app.post("/auth/login", response_model=schemas.Token)
def login(login_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == login_data.email).first()

    if user is None:
        auth.fake_verify()
        valid = False
    else:
        valid = auth.verify_password(login_data.password, user.password_hash)

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác!",
        )

    # Tự nâng cấp hash cũ (SHA-256) lên argon2 sau khi đăng nhập thành công
    if auth.needs_rehash(user.password_hash):
        user.password_hash = auth.hash_password(login_data.password)
        db.commit()

    access_token = auth.create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schemas.UserResponse)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.get("/")
def home():
    return {"status": "success", "message": "API Q&A RAG đang chạy ngon lành!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)