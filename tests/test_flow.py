import sqlite3

from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from .conftest import login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"scan-of-wali-reply-\xd8\xa7\xd9\x84\xd8\xb1\xd8\xaf" * 50


def test_full_question_flow(client, admin_h, world):
    op, a, b = world["op"], world["a"], world["b"]

    # صورة النائب
    r = client.put(f"/admin/deputies/{a['id']}/photo", headers=admin_h, files={"file": ("p.png", PNG, "image/png")})
    assert r.status_code == 204
    r = client.get("/me/photo", headers=a["h"])
    assert r.status_code == 200 and r.content == PNG
    # لا يمكن للنائب رؤية صورة غيره ولا دليل النواب
    assert client.get(f"/me/deputies/{a['id']}/photo", headers=b["h"]).status_code == 404
    assert client.get("/me/deputies", headers=a["h"]).status_code == 404
    assert client.get("/me/photo", headers=b["h"]).status_code == 404
    # الصورة على القرص مشفّرة
    for p in (get_settings().data_dir / "files").rglob("*.enc"):
        assert PNG not in p.read_bytes()

    # السؤال
    q = client.post("/me/questions", headers=a["h"], json={"subject": "طريق ولائي متدهور", "text": "ما هي إجراءات الجهاز التنفيذي لصيانة الطريق الولائي؟"})
    assert q.status_code == 201, q.text
    qid = q.json()["id"]
    assert q.json()["status"] == "submitted"

    # النص مشفّر في القاعدة
    with engine.connect() as conn:
        raw = conn.execute(text("select text, subject from questions")).one()
    assert raw[0].startswith("v1:") and "الطريق" not in raw[0] and raw[1].startswith("v1:")

    # النائب ب لا يرى سؤال النائب أ
    assert client.get(f"/me/questions/{qid}", headers=b["h"]).status_code == 404

    # مراجعة ثم إرجاع للتعديل
    assert client.post(f"/staff/questions/{qid}/start-review", headers=op).json()["status"] == "under_review"
    assert client.post(f"/staff/questions/{qid}/return", headers=op, json={"note": "حدّد الطريق برقمه"}).json()["status"] == "returned"
    mine = client.get(f"/me/questions/{qid}", headers=a["h"]).json()
    assert mine["status"] == "returned" and mine["return_note"] == "حدّد الطريق برقمه"

    # لا إحالة قبل التأكيد
    assert client.post(f"/staff/questions/{qid}/refer", headers=op).status_code == 409
    # الديوان لا يعدّل نص النائب، والنائب لا يعدّل إلا بعد الإرجاع
    assert client.put(f"/me/questions/{qid}", headers=b["h"], json={"subject": "xxx", "text": "x" * 20}).status_code == 404

    r = client.put(f"/me/questions/{qid}", headers=a["h"], json={"subject": "الطريق الولائي رقم 40", "text": "ما هي إجراءات الجهاز التنفيذي لصيانة الطريق الولائي رقم 40؟"})
    assert r.status_code == 200 and r.json()["status"] == "submitted"
    assert client.put(f"/me/questions/{qid}", headers=a["h"], json={"subject": "yyy", "text": "y" * 20}).status_code == 409

    # تأكيد ثم إحالة ثم رد ممسوح
    assert client.post(f"/staff/questions/{qid}/confirm", headers=op).json()["status"] == "confirmed"
    assert client.post(f"/staff/questions/{qid}/refer", headers=op).json()["status"] == "referred"
    assert client.get(f"/me/questions/{qid}/reply", headers=a["h"]).status_code == 404
    bad = client.post(f"/staff/questions/{qid}/reply", headers=op, files={"file": ("x.pdf", b"not a pdf at all", "application/pdf")})
    assert bad.status_code == 415
    ok = client.post(f"/staff/questions/{qid}/reply", headers=op, files={"file": ("reply.pdf", PDF, "application/pdf")})
    assert ok.status_code == 200 and ok.json()["status"] == "answered"

    got = client.get(f"/me/questions/{qid}/reply", headers=a["h"])
    assert got.status_code == 200 and got.content == PDF and got.headers["content-type"] == "application/pdf"
    assert client.get(f"/me/questions/{qid}/reply", headers=b["h"]).status_code == 404
    for p in (get_settings().data_dir / "files").rglob("*.enc"):
        assert PDF[:30] not in p.read_bytes()

    # المسار الكامل ظاهر للنائب، والديوان يرى الصياغتين
    events = [e["status"] for e in client.get(f"/me/questions/{qid}", headers=a["h"]).json()["events"]]
    assert events == ["submitted", "under_review", "returned", "submitted", "confirmed", "referred", "answered"]
    staff = client.get(f"/staff/questions/{qid}", headers=op).json()
    assert len(staff["versions"]) == 2 and staff["deputy_name"] == "نائب أ"


