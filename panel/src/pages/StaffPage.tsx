import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { Role, StaffUser } from "../types";
import { Alert, Field, Loading, Modal, ROLE_AR, errMsg, useLoad } from "../ui";

export default function StaffPage() {
  const staff = useLoad(() => api.get<StaffUser[]>("/admin/staff"));
  const [form, setForm] = useState({ username: "", full_name: "", password: "", role: "operator" as Role });
  const [pwFor, setPwFor] = useState<StaffUser | null>(null);
  const [newPw, setNewPw] = useState("");
  const [msg, setMsg] = useState<{ kind: "err" | "ok"; text: string } | null>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    try {
      await api.post("/admin/staff", { ...form, username: form.username.trim(), full_name: form.full_name.trim() });
      setForm({ username: "", full_name: "", password: "", role: "operator" });
      setMsg({ kind: "ok", text: "أُنشئ الحساب" });
      staff.reload();
    } catch (x) { setMsg({ kind: "err", text: errMsg(x) }); }
  }
  async function patch(u: StaffUser, body: object, ok: string) {
    setMsg(null);
    try { await api.patch(`/admin/staff/${u.id}`, body); setMsg({ kind: "ok", text: ok }); staff.reload(); return true; }
    catch (x) { setMsg({ kind: "err", text: errMsg(x) }); return false; }
  }

  return (
    <>
      <div className="page-head"><h2>الموظفون</h2></div>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="grid2" style={{ alignItems: "start" }}>
        <div className="card" style={{ padding: 0 }}>
          <Loading error={staff.error} loading={staff.loading && !staff.data} />
          <table>
            <thead><tr><th>الاسم</th><th>الدور</th><th>الحالة</th><th></th></tr></thead>
            <tbody>
              {(staff.data ?? []).map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}<div className="muted" dir="ltr" style={{ textAlign: "right", fontSize: ".8rem" }}>{u.username}</div></td>
                  <td>{ROLE_AR[u.role]}</td>
                  <td><span className={`badge ${u.active ? "st-confirmed" : "off"}`}>{u.active ? "نشط" : "معطّل"}</span></td>
                  <td>
                    <div className="row">
                      <button className="small" onClick={() => { setNewPw(""); setPwFor(u); }}>كلمة مرور</button>
                      <button className={`small${u.active ? " danger" : ""}`} onClick={() => patch(u, { active: !u.active }, u.active ? "عُطّل الحساب" : "فُعّل الحساب")}>{u.active ? "تعطيل" : "تفعيل"}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <form className="card" onSubmit={create}>
          <h3>حساب جديد</h3>
          <Field label="الاسم الكامل"><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required minLength={2} /></Field>
          <Field label="اسم المستخدم" hint="أحرف لاتينية وأرقام فقط"><input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required minLength={3} pattern="[A-Za-z0-9_.\-]+" dir="ltr" autoComplete="off" /></Field>
          <Field label="كلمة المرور" hint="12 حرفاً على الأقل"><input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={12} dir="ltr" autoComplete="new-password" /></Field>
          <Field label="الدور">
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
              <option value="operator">{ROLE_AR.operator}: الأسئلة والإشعارات فقط</option>
              <option value="admin">{ROLE_AR.admin}: كل الصلاحيات</option>
            </select>
          </Field>
          <button className="primary">إنشاء</button>
        </form>
      </div>

      {pwFor && (
        <Modal title={`كلمة مرور جديدة: ${pwFor.full_name}`} onClose={() => setPwFor(null)}>
          <Field label="كلمة المرور الجديدة" hint="12 حرفاً على الأقل. تفك أيضاً قفل الحساب إن كان مقفلاً.">
            <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} minLength={12} dir="ltr" autoFocus autoComplete="new-password" />
          </Field>
          <div className="row">
            <button className="primary" disabled={newPw.length < 12} onClick={async () => { if (await patch(pwFor, { password: newPw }, "غُيّرت كلمة المرور")) setPwFor(null); }}>حفظ</button>
            <button onClick={() => setPwFor(null)}>إلغاء</button>
          </div>
        </Modal>
      )}
    </>
  );
}
