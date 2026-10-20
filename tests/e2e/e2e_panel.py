"""اختبار شامل للوحة في متصفح حقيقي: pip install playwright && playwright install chromium && python tests/e2e/e2e_panel.py"""
import base64, os, struct, subprocess, sys, tempfile, time, zlib, json, urllib.request
SCR = tempfile.mkdtemp(prefix="apw-shots-")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="apw-e2e-")
env = dict(os.environ,
    APW_DATABASE_URL=f"sqlite:///{tmp}/e2e.db", APW_DATA_DIR=f"{tmp}/data",
    APW_FILE_KEY=base64.b64encode(os.urandom(32)).decode(), APW_FIELD_KEY=base64.b64encode(os.urandom(32)).decode(),
    APW_JWT_SECRET=base64.urlsafe_b64encode(os.urandom(48)).decode())
os.environ.update({k: v for k, v in env.items() if k.startswith("APW_")})
sys.path.insert(0, ROOT); os.chdir(ROOT)
from app.main import init_db
from app.db import SessionLocal
from app import models
from app.security import hash_password
init_db()
with SessionLocal() as db:
    db.add(models.StaffUser(username="admin", full_name="مدير النظام", password_hash=hash_password("admin-password-123"), role=models.StaffRole.admin)); db.commit()

srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8765", "--log-level", "warning"], env=env, cwd=ROOT)
BASE = "http://127.0.0.1:8765"
for _ in range(50):
    try: urllib.request.urlopen(BASE + "/health"); break
    except Exception: time.sleep(0.2)