def test_notifications_targeting(client, world):
    op, a, b = world["op"], world["a"], world["b"]
    r = client.post("/staff/notifications", headers=op, json={"kind": "meeting", "title": "اجتماع لجنة المالية", "body": "الأحد 10:00", "meeting_at": "2026-11-01T10:00:00+01:00", "target_type": "committees", "committee_ids": [world["c1"]]})
    assert r.status_code == 201 and r.json()["recipients"] == 1
    nid = r.json()["id"]
    assert len(client.get("/me/notifications", headers=a["h"]).json()) == 1
    assert client.get("/me/notifications", headers=b["h"]).json() == []
    assert client.post(f"/me/notifications/{nid}/read", headers=b["h"]).status_code == 404
    assert client.post(f"/me/notifications/{nid}/read", headers=a["h"]).status_code == 204
    rc = client.get(f"/staff/notifications/{nid}/receipts", headers=op).json()
    assert rc[0]["read_at"] is not None

    # دعوة اجتماع بلا موعد مرفوضة
    bad = client.post("/staff/notifications", headers=op, json={"kind": "meeting", "title": "اجتماع", "body": "x", "target_type": "all"})
    assert bad.status_code == 422
    # للجميع
    allr = client.post("/staff/notifications", headers=op, json={"kind": "info", "title": "معلومة مهمة", "body": "نص", "target_type": "all"})
    assert allr.json()["recipients"] == 2
    # النص مشفّر في القاعدة
    with engine.connect() as conn:
        rows = conn.execute(text("select title, body from notifications")).all()
    assert all(v.startswith("v1:") for row in rows for v in row)


def test_permissions(client, admin_h, world):
    op, a = world["op"], world["a"]
    assert client.post("/admin/staff", headers=op, json={"username": "evil", "full_name": "xx", "password": "long-enough-pass1", "role": "admin"}).status_code == 403
    assert client.get("/admin/audit", headers=op).status_code == 403
    assert client.get("/staff/questions", headers=a["h"]).status_code == 401  # رمز نائب على واجهة الموظفين
    assert client.get("/me/questions", headers=op).status_code == 401  # رمز موظف على واجهة النواب
    assert client.get("/me/questions").status_code == 401
    assert client.get("/openapi.json").status_code == 404


