
from getpass import getpass

from database import SessionLocal
from models import User, UserRole
from auth import hash_password


def create_admin():
    db = SessionLocal()

    try:
        email = input("Nhập email Admin: ").strip().lower()

        existing_user = db.query(User).filter(
            User.email == email
        ).first()

        if existing_user:
            print("Email đã tồn tại!")

            if existing_user.role == UserRole.admin:
                print("Tài khoản này đã có quyền Admin.")
                return

            confirm = input(
                "Bạn có muốn nâng cấp tài khoản này lên Admin? (y/n): "
            ).strip().lower()

            if confirm != "y":
                print("Đã hủy.")
                return

            existing_user.role = UserRole.admin
            db.commit()
            print("Đã nâng cấp tài khoản thành Admin!")
            return

        full_name = input("Nhập họ tên Admin: ").strip()
        password = getpass("Nhập mật khẩu Admin: ")

        if len(password) < 8:
            print("Mật khẩu phải có ít nhất 8 ký tự.")
            return

        new_admin = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.admin
        )

        db.add(new_admin)
        db.commit()

        print("Tạo tài khoản Admin thành công!")

    except Exception as e:
        db.rollback()
        print("Lỗi:", e)

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
