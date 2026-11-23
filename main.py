from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from routers.ai_router import router as ai_router
from services.ai_service import ask_ai
from routers.document_router import router as document_router
from routers.conversation_router import router as conversation_router

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
app.include_router(conversation_router)

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

@app.get(
    "/admin/users",
    response_model=list[schemas.AdminUserResponse],
)
def get_all_users(
    admin: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    users = (
        db.query(models.User)
        .order_by(models.User.id.desc())
        .all()
    )
    return users


@app.put("/admin/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role_data: schemas.UserRoleUpdate,
    admin: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(
        models.User.id == user_id
    ).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy tài khoản",
        )

    new_role = models.UserRole(role_data.role)

    # Không cho Admin tự hạ quyền
    if user.id == admin.id and new_role != models.UserRole.admin:
        raise HTTPException(
            status_code=400,
            detail="Không thể tự hạ quyền Admin của chính mình",
        )

    # Không cho hạ quyền Admin cuối cùng
    if (
        user.role == models.UserRole.admin
        and new_role == models.UserRole.user
    ):
        admin_count = (
            db.query(models.User)
            .filter(models.User.role == models.UserRole.admin)
            .count()
        )

        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Hệ thống phải có ít nhất một Admin",
            )

    user.role = new_role
    db.commit()
    db.refresh(user)

    return {
        "message": "Cập nhật quyền tài khoản thành công",
        "user": schemas.AdminUserResponse.model_validate(user),
    }
@app.get("/auth/me", response_model=schemas.UserResponse)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@app.put("/auth/profile", response_model=schemas.UserResponse)
def update_profile(
    profile_data: schemas.ProfileUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    current_user.full_name = profile_data.full_name.strip()

    if not current_user.full_name:
        raise HTTPException(
            status_code=400,
            detail="Họ tên không được để trống!",
        )

    db.commit()
    db.refresh(current_user)

    return current_user


@app.put("/auth/change-password")
def change_password(
    password_data: schemas.ChangePasswordRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if not auth.verify_password(
        password_data.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail="Mật khẩu hiện tại không chính xác!",
        )

    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=400,
            detail="Mật khẩu mới phải khác mật khẩu hiện tại!",
        )

    current_user.password_hash = auth.hash_password(
        password_data.new_password
    )

    db.commit()

    return {"message": "Đổi mật khẩu thành công!"}

@app.get("/")
def home():
    return {"status": "success", "message": "API Q&A RAG đang chạy ngon lành!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)