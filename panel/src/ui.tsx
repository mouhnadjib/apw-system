import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "./api";
import type { NotifKind, QStatus, TargetType } from "./types";

export const STATUS_AR: Record<QStatus, string> = {
  submitted: "مُرسل",
  under_review: "قيد المراجعة",
  returned: "أُعيد للنائب",
  confirmed: "مؤكَّد",
  referred: "أُحيل إلى الوالي",
  answered: "تم الرد",
};
export const KIND_AR: Record<NotifKind, string> = {
  meeting: "دعوة اجتماع",
  targeted: "دعوة مخصصة",
  info: "معلومة مهمة",
};
export const TARGET_AR: Record<TargetType, string> = {
  all: "كل النواب",
  committees: "لجان",
  deputies: "نواب محددون",
};
export const ROLE_AR = { admin: "أدمن", operator: "الديوان (تسيير)" } as const;

export function parseDate(s: string): Date {
  // SQLite قد يُرجع تاريخاً بلا منطقة زمنية؛ نعتبره UTC
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s + "Z");
}
export function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  return parseDate(s).toLocaleString("ar-DZ-u-nu-latn", { dateStyle: "medium", timeStyle: "short" });
}

export function StatusBadge({ status }: { status: QStatus }) {
  return <span className={`badge st-${status}`}>{STATUS_AR[status]}</span>;
}

export function errMsg(e: unknown): string {
  return e instanceof ApiError ? e.message : "حدث خطأ غير متوقع";
}

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fnRef.current());
      setError("");
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { reload(); }, deps);
  return { data, error, loading, reload, setData };
}

export function Loading({ error, loading }: { error?: string; loading?: boolean }) {
  if (error) return <div className="alert err">{error}</div>;
  if (loading) return <div className="muted pad">جارٍ التحميل…</div>;
  return null;
}

export function Alert({ kind, children }: { kind: "err" | "ok"; children: ReactNode }) {
  return <div className={`alert ${kind}`} role={kind === "err" ? "alert" : "status"}>{children}</div>;
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal${wide ? " wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon" onClick={onClose} aria-label="إغلاق">×</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function Photo({ id, has, name, size = 44 }: { id: number; has: boolean; name: string; size?: number }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!has) { setUrl(null); return; }
    let revoked = false;
    let u = "";
    api.blob(`/staff/deputies/${id}/photo`).then((b) => {
      if (revoked) return;
      u = URL.createObjectURL(b);
      setUrl(u);
    }).catch(() => setUrl(null));
    return () => { revoked = true; if (u) URL.revokeObjectURL(u); };
  }, [id, has]);
  const style = { width: size, height: size, fontSize: size * 0.4 };
  return url
    ? <img className="avatar" style={style} src={url} alt={name} />
    : <span className="avatar ph" style={style} aria-hidden="true">{name.trim().charAt(0)}</span>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}

export function CheckList<T extends { id: number }>({ items, selected, onChange, label }: {
  items: T[]; selected: number[]; onChange: (ids: number[]) => void; label: (i: T) => string;
}) {
  const toggle = (id: number) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  if (!items.length) return <div className="muted">لا توجد عناصر</div>;
  return (
    <div className="checklist">
      {items.map((i) => (
        <label key={i.id} className="check">
          <input type="checkbox" checked={selected.includes(i.id)} onChange={() => toggle(i.id)} />
          <span>{label(i)}</span>
        </label>
      ))}
    </div>
  );
}
