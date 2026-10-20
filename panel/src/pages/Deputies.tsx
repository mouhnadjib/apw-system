import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { Committee, Deputy, Invite } from "../types";
import { Alert, CheckList, Field, Loading, Modal, Photo, errMsg, fmtDate, useLoad } from "../ui";

interface FormState { full_name: string; title: string; phone: string; committee_ids: number[] }
const EMPTY: FormState = { full_name: "", title: "", phone: "", committee_ids: [] };
const MAX_PHOTO = 3 * 1024 * 1024;

export default function Deputies() {
  const deps = useLoad(() => api.get<Deputy[]>("/staff/deputies"));
  const comm = useLoad(() => api.get<Committee[]>("/staff/committees"));
  const [editing, setEditing] = useState<Deputy | "new" | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [msg, setMsg] = useState<{ kind: "err" | "ok"; text: string } | null>(null);
  const [invite, setInvite] = useState<{ d: Deputy; inv: Invite } | null>(null);
  const [ver, setVer] = useState<Record<number, number>>({});
  const [copied, setCopied] = useState(false);

  function openNew() { setForm(EMPTY); setPhoto(null); setFormErr(""); setEditing("new"); }
  function openEdit(d: Deputy) {
    setForm({ full_name: d.full_name, title: d.title ?? "", phone: d.phone, committee_ids: d.committees.map((c) => c.id) });
    setPhoto(null); setFormErr(""); setEditing(d);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (photo && photo.size > MAX_PHOTO) return setFormErr("حجم الصورة يتجاوز 3 ميغابايت");
    setBusy(true);
    setFormErr("");
    try {
      const body = { full_name: form.full_name.trim(), title: form.title.trim() || null, phone: form.phone.trim(), committee_ids: form.committee_ids };
      const saved = editing === "new"
        ? await api.post<Deputy>("/admin/deputies", body)
        : await api.patch<Deputy>(`/admin/deputies/${(editing as Deputy).id}`, body);
      if (photo) {
        const fd = new FormData();
        fd.append("file", photo);
        await api.put(`/admin/deputies/${saved.id}/photo`, fd);
        setVer((v) => ({ ...v, [saved.id]: (v[saved.id] ?? 0) + 1 }));
      }
      setEditing(null);
      setMsg({ kind: "ok", text: "تم الحفظ" });
      deps.reload();
    } catch (x) {
      setFormErr(errMsg(x));
    } finally {
      setBusy(false);
    }
  }

  async function run(fn: () => Promise<unknown>, ok: string) {
    setMsg(null);
    try { await fn(); setMsg({ kind: "ok", text: ok }); deps.reload(); } catch (x) { setMsg({ kind: "err", text: errMsg(x) }); }
  }

  async function makeInvite(d: Deputy) {
    if (!window.confirm(`إنشاء رمز دعوة جديد لـ ${d.full_name}؟ سيُلغى أي رمز سابق غير مستعمل.`)) return;
    setMsg(null);
    try {
      setInvite({ d, inv: await api.post<Invite>(`/admin/deputies/${d.id}/invite`) });
      setCopied(false);
    } catch (x) { setMsg({ kind: "err", text: errMsg(x) }); }
  }

  return (
    <>
      <div className="page-head">
        <h2>النواب</h2>
        <button className="primary" onClick={openNew} disabled={!comm.data && !comm.error}>+ إضافة نائب</button>
      </div>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <Loading error={deps.error} loading={deps.loading && !deps.data} />
      {deps.data && (
        <div className="card table-wrap" style={{ padding: 0 }}>
          <table>
            <thead><tr><th></th><th>الاسم</th><th>الهاتف</th><th>اللجان</th><th>الحالة</th><th></th></tr></thead>
            <tbody>
              {deps.data.map((d) => (
                <tr key={d.id}>
                  <td><Photo key={`${d.id}-${ver[d.id] ?? 0}`} id={d.id} has={d.has_photo} name={d.full_name} /></td>
                  <td>{d.full_name}{d.title && <div className="muted" style={{ fontSize: ".82rem" }}>{d.title}</div>}</td>
                  <td dir="ltr" style={{ textAlign: "right" }}>{d.phone}</td>
                  <td>{d.committees.map((c) => c.name).join("، ") || <span className="muted">—</span>}</td>
                  <td><span className={`badge ${d.active ? "st-confirmed" : "off"}`}>{d.active ? "نشط" : "معطّل"}</span></td>
                  <td>
                    <div className="row">
                      <button className="small" onClick={() => openEdit(d)}>تعديل</button>
                      {d.active && <button className="small" onClick={() => makeInvite(d)}>رمز دعوة</button>}
                      {d.active && <button className="small" onClick={() => window.confirm("سيُفصل جهاز النائب وتنتهي جلسته فوراً. متابعة؟") && run(() => api.post(`/admin/deputies/${d.id}/reset-device`), "فُصل الجهاز؛ أنشئ رمز دعوة جديداً")}>فصل الجهاز</button>}
                      <button className={`small${d.active ? " danger" : ""}`}
                        onClick={() => (!d.active || window.confirm("تعطيل النائب يقطع جلسته فوراً. متابعة؟")) && run(() => api.patch(`/admin/deputies/${d.id}`, { active: !d.active }), d.active ? "عُطّل النائب" : "فُعّل النائب")}>
                        {d.active ? "تعطيل" : "تفعيل"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!deps.data.length && <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: "2rem" }}>لا يوجد نواب في الدورة الحالية</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <Modal title={editing === "new" ? "إضافة نائب" : "تعديل نائب"} onClose={() => setEditing(null)}>
          <form onSubmit={save}>
            {formErr && <Alert kind="err">{formErr}</Alert>}
            <Field label="الاسم الكامل"><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required minLength={2} autoFocus /></Field>
            <Field label="الصفة (اختياري)" hint="مثل: رئيس المجلس، نائب الرئيس، رئيس لجنة"><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={64} /></Field>
            <Field label="رقم الهاتف" hint="يُستعمل لتفعيل الحساب مع رمز الدعوة"><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} required dir="ltr" inputMode="tel" /></Field>
            <Field label="اللجان"><CheckList items={comm.data ?? []} selected={form.committee_ids} onChange={(ids) => setForm({ ...form, committee_ids: ids })} label={(c) => c.name} /></Field>
            <Field label="الصورة (JPEG/PNG، حتى 3 ميغابايت)"><input type="file" accept="image/jpeg,image/png" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} /></Field>
            <div className="row"><button className="primary" disabled={busy}>{busy ? "…" : "حفظ"}</button><button type="button" onClick={() => setEditing(null)}>إلغاء</button></div>
          </form>
        </Modal>
      )}

      {invite && (
        <Modal title={`رمز دعوة: ${invite.d.full_name}`} onClose={() => setInvite(null)}>
          <div className="code-box">{invite.inv.code}</div>
          <p>صالح حتى <strong>{fmtDate(invite.inv.expires_at)}</strong>، ويُستعمل مرة واحدة. يُدخله النائب مع رقم هاتفه <strong dir="ltr">{invite.d.phone}</strong> عند أول فتح للتطبيق.</p>
          <Alert kind="err">يُعرض هذا الرمز الآن فقط ولا يمكن استرجاعه لاحقاً. سلّمه للنائب مباشرة.</Alert>
          <div className="row">
            <button className="primary" onClick={async () => { await navigator.clipboard?.writeText(invite.inv.code).catch(() => {}); setCopied(true); }}>{copied ? "نُسخ ✓" : "نسخ الرمز"}</button>
            <button onClick={() => setInvite(null)}>إغلاق</button>
          </div>
        </Modal>
      )}
    </>
  );
}
