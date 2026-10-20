"""أوامر الإدارة من الطرفية على الخادم.

  python -m app.cli init-db
  python -m app.cli create-admin <username> "<الاسم الكامل>"
  python -m app.cli gen-keys
"""
import base64
import getpass
import os
import sys

from sqlalchemy import select


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "gen-keys":
        for name in ("APW_FILE_KEY", "APW_FIELD_KEY"):
            print(f"{name}={base64.b64encode(os.urandom(32)).decode()}")
        print(f"APW_JWT_SECRET={base64.urlsafe_b64encode(os.urandom(48)).decode()}")
        return 0

    from .db import SessionLocal
    from .main import init_db
    from .models import StaffRole, StaffUser
    from .security import hash_password, validate_password_strength

    if cmd == "init-db":
        init_db()
        print("تم إنشاء الجداول")
        return 0
    if cmd == "create-admin" and len(argv) >= 4:
        init_db()
        pw = getpass.getpass("كلمة المرور (12 حرفاً على الأقل): ")
        if pw != getpass.getpass("أعد الإدخال: "):
            print("كلمتا المرور غير متطابقتين")
            return 1
        try:
            validate_password_strength(pw)
        except ValueError as e:
            print(e)
            return 1
        with SessionLocal() as db:
            if db.scalar(select(StaffUser).where(StaffUser.username == argv[2])):
                print("اسم المستخدم مستعمل")
                return 1
            db.add(StaffUser(username=argv[2], full_name=argv[3], password_hash=hash_password(pw), role=StaffRole.admin))
            db.commit()
        print("تم إنشاء حساب الأدمن")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
