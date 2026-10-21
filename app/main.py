import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .db import Base, engine
from .deps import client_ip
from .ratelimit import limiter
from .security import validate_config
from .routers import admin, auth, deputy, public, staff

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_config()  # يفشل الإقلاع بوضوح بدل أخطاء 500 لاحقة
    yield


app = FastAPI(
    lifespan=lifespan,
    title="خادم المجلس الشعبي الولائي",
    docs_url=None,  # لا توثيق تفاعلي علني في الإنتاج
    redoc_url=None,
    openapi_url=None,
)


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_JSON_BYTES = 256 * 1024
_UPLOAD_SUFFIXES = ("/reply", "/photo")


@app.middleware("http")
async def guard_requests(request: Request, call_next):
    """حدّ عام لكل IP وحدّ لحجم الجسم (الملفات حتى 20 ميغابايت، وغيرها 256 كيلوبايت)."""
    if not request.url.path.startswith("/panel"):
        ip = client_ip(request) or "?"
        if not limiter.hit(f"global:{ip}", 600, 60):
            return JSONResponse({"detail": "طلبات كثيرة، حاول لاحقاً"}, status_code=429)
    if request.method in ("POST", "PUT", "PATCH"):
        is_upload = request.url.path.endswith(_UPLOAD_SUFFIXES)
        limit = MAX_UPLOAD_BYTES if is_upload else MAX_JSON_BYTES
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "طلب غير صالح"}, status_code=400)
        if length > limit:
            return JSONResponse({"detail": "حجم الطلب كبير جداً"}, status_code=413)
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if "Cache-Control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-store"
    if request.url.path.startswith("/panel"):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' blob: data:; object-src 'self' blob:; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logging.getLogger("apw").exception("خطأ غير متوقع")
    return JSONResponse({"detail": "خطأ داخلي في الخادم"}, status_code=500)


for r in (public.router, auth.router, admin.router, staff.router, deputy.router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"ok": True}


# لوحة الأدمن (React) مبنيّة مسبقاً داخل app/static/panel وتُخدَّم من الخادم نفسه
_PANEL = Path(__file__).parent / "static" / "panel"
if _PANEL.is_dir():
    app.mount("/panel", StaticFiles(directory=_PANEL, html=True), name="panel")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/panel/")


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