def test_device_binding_and_revocation(client, admin_h, world):
    a = world["a"]
    # رمز التحديث يدور. الرمز السابق يُقبل في مهلة قصيرة (ضياع رد التجديد على الشبكة)
    r = client.post("/auth/refresh", json={"refresh_token": a["refresh"], "device_uid": a["uid"]})
    assert r.status_code == 200
    new = r.json()
    assert new["refresh_token"] != a["refresh"]
    again = client.post("/auth/refresh", json={"refresh_token": a["refresh"], "device_uid": a["uid"]})
    assert again.status_code == 200  # إعادة محاولة بالرمز القديم داخل المهلة
    new = again.json()
    # بعد انقضاء المهلة يسقط الرمز القديم
    from datetime import timedelta
    from sqlalchemy import update
    from app.db import SessionLocal
    from app import models
    from app.security import utcnow
    with SessionLocal() as db:
        db.execute(update(models.Device).values(prev_refresh_until=utcnow() - timedelta(minutes=1)))
        db.commit()
    assert client.post("/auth/refresh", json={"refresh_token": a["refresh"], "device_uid": a["uid"]}).status_code == 401
    # جهاز مختلف لا يستعمل رمز التحديث
    assert client.post("/auth/refresh", json={"refresh_token": new["refresh_token"], "device_uid": "another-device-9999"}).status_code == 401
    # رمز الدعوة لا يُستعمل مرتين
    assert client.post("/auth/activate", json={"phone": "0550112233", "code": a["code"], "device_uid": "device-uid-x-9999", "platform": "ios"}).status_code == 400

    # إعادة ضبط الجهاز تقطع الجلسة فوراً
    assert client.get("/me/questions", headers={"Authorization": f"Bearer {new['access_token']}"}).status_code == 200
    assert client.post(f"/admin/deputies/{a['id']}/reset-device", headers=admin_h).status_code == 204
    assert client.get("/me/questions", headers={"Authorization": f"Bearer {new['access_token']}"}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": new["refresh_token"], "device_uid": a["uid"]}).status_code == 401


def test_invite_and_staff_lockouts(client, admin_h):
    client.post("/admin/mandates", headers=admin_h, json={"label": "الدورة الحالية", "start_year": 2026, "end_year": 2031, "active": True})
    did = client.post("/admin/deputies", headers=admin_h, json={"full_name": "نائب", "phone": "0770000000"}).json()["id"]
    code = client.post(f"/admin/deputies/{did}/invite", headers=admin_h).json()["code"]
    body = {"phone": "0770000000", "device_uid": "device-uid-lock-1", "platform": "android"}
    for _ in range(5):
        assert client.post("/auth/activate", json={**body, "code": "AAAAA-BBBBB"}).status_code == 400
    # بعد 5 محاولات خاطئة من العنوان نفسه يُحجب هذا العنوان لهذا الهاتف (حتى بالرمز الصحيح)
    assert client.post("/auth/activate", json={**body, "code": code}).status_code == 429
    # لكن الرمز نفسه لم يُحرق: من عنوان آخر يعمل
    from app.ratelimit import limiter

    limiter.clear()
    assert client.post("/auth/activate", json={**body, "code": code}).status_code == 200

    # قفل الموظف لكل (مستخدم، IP)
    for _ in range(5):
        assert client.post("/auth/staff/login", json={"username": "admin", "password": "wrong-password"}).status_code == 401
    assert client.post("/auth/staff/login", json={"username": "admin", "password": "admin-password-123"}).status_code == 429


def test_attacker_cannot_lock_admin_out_from_other_ip(client, admin_h):
    """هجوم تعطيل الحساب: محاولات خاطئة من IP آخر لا تمنع الأدمن الحقيقي."""
    from app.ratelimit import limiter

    s = __import__("app.config", fromlist=["get_settings"]).get_settings()
    for _ in range(s.max_login_failures + 3):
        limiter.add("login-fail:admin:6.6.6.6")  # عنوان المهاجم
    assert client.post("/auth/staff/login", json={"username": "admin", "password": "admin-password-123"}).status_code == 200


def test_distributed_attack_cap_per_username(client, admin_h):
    from app.config import get_settings
    from app.ratelimit import limiter

    s = get_settings()
    for i in range(s.max_login_failures * 6):
        limiter.add("login-fail-total:admin")
    assert client.post("/auth/staff/login", json={"username": "admin", "password": "admin-password-123"}).status_code == 429


def test_ip_rate_limit_on_login(client):
    codes = [client.post("/auth/staff/login", json={"username": f"u{i}", "password": "x"}).status_code for i in range(40)]
    assert 429 in codes and codes.count(401) <= 30


def test_cf_header_spoof_ignored_from_non_loopback(client, admin_h):
    """TestClient يأتي من عنوان غير loopback، فيُتجاهل رأس cf-connecting-ip المنتحَل."""
    client.post("/auth/staff/login", json={"username": "admin", "password": "wrong-password"}, headers={"cf-connecting-ip": "9.9.9.9"})
    log = client.get("/admin/audit", headers=admin_h).json()
    failed = [r for r in log if r["action"] == "login_failed"]
    assert failed and failed[0]["ip"] != "9.9.9.9"


def test_client_ip_trusts_header_only_from_loopback():
    from types import SimpleNamespace

    from app.deps import client_ip

    def req(peer, cf=None):
        h = {"cf-connecting-ip": cf} if cf else {}
        return SimpleNamespace(client=SimpleNamespace(host=peer), headers=h)

    assert client_ip(req("127.0.0.1", "1.2.3.4")) == "1.2.3.4"
    assert client_ip(req("192.168.1.9", "1.2.3.4")) == "192.168.1.9"
    assert client_ip(req("127.0.0.1")) == "127.0.0.1"


def test_password_change_invalidates_old_staff_token(client, admin_h, world):
    old_op = world["op"]
    assert client.get("/staff/questions", headers=old_op).status_code == 200
    ops = [u for u in client.get("/admin/staff", headers=admin_h).json() if u["username"] == "diwan"]
    r = client.patch(f"/admin/staff/{ops[0]['id']}", headers=admin_h, json={"password": "brand-new-password-9"})
    assert r.status_code == 200
    assert client.get("/staff/questions", headers=old_op).status_code == 401
    assert client.get("/staff/questions", headers=login(client, "diwan", "brand-new-password-9")).status_code == 200


def test_body_size_limits(client, admin_h):
    big = "x" * (300 * 1024)
    r = client.post("/admin/staff", headers=admin_h, json={"username": "zzz", "full_name": big, "password": "a" * 20, "role": "operator"})
    assert r.status_code == 413


def test_startup_validation_rejects_bad_keys(monkeypatch):
    from app import security
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "field_key", "")
    import pytest

    with pytest.raises(RuntimeError):
        security.validate_config()
    monkeypatch.setattr(s, "field_key", "not base64!!")
    with pytest.raises(RuntimeError):
        security.validate_config()


