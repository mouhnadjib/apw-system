"""تعبئة قاعدة العرض التجريبي ببيانات وهمية (لا علاقة لها بأي بيانات حقيقية).

تُشغَّل عبر run_demo.sh بعد ضبط متغيرات البيئة (قاعدة SQLite ومفاتيح تجريبية).
  python demo/seed.py            # تعبئة إن كانت القاعدة فارغة
  python demo/seed.py --reset    # حذف كل شيء وإعادة التعبئة
"""
import shutil
import struct
import sys
import zlib
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.main import init_db
from app.models import (
    Committee, Deputy, Invitation, Mandate, NotifKind, Notification, NotificationRecipient,
    Question, QuestionEvent, QuestionVersion, QStatus, StaffRole, StaffUser, TargetType,
)
from app.security import hash_password, new_invite_code, normalize_code, save_encrypted, token_digest, utcnow
from app.services import set_setting

ADMIN = ("admin", "Demo-Admin-2026!")
OPERATOR = ("cabinet", "Demo-Cabinet-2026!")

NAMES = [
    ("عبد الرحمان بن يوسف", "رئيس المجلس", [0]),
    ("فاطمة الزهراء بلقاسم", "نائب الرئيس", [1]),
    ("محمد الأمين حدّاد", "رئيس لجنة", [0]),
    ("خديجة مرابط", "نائب", [1]),
    ("يوسف بوزيدي", "نائب", [2]),
    ("سمية عمراني", "نائب", [2]),
    ("إبراهيم قاسمي", "نائب", [0, 2]),
    ("نورة بن عيسى", "نائب", [1]),
    ("الطاهر زروقي", "نائب", [2]),
    ("أمينة شريف", "نائب", [0]),
]
COMMITTEES = ["لجنة الصحة والنظافة", "لجنة التهيئة والتعمير", "لجنة المالية والاقتصاد"]
COLORS = [(31, 78, 121), (46, 125, 50), (141, 110, 99), (123, 31, 162), (0, 105, 92),
          (191, 54, 12), (69, 90, 100), (2, 119, 189), (136, 14, 79), (85, 139, 47)]