def png(path):
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes([15, 107, 79]) * 64 for _ in range(64))
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
png(f"{tmp}/photo.png")
open(f"{tmp}/reply.pdf", "wb").write(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")

def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r: return json.loads(r.read() or "null")
    except urllib.error.HTTPError as e: raise RuntimeError(f"{path} -> {e.code} {e.read().decode()}")

errors = []
from playwright.sync_api import sync_playwright, expect
try:
  with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 800}, locale="ar-DZ")
    page.on("dialog", lambda d: d.accept())
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type in ("error",) else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    def login(u, pw):
        page.goto(BASE + "/panel/")
        page.fill("input[autocomplete=username]", u); page.fill("input[type=password]", pw)
        page.click("button.primary"); page.wait_for_selector(".shell")

    page.goto(BASE + "/panel/"); page.wait_for_selector(".login")
    page.screenshot(path=f"{SCR}/01-login.png")
    page.fill("input[autocomplete=username]", "admin"); page.fill("input[type=password]", "wrong-password-xx"); page.click("button.primary")
    expect(page.locator(".alert.err")).to_contain_text("غير صحيحة")
    login("admin", "admin-password-123")

    # الدورة واللجان
    page.click("text=الدورة واللجان")
    page.fill("input[placeholder^='مثال']", "الدورة 2026–2031"); page.click("text=إنشاء وتفعيل")
    expect(page.locator(".alert.ok")).to_contain_text("أُنشئت")
    page.fill("input[placeholder='اسم اللجنة']", "لجنة المالية"); page.click("button:has-text('إضافة')")
    expect(page.locator("li", has_text="لجنة المالية")).to_be_visible()

    # موظف التسيير
    page.click("text=الموظفون")
    page.fill("label:has-text('الاسم الكامل') input", "موظف الديوان"); page.fill("label:has-text('اسم المستخدم') input", "diwan")
    page.fill("label:has-text('كلمة المرور') input", "operator-pass-1234"); page.click("form.card button.primary")
    expect(page.locator(".alert.ok")).to_contain_text("أُنشئ"); 

    # النائب + الصورة + الدعوة
    page.click("text=النواب")
    page.click("button:has-text('إضافة نائب')")
    m = page.locator(".modal")
    m.locator("label:has-text('الاسم الكامل') input").fill("بن عيسى عبد القادر")
    m.locator("label:has-text('الصفة') input").fill("رئيس لجنة")
    m.locator("label:has-text('رقم الهاتف') input").fill("0550 11 22 33")
    m.locator(".check", has_text="لجنة المالية").click()
    m.locator("input[type=file]").set_input_files(f"{tmp}/photo.png")
    m.locator("button.primary").click()
    expect(page.locator("tbody tr", has_text="بن عيسى")).to_be_visible()
    expect(page.locator("img.avatar")).to_be_visible(timeout=5000)
    page.click("button:has-text('رمز دعوة')")
    code = page.locator(".code-box").inner_text().strip()
    assert len(code) == 11, code
    page.screenshot(path=f"{SCR}/02-invite.png"); page.click(".modal button:has-text('إغلاق')")
    page.click("text=النواب"); page.screenshot(path=f"{SCR}/03-deputies.png")

    # النائب (من الهاتف) يفعّل ويرسل سؤالاً
    t = call("POST", "/auth/activate", {"phone": "0550112233", "code": code, "device_uid": "e2e-device-0001", "platform": "android"})
    dtok = t["access_token"]
    q = call("POST", "/me/questions", {"subject": "صيانة الطريق الولائي", "text": "ما هي إجراءات الجهاز التنفيذي لصيانة الطريق الولائي؟"}, dtok)

    # الديوان
    page.click("text=خروج"); page.wait_for_selector(".login")
    login("diwan", "operator-pass-1234")
    assert page.locator("a:has-text('النواب')").count() == 0  # لا تظهر قائمة الإدارة للديوان
    expect(page.locator(".tab.on")).to_contain_text("تحتاج مراجعة (1)")
    page.screenshot(path=f"{SCR}/04-questions.png")
    page.click("a:has-text('صيانة الطريق')")
    page.click("button:has-text('بدء المراجعة')"); expect(page.locator(".alert.ok")).to_contain_text("بدأت")
    page.click("button:has-text('إرجاع للنائب')"); page.fill(".modal textarea", "حدّد الطريق برقمه"); page.click(".modal button.primary")
    expect(page.locator(".note")).to_contain_text("حدّد الطريق برقمه")
    # النائب يعدّل
    call("PUT", f"/me/questions/{q['id']}", {"subject": "صيانة الطريق الولائي رقم 40", "text": "ما هي إجراءات الجهاز التنفيذي لصيانة الطريق الولائي رقم 40؟"}, dtok)
    page.reload(); page.wait_for_selector("h2")
    page.click("button:has-text('الصياغات السابقة')") if page.locator("button:has-text('الصياغات السابقة')").count() else None
    page.click("button:has-text('تأكيد')"); expect(page.locator(".alert.ok")).to_contain_text("أُكِّد")
    page.click("button:has-text('إحالة إلى الوالي')"); expect(page.locator(".alert.ok")).to_contain_text("أُحيل")
    page.set_input_files("input[type=file]", f"{tmp}/reply.pdf"); page.click("button:has-text('رفع الرد')")
    expect(page.locator(".alert.ok")).to_contain_text("رُفع الرد")
    expect(page.locator("button:has-text('عرض الرد الممسوح')")).to_be_visible()
    page.screenshot(path=f"{SCR}/05-question-detail.png", full_page=True)
    # النائب يحمّل الرد
    req = urllib.request.Request(BASE + f"/me/questions/{q['id']}/reply", headers={"Authorization": "Bearer " + dtok})
    assert urllib.request.urlopen(req).read().startswith(b"%PDF")

    # الإشعارات
    page.click("a:has-text('الإشعارات')")
    page.fill("label:has-text('العنوان') input", "اجتماع لجنة المالية"); page.fill("label:has-text('النص') textarea", "الأحد الساعة العاشرة")
    page.select_option("label:has-text('النوع') select", "meeting")
    page.fill("input[type=datetime-local]", "2026-11-01T10:00")
    page.select_option("label:has-text('المستلمون') select", "committees"); page.click(".check:has-text('لجنة المالية')")
    page.click("form.card button.primary"); expect(page.locator(".alert.ok")).to_contain_text("إلى 1 نائب")
    expect(page.locator("tbody tr", has_text="اجتماع لجنة المالية")).to_contain_text("0/1")
    page.click("button:has-text('التفاصيل')"); expect(page.locator(".modal")).to_contain_text("لم يقرأ بعد")
    page.screenshot(path=f"{SCR}/06-notifications.png")
    notifs = call("GET", "/me/notifications", token=dtok); assert len(notifs) == 1 and notifs[0]["kind"] == "meeting"
    b.close()
finally:
    srv.terminate()
print("JS errors:", errors or "none")
print("E2E OK")