def test_file_responses_are_sandboxed(client, admin_h, world):
    a = world["a"]
    q = client.post("/me/questions", headers=a["h"], json={"subject": "موضوع السؤال", "text": "نص السؤال الطويل بما يكفي"}).json()
    for act in ("confirm", "refer"):
        assert client.post(f"/staff/questions/{q['id']}/{act}", headers=world["op"]).status_code == 200
    up = client.post(f"/staff/questions/{q['id']}/reply", headers=world["op"], files={"file": ("r.pdf", PDF, "application/pdf")})
    assert up.status_code == 200, up.text
    r = client.get(f"/me/questions/{q['id']}/reply", headers=a["h"])
    assert r.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_question_creation_rate_limit(client, world):
    a = world["a"]
    codes = [
        client.post("/me/questions", headers=a["h"], json={"subject": f"موضوع {i}", "text": "نص السؤال الطويل بما يكفي"}).status_code
        for i in range(22)
    ]
    assert codes.count(201) == 20 and codes[-1] == 429


def test_mandate_is_five_years_and_switch_revokes(client, admin_h, world):
    assert client.post("/admin/mandates", headers=admin_h, json={"label": "x", "start_year": 2026, "end_year": 2030, "active": True}).status_code == 422
    a = world["a"]
    assert client.get("/me/questions", headers=a["h"]).status_code == 200
    # دورة جديدة نشطة => جلسات نواب الدورة السابقة تسقط
    assert client.post("/admin/mandates", headers=admin_h, json={"label": "2031-2036", "start_year": 2031, "end_year": 2036, "active": True}).status_code == 201
    assert client.get("/me/questions", headers=a["h"]).status_code == 401


def test_upload_limits(client, admin_h, world):
    a, op = world["a"], world["op"]
    r = client.put(f"/admin/deputies/{a['id']}/photo", headers=admin_h, files={"file": ("p.exe", b"MZ" + b"\x00" * 100, "image/png")})
    assert r.status_code == 415
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (get_settings().max_photo_mb * 1024 * 1024 + 10)
    r = client.put(f"/admin/deputies/{a['id']}/photo", headers=admin_h, files={"file": ("p.png", big, "image/png")})
    assert r.status_code == 413


def test_panel_is_served_with_csp(client):
    r = client.get("/panel/", follow_redirects=False)
    assert r.status_code == 200 and '<html lang="ar" dir="rtl">' in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/", follow_redirects=False).headers["location"] == "/panel/"
    # الملفات المبنية متاحة، ولا يُكشف شيء خارج مجلد اللوحة
    import re
    js = re.search(r'src="(/panel/assets/[^"]+\.js)"', r.text).group(1)
    assert client.get(js).status_code == 200
    assert client.get("/panel/../main.py").status_code in (400, 404)


def test_profile_settings_and_fcm(client, admin_h, world):
    a, op = world["a"], world["op"]
    # اسم الولاية اختياري: غير مضبوط افتراضياً ويُقرأ بلا مصادقة
    info = client.get("/public/info").json()
    assert info["wilaya_name"] is None and info["app_name"]
    assert client.put("/admin/settings", headers=op, json={"wilaya_name": "x"}).status_code == 403
    assert client.put("/admin/settings", headers=admin_h, json={"wilaya_name": "  ولاية تجريبية  "}).json()["wilaya_name"] == "ولاية تجريبية"
    assert client.get("/public/info").json()["wilaya_name"] == "ولاية تجريبية"
    assert client.put("/admin/settings", headers=admin_h, json={"wilaya_name": "   "}).status_code == 200
    assert client.get("/public/info").json()["wilaya_name"] is None

    p = client.get("/me/profile", headers=a["h"]).json()
    assert p["full_name"] == "نائب أ" and p["committees"] == ["لجنة المالية"] and p["mandate_label"] == "2026-2031"
    assert client.get("/me/profile", headers=op).status_code == 401

    assert client.post("/me/fcm-token", headers=a["h"], json={"fcm_token": "new-token"}).status_code == 204
    from sqlalchemy import select
    from app.db import SessionLocal
    from app import models
    with SessionLocal() as db:
        tok = db.scalar(select(models.Device.fcm_token).where(models.Device.deputy_id == a["id"], models.Device.active.is_(True)))
    assert tok == "new-token"
