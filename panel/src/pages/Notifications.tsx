import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { Committee, Deputy, NotifKind, NotificationStaff, Receipt, TargetType } from "../types";
import { Alert, CheckList, Field, KIND_AR, Loading, Modal, TARGET_AR, errMsg, fmtDate, useLoad } from "../ui";

export default function Notifications() {
  const list = useLoad(() => api.get<NotificationStaff[]>("/staff/notifications"));
  const comm = useLoad(() => api.get<Committee[]>("/staff/committees"));
  const deps = useLoad(() => api.get<Deputy[]>("/staff/deputies"));

  const [kind, setKind] = useState<NotifKind>("info");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [meetingAt, setMeetingAt] = useState("");
  const [target, setTarget] = useState<TargetType>("all");
  const [cIds, setCIds] = useState<number[]>([]);
  const [dIds, setDIds] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "err" | "ok"; text: string } | null>(null);
  const [receipts, setReceipts] = useState<{ n: NotificationStaff; rows: Receipt[] } | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!window.confirm("إرسال الإشعار الآن؟ لا يمكن سحبه بعد الإرسال.")) return;
    setBusy(true);
    setMsg(null);
    try {
      const n = await api.post<NotificationStaff>("/staff/notifications", {
        kind, title: title.trim(), body: body.trim(),
        meeting_at: kind === "meeting" && meetingAt ? new Date(meetingAt).toISOString() : null,
        target_type: target,
        committee_ids: target === "committees" ? cIds : [],
        deputy_ids: target === "deputies" ? dIds : [],
      });
      setMsg({ kind: "ok", text: `أُرسل الإشعار إلى ${n.recipients} نائب` });
      setTitle(""); setBody(""); setMeetingAt(""); setCIds([]); setDIds([]);
      list.reload();
    } catch (x) {
      setMsg({ kind: "err", text: errMsg(x) });
    } finally {
      setBusy(false);
    }
  }

  async function showReceipts(n: NotificationStaff) {
    try {
      setReceipts({ n, rows: await api.get<Receipt[]>(`/staff/notifications/${n.id}/receipts`) });
    } catch (x) {
      setMsg({ kind: "err", text: errMsg(x) });
    }
  }

  const activeDeps = (deps.data ?? []).filter((d) => d.active);

  return (
    <>
      <div className="page-head"><h2>الإشعارات</h2></div>
      <div className="grid2" style={{ alignItems: "start" }}>
        <form className="card" onSubmit={submit}>
          <h3>إشعار جديد</h3>
          {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
          <Field label="النوع">
            <select value={kind} onChange={(e) => setKind(e.target.value as NotifKind)}>
              {(Object.keys(KIND_AR) as NotifKind[]).map((k) => <option key={k} value={k}>{KIND_AR[k]}</option>)}
            </select>
          </Field>
          <Field label="العنوان"><input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required minLength={2} /></Field>
          <Field label="النص"><textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={5000} required /></Field>
          {kind === "meeting" && (
            <Field label="موعد الاجتماع"><input type="datetime-local" value={meetingAt} onChange={(e) => setMeetingAt(e.target.value)} required /></Field>
          )}
          <Field label="المستلمون">
            <select value={target} onChange={(e) => setTarget(e.target.value as TargetType)}>
              {(Object.keys(TARGET_AR) as TargetType[]).map((t) => <option key={t} value={t}>{TARGET_AR[t]}</option>)}
            </select>
          </Field>
          {target === "committees" && (
            <CheckList items={comm.data ?? []} selected={cIds} onChange={setCIds} label={(c) => c.name} />
          )}
          {target === "deputies" && (
            <CheckList items={activeDeps} selected={dIds} onChange={setDIds} label={(d) => d.full_name} />
          )}
          <div style={{ marginTop: "1rem" }}>
            <button className="primary" disabled={busy ||
              (target === "committees" && !cIds.length) || (target === "deputies" && !dIds.length)}>
              {busy ? "جارٍ الإرسال…" : "إرسال"}
            </button>
          </div>
        </form>

        <div className="card" style={{ padding: 0 }}>
          <h3 style={{ padding: "1rem 1.25rem 0" }}>المرسَلة</h3>
          <Loading error={list.error} loading={list.loading && !list.data} />
          <div className="table-wrap">
            <table>
              <thead><tr><th>العنوان</th><th>النوع</th><th>القراءة</th><th></th></tr></thead>
              <tbody>
                {(list.data ?? []).map((n) => (
                  <tr key={n.id}>
                    <td>{n.title}<div className="muted" style={{ fontSize: ".8rem" }}>{fmtDate(n.created_at)} · {TARGET_AR[n.target_type]}</div></td>
                    <td>{KIND_AR[n.kind]}</td>
                    <td>{n.read}/{n.recipients}</td>
                    <td><button className="small" onClick={() => showReceipts(n)}>التفاصيل</button></td>
                  </tr>
                ))}
                {list.data && !list.data.length && <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: "1.5rem" }}>لم يُرسل أي إشعار بعد</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {receipts && (
        <Modal title={receipts.n.title} onClose={() => setReceipts(null)} wide>
          <p className="qtext">{receipts.n.body}</p>
          {receipts.n.meeting_at && <p>موعد الاجتماع: <strong>{fmtDate(receipts.n.meeting_at)}</strong></p>}
          <table>
            <thead><tr><th>النائب</th><th>القراءة</th></tr></thead>
            <tbody>
              {receipts.rows.map((r) => (
                <tr key={r.deputy_id}><td>{r.full_name}</td><td>{r.read_at ? `قرأ ${fmtDate(r.read_at)}` : <span className="muted">لم يقرأ بعد</span>}</td></tr>
              ))}
            </tbody>
          </table>
        </Modal>
      )}
    </>
  );
}