def solid_png(rgb, size=160) -> bytes:
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    row = b"\x00" + bytes(rgb) * size
    raw = row * size
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def demo_pdf() -> bytes:
    """PDF صالح من صفحة واحدة (نص لاتيني بسيط: 'Demo reply')."""
    stream = b"BT /F1 28 Tf 72 700 Td (DEMO - Executive reply, scanned copy) Tj ET\n" \
             b"BT /F1 16 Tf 72 660 Td (This is a sample document for demonstration only.) Tj ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def main(reset: bool) -> None:
    if reset:
        data = get_settings().data_dir
        if data.exists():
            shutil.rmtree(data)
        from app.db import Base, engine
        from app import models  # noqa: F401
        Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(StaffUser)):
            print("القاعدة معبّأة مسبقاً (استعمل --reset لإعادة التعبئة).")
            return
        now = utcnow()
        admin = StaffUser(username=ADMIN[0], full_name="مدير النظام (تجريبي)",
                          password_hash=hash_password(ADMIN[1]), role=StaffRole.admin)
        oper = StaffUser(username=OPERATOR[0], full_name="موظف الديوان (تجريبي)",
                         password_hash=hash_password(OPERATOR[1]), role=StaffRole.operator)
        db.add_all([admin, oper])
        mandate = Mandate(label="الدورة التجريبية 2026-2031", start_year=2026, end_year=2031, active=True)
        db.add(mandate)
        db.flush()
        set_setting(db, "wilaya_name", "ولاية تجريبية")
        comms = [Committee(mandate_id=mandate.id, name=n) for n in COMMITTEES]
        db.add_all(comms)
        db.flush()

        deputies, codes = [], []
        for i, (name, title, cidx) in enumerate(NAMES):
            d = Deputy(mandate_id=mandate.id, full_name=name, title=title, phone=f"055000{i + 1:04d}",
                       committees=[comms[c] for c in cidx], photo_path=save_encrypted(solid_png(COLORS[i]), "photos"))
            db.add(d)
            db.flush()
            code = new_invite_code()
            db.add(Invitation(deputy_id=d.id, code_digest=token_digest(normalize_code(code)),
                              expires_at=now + timedelta(days=365), created_by=admin.id))
            deputies.append(d)
            codes.append((d.phone, code, name))

        def notif(kind, title, body, target, recips, ago_h, meeting=None):
            db.add(Notification(kind=kind, title=title, body=body, target_type=target, created_by=oper.id,
                                meeting_at=meeting, created_at=now - timedelta(hours=ago_h),
                                recipients=[NotificationRecipient(deputy_id=d.id) for d in recips]))
        notif(NotifKind.meeting, "دعوة لحضور الدورة العادية",
              "يشرّفنا دعوتكم لحضور أشغال الدورة العادية للمجلس.\nالمكان: قاعة المداولات بمقر المجلس.",
              TargetType.all, deputies, 30, meeting=now + timedelta(days=3, hours=2))
        notif(NotifKind.targeted, "اجتماع لجنة الصحة والنظافة",
              "تُعقد اللجنة اجتماعاً لدراسة وضعية المؤسسات الاستشفائية بالولاية.",
              TargetType.committees, [deputies[0], deputies[2], deputies[6], deputies[9]], 8,
              meeting=now + timedelta(days=1, hours=1))
        notif(NotifKind.info, "معلومة مهمة", "يرجى تحيين بياناتكم لدى ديوان رئيس المجلس قبل نهاية الأسبوع.",
              TargetType.all, deputies, 2)

        d0 = deputies[0]

        def question(subject, text, steps, ago_h):
            q = Question(deputy_id=d0.id, subject=subject, text=text, status=QStatus.submitted,
                         created_at=now - timedelta(hours=ago_h), updated_at=now - timedelta(hours=ago_h))
            q.versions.append(QuestionVersion(subject=subject, text=text))
            q.events.append(QuestionEvent(status=QStatus.submitted, actor_type="deputy", actor_id=d0.id))
            db.add(q)
            for status, note in steps:
                q.status = status
                q.return_note = note if status == QStatus.returned else None
                q.events.append(QuestionEvent(status=status, note=note, actor_type="staff", actor_id=oper.id))
            return q
        question("وضعية الطريق الولائي رقم 1", "نرجو إفادتنا بالتدابير المتخذة لإعادة تهيئة الطريق.", [], 70)
        question("تزويد القرى النائية بالماء الشروب", "ما هو برنامج ربط القرى بالشبكة؟",
                 [(QStatus.under_review, None)], 50)
        question("مشروع قاعة العلاج", "متى ينطلق إنجاز المشروع؟",
                 [(QStatus.returned, "يرجى تحديد البلدية المعنية في صياغة السؤال.")], 40)
        question("النقل المدرسي", "ما هي الإجراءات لتدعيم النقل المدرسي بالمناطق الريفية؟",
                 [(QStatus.confirmed, None)], 30)
        question("الإنارة العمومية", "نطلب توضيحاً حول برنامج صيانة الإنارة العمومية.",
                 [(QStatus.confirmed, None), (QStatus.referred, None)], 20)
        q6 = question("برنامج السكن الريفي", "ما مآل حصة السكن الريفي للسنة الجارية؟",
                      [(QStatus.confirmed, None), (QStatus.referred, None), (QStatus.answered, None)], 10)
        q6.reply_path = save_encrypted(demo_pdf(), "replies")
        q6.reply_mime = "application/pdf"
        q6.reply_filename = "reply-demo.pdf"
        db.commit()

    lines = [
        "=== بيانات العرض التجريبي (وهمية) ===",
        f"لوحة الديوان: admin / {ADMIN[1]}   أو   cabinet / {OPERATOR[1]}",
        "",
        "رموز تفعيل النواب (الهاتف  |  الرمز  |  الاسم):",
    ] + [f"{p}  |  {c}  |  {n}" for p, c, n in codes]
    text = "\n".join(lines)
    Path(__file__).with_name("DEMO-CODES.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main("--reset" in sys.argv)
