import base64
import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="apw-test-")
os.environ["APW_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["APW_DATA_DIR"] = f"{_tmp}/data"
os.environ["APW_FILE_KEY"] = base64.b64encode(os.urandom(32)).decode()
os.environ["APW_FIELD_KEY"] = base64.b64encode(os.urandom(32)).decode()
os.environ["APW_JWT_SECRET"] = base64.urlsafe_b64encode(os.urandom(48)).decode()

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, engine, Base
from app.main import app
from app import models
from app.security import hash_password

ADMIN_PW = "admin-password-123"


@pytest.fixture(autouse=True)
def _reset_limiter():
    from app.ratelimit import limiter

    limiter.clear()
    yield
    limiter.clear()


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(models.StaffUser(username="admin", full_name="الأدمن", password_hash=hash_password(ADMIN_PW), role=models.StaffRole.admin))
        db.commit()
    with TestClient(app) as c:
        yield c


def login(client, username, password):
    r = client.post("/auth/staff/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin_h(client):
    return login(client, "admin", ADMIN_PW)


@pytest.fixture()
def world(client, admin_h):
    """دورة + لجنتان + موظف تسيير + نائبان مفعّلان."""
    op_pw = "operator-pass-1234"
    r = client.post("/admin/staff", headers=admin_h, json={"username": "diwan", "full_name": "موظف الديوان", "password": op_pw, "role": "operator"})
    assert r.status_code == 201, r.text
    op_h = login(client, "diwan", op_pw)

    assert client.post("/admin/mandates", headers=admin_h, json={"label": "2026-2031", "start_year": 2026, "end_year": 2031, "active": True}).status_code == 201
    c1 = client.post("/admin/committees", headers=admin_h, json={"name": "لجنة المالية"}).json()["id"]
    c2 = client.post("/admin/committees", headers=admin_h, json={"name": "لجنة الصحة"}).json()["id"]

    deps = {}
    for key, name, phone, cids in (("a", "نائب أ", "0550 11 22 33", [c1]), ("b", "نائب ب", "+213661445566", [c2])):
        d = client.post("/admin/deputies", headers=admin_h, json={"full_name": name, "phone": phone, "title": "عضو", "committee_ids": cids})
        assert d.status_code == 201, d.text
        did = d.json()["id"]
        code = client.post(f"/admin/deputies/{did}/invite", headers=admin_h).json()["code"]
        phone_in = {"a": "0550112233", "b": "0661445566"}[key]
        act = client.post("/auth/activate", json={"phone": phone_in, "code": code, "device_uid": f"device-uid-{key}-0001", "platform": "android", "fcm_token": "tok" + key})
        assert act.status_code == 200, act.text
        t = act.json()
        deps[key] = {"id": did, "h": {"Authorization": f"Bearer {t['access_token']}"}, "refresh": t["refresh_token"], "uid": f"device-uid-{key}-0001", "code": code}
    return {"op": op_h, "c1": c1, "c2": c2, "a": deps["a"], "b": deps["b"]}
