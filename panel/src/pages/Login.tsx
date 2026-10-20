import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { Alert, errMsg } from "../ui";

export default function Login() {
  const { login } = useAuth();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try { await login(u.trim(), p); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  }
  return (
    <div className="login-wrap">
      <form className="card login" onSubmit={submit}>
        <h1>المجلس الشعبي الولائي</h1>
        <p className="muted">لوحة الديوان — تسجيل الدخول</p>
        {err && <Alert kind="err">{err}</Alert>}
        <label className="field"><span>اسم المستخدم</span>
          <input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" autoFocus required dir="ltr" />
        </label>
        <label className="field"><span>كلمة المرور</span>
          <input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required dir="ltr" />
        </label>
        <button className="primary" disabled={busy}>{busy ? "…" : "دخول"}</button>
      </form>
    </div>
  );
}
