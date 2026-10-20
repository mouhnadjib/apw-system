import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { Committee, Mandate } from "../types";
import { Alert, Field, Loading, errMsg, useLoad } from "../ui";

export default function Setup() {
  const mandates = useLoad(() => api.get<Mandate[]>("/admin/mandates"));
  const committees = useLoad(() => api.get<Committee[]>("/staff/committees").catch(() => [] as Committee[]));
  const [label, setLabel] = useState("");
  const [start, setStart] = useState(new Date().getFullYear());
  const [cName, setCName] = useState("");
  const [wilaya, setWilaya] = useState("");
  const info = useLoad(async () => {
    const r = await api.get<{ wilaya_name: string | null }>("/public/info");
    setWilaya(r.wilaya_name ?? "");
    return r;
  });
  const [msg, setMsg] = useState<{ kind: "err" | "ok"; text: string } | null>(null);

  const active = mandates.data?.find((m) => m.active);

  async function addMandate(e: FormEvent) {
    e.preventDefault();
    const warn = active
      ? "ستصبح هذه الدورة هي النشطة، وتُقطع فوراً جلسات نواب الدورة الحالية. متابعة؟"
      : "إنشاء الدورة وتفعيلها؟";
    if (!window.confirm(warn)) return;
    setMsg(null);
    try {
      await api.post("/admin/mandates", { label: label.trim(), start_year: start, end_year: start + 5, active: true });
      setLabel("");
      setMsg({ kind: "ok", text: "أُنشئت الدورة وفُعِّلت" });
      mandates.reload(); committees.reload();
    } catch (x) { setMsg({ kind: "err", text: errMsg(x) }); }
  }

  async function addCommittee(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    try {
      await api.post("/admin/committees", { name: cName.trim() });
      setCName("");
      committees.reload();
    } catch (x) { setMsg({ kind: "err", text: errMsg(x) }); }
  }

  async function saveWilaya(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    try {
      await api.put("/admin/settings", { wilaya_name: wilaya.trim() || null });
      setMsg({ kind: "ok", text: "حُفظ اسم الولاية" });
      info.reload();
    } catch (x) { setMsg({ kind: "err", text: errMsg(x) }); }
  }

  return (
    <>
      <div className="page-head"><h2>الدورة واللجان</h2></div>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="grid2" style={{ alignItems: "start" }}>
        <div className="card">
          <h3>الدورات (5 سنوات)</h3>
          <Loading error={mandates.error} loading={mandates.loading && !mandates.data} />
          <ul style={{ paddingInlineStart: "1.2rem" }}>
            {(mandates.data ?? []).map((m) => (
              <li key={m.id}>{m.label} ({m.start_year}–{m.end_year}) {m.active && <span className="badge st-confirmed">النشطة</span>}</li>
            ))}
            {mandates.data && !mandates.data.length && <li className="muted">لا توجد دورة بعد، أنشئ الدورة الأولى للبدء.</li>}
          </ul>
          <form onSubmit={addMandate}>
            <h3>دورة جديدة</h3>
            <Field label="التسمية"><input value={label} onChange={(e) => setLabel(e.target.value)} required minLength={2} placeholder="مثال: الدورة 2026–2031" /></Field>
            <Field label="سنة البداية" hint={`تنتهي سنة ${start + 5}`}><input type="number" value={start} min={2000} max={2100} onChange={(e) => setStart(Number(e.target.value))} /></Field>
            <button className="primary">إنشاء وتفعيل</button>
          </form>
        </div>

        <div className="card">
          <h3>اللجان {active ? `— ${active.label}` : ""}</h3>
          <Loading error={committees.error} loading={committees.loading && !committees.data} />
          <ul style={{ paddingInlineStart: "1.2rem" }}>
            {(committees.data ?? []).map((c) => <li key={c.id}>{c.name}</li>)}
            {committees.data && !committees.data.length && <li className="muted">لا توجد لجان</li>}
          </ul>
          <form onSubmit={addCommittee} className="row">
            <input style={{ flex: 1, minWidth: 180 }} value={cName} onChange={(e) => setCName(e.target.value)} placeholder="اسم اللجنة" required minLength={2} disabled={!active} />
            <button className="primary" disabled={!active}>إضافة</button>
          </form>
        </div>
      </div>

      <form className="card" onSubmit={saveWilaya} style={{ maxWidth: 520 }}>
        <h3>اسم الولاية (اختياري)</h3>
        <p className="muted" style={{ marginTop: 0 }}>يظهر في ترويسة تطبيق النواب. اتركه فارغاً لإخفائه.</p>
        <div className="row">
          <input style={{ flex: 1, minWidth: 180 }} value={wilaya} onChange={(e) => setWilaya(e.target.value)} maxLength={64} placeholder="مثال: ولاية الجلفة" />
          <button className="primary" disabled={info.loading}>حفظ</button>
        </div>
      </form>
    </>
  );
}
