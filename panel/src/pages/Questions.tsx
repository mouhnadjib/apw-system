import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import type { QStatus, QuestionDetail as QD, QuestionRow } from "../types";
import { Alert, Loading, Modal, STATUS_AR, StatusBadge, errMsg, fmtDate, useLoad } from "../ui";

const FILTERS: (QStatus | "all" | "todo")[] = ["todo", "all", "submitted", "under_review", "returned", "confirmed", "referred", "answered"];

export function QuestionsList() {
  const nav = useNavigate();
  const { data, error, loading, reload } = useLoad(() => api.get<QuestionRow[]>("/staff/questions?limit=500"));
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("todo");

  useEffect(() => {
    const id = window.setInterval(reload, 30000);
    return () => window.clearInterval(id);
  }, [reload]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: data?.length ?? 0, todo: 0 };
    data?.forEach((q) => {
      c[q.status] = (c[q.status] ?? 0) + 1;
      if (q.status === "submitted" || q.status === "under_review") c.todo++;
    });
    return c;
  }, [data]);

  const rows = (data ?? []).filter((q) =>
    filter === "all" ? true : filter === "todo" ? q.status === "submitted" || q.status === "under_review" : q.status === filter
  );

  return (
    <>
      <div className="page-head">
        <h2>الأسئلة الكتابية</h2>
        <button onClick={reload}>تحديث</button>
      </div>
      <div className="tabs">
        {FILTERS.map((f) => (
          <button key={f} className={`tab${filter === f ? " on" : ""}`} onClick={() => setFilter(f)}>
            {f === "todo" ? "تحتاج مراجعة" : f === "all" ? "الكل" : STATUS_AR[f]} ({counts[f] ?? 0})
          </button>
        ))}
      </div>
      <Loading error={error} loading={loading && !data} />
      {data && (
        <div className="card table-wrap" style={{ padding: 0 }}>
          <table>
            <thead><tr><th>#</th><th>الموضوع</th><th>النائب</th><th>الحالة</th><th>آخر تحديث</th></tr></thead>
            <tbody>
              {rows.map((q) => (
                <tr key={q.id} className="click" onClick={() => nav(`/questions/${q.id}`)}>
                  <td>{q.id}</td>
                  <td><Link to={`/questions/${q.id}`} onClick={(e) => e.stopPropagation()}>{q.subject}</Link></td>
                  <td>{q.deputy_name}</td>
                  <td><StatusBadge status={q.status} /></td>
                  <td>{fmtDate(q.updated_at)}</td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: "2rem" }}>لا توجد أسئلة في هذا التصنيف</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export function QuestionDetail() {
  const { id } = useParams();
  const { data: q, error, loading, setData } = useLoad(() => api.get<QD>(`/staff/questions/${id}`), [id]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "err" | "ok"; text: string } | null>(null);
  const [returning, setReturning] = useState(false);
  const [note, setNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [showVersions, setShowVersions] = useState(false);

  async function act(path: string, body?: unknown, ok = "تم") {
    setBusy(true);
    setMsg(null);
    try {
      setData(await api.post<QD>(`/staff/questions/${id}/${path}`, body));
      setMsg({ kind: "ok", text: ok });
      return true;
    } catch (e) {
      setMsg({ kind: "err", text: errMsg(e) });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function sendReply() {
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      setData(await api.post<QD>(`/staff/questions/${id}/reply`, fd));
      setFile(null);
      setMsg({ kind: "ok", text: "رُفع الرد وأُخطر النائب" });
    } catch (e) {
      setMsg({ kind: "err", text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }

  async function openReply() {
    const w = window.open("", "_blank");
    try {
      const b = await api.blob(`/staff/questions/${id}/reply`);
      const url = URL.createObjectURL(b);
      if (w) w.location.href = url;
      else window.location.href = url;
    } catch (e) {
      w?.close();
      setMsg({ kind: "err", text: errMsg(e) });
    }
  }

  if (!q) return <Loading error={error} loading={loading} />;
  const s = q.status;

  return (
    <>
      <div className="page-head">
        <div>
          <Link to="/questions">← كل الأسئلة</Link>
          <h2 style={{ marginTop: ".4rem" }}>{q.subject}</h2>
          <div className="row muted">
            <span>#{q.id}</span><span>النائب: <strong style={{ color: "var(--ink)" }}>{q.deputy_name}</strong></span>
            <span>أُرسل: {fmtDate(q.created_at)}</span>
          </div>
        </div>
        <StatusBadge status={s} />
      </div>

      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}

      <div className="grid2" style={{ alignItems: "start" }}>
        <div>
          <div className="card">
            <h3>نص السؤال</h3>
            <div className="qtext">{q.text}</div>
            {s === "returned" && q.return_note && <div className="note"><strong>ملاحظة الإرجاع:</strong> {q.return_note}</div>}
            {q.versions && q.versions.length > 1 && (
              <>
                <button className="small" style={{ marginTop: ".7rem" }} onClick={() => setShowVersions(!showVersions)}>
                  {showVersions ? "إخفاء" : "عرض"} الصياغات السابقة ({q.versions.length - 1})
                </button>
                {showVersions && q.versions.slice(0, -1).reverse().map((v, i) => (
                  <div key={i} style={{ marginTop: ".7rem" }}>
                    <div className="muted">{fmtDate(v.created_at)} — {v.subject}</div>
                    <div className="qtext">{v.text}</div>
                  </div>
                ))}
              </>
            )}
          </div>

          <div className="card">
            <h3>الإجراء</h3>
            <div className="row">
              {s === "submitted" && <button disabled={busy} onClick={() => act("start-review", undefined, "بدأت المراجعة")}>بدء المراجعة</button>}
              {(s === "submitted" || s === "under_review") && <>
                <button className="primary" disabled={busy} onClick={() => window.confirm("تأكيد السؤال بصيغته الحالية؟") && act("confirm", undefined, "أُكِّد السؤال")}>تأكيد</button>
                <button className="danger" disabled={busy} onClick={() => { setNote(""); setReturning(true); }}>إرجاع للنائب للتعديل</button>
              </>}
              {s === "returned" && <span className="muted">بانتظار تعديل النائب لسؤاله.</span>}
              {s === "confirmed" && <button className="primary" disabled={busy} onClick={() => window.confirm("إحالة السؤال إلى الجهاز التنفيذي (الوالي)؟") && act("refer", undefined, "أُحيل السؤال إلى الوالي")}>إحالة إلى الوالي</button>}
              {s === "answered" && <button className="primary" onClick={openReply}>عرض الرد الممسوح</button>}
            </div>
            {s === "referred" && (
              <div style={{ marginTop: ".5rem" }}>
                <p className="muted" style={{ marginTop: 0 }}>ارفع رد الجهاز التنفيذي الممسوح ضوئياً (PDF أو صورة، حتى 15 ميغابايت). سيُخطَر النائب فوراً.</p>
                <div className="row">
                  <input type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                  <button className="primary" disabled={!file || busy} onClick={sendReply}>{busy ? "جارٍ الرفع…" : "رفع الرد"}</button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <h3>مسار السؤال</h3>
          <ul className="timeline">
            {[...q.events].reverse().map((e, i) => (
              <li key={i}>
                <StatusBadge status={e.status} /> <span className="muted">{fmtDate(e.created_at)}</span>
                {e.note && <div>{e.note}</div>}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {returning && (
        <Modal title="إرجاع السؤال للنائب" onClose={() => setReturning(false)}>
          <p className="muted" style={{ marginTop: 0 }}>التعديل يقوم به النائب نفسه. اكتب له ما يلزم تعديله.</p>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} autoFocus placeholder="مثال: حدّد الطريق برقمه" />
          <div className="row" style={{ marginTop: ".8rem" }}>
            <button className="primary" disabled={busy || note.trim().length < 3}
              onClick={async () => { if (await act("return", { note: note.trim() }, "أُعيد السؤال للنائب")) setReturning(false); }}>
              إرجاع
            </button>
            <button onClick={() => setReturning(false)}>إلغاء</button>
          </div>
        </Modal>
      )}
    </>
  );
}
