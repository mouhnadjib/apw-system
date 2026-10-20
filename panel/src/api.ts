import type { Role } from "./types";

const KEY = "apw_token";
const USER_KEY = "apw_user";

export const tokenStore = {
  get: () => sessionStorage.getItem(KEY),
  set: (t: string) => sessionStorage.setItem(KEY, t),
  clear: () => {
    sessionStorage.removeItem(KEY);
    sessionStorage.removeItem(USER_KEY);
  },
  setUser: (u: string) => sessionStorage.setItem(USER_KEY, u),
  user: () => sessionStorage.getItem(USER_KEY) ?? "",
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const FIELD_AR: Record<string, string> = {
  username: "اسم المستخدم", password: "كلمة المرور", full_name: "الاسم", phone: "الهاتف", title: "العنوان",
  body: "النص", subject: "الموضوع", text: "نص السؤال", note: "الملاحظة", label: "التسمية", name: "الاسم",
  start_year: "سنة البداية", end_year: "سنة النهاية", meeting_at: "موعد الاجتماع",
};

function messageFrom(status: number, data: any): string {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const custom = d.map((e) => (typeof e?.msg === "string" && /[؀-ۿ]/.test(e.msg) ? e.msg.replace(/^Value error, /, "") : "")).filter(Boolean);
    if (custom.length) return custom.join("، ");
    const fields = d.map((e) => FIELD_AR[String(e?.loc?.at(-1))] ?? String(e?.loc?.at(-1) ?? "")).filter(Boolean);
    return `بيانات غير صالحة${fields.length ? ": " + [...new Set(fields)].join("، ") : ""}`;
  }
  if (status === 413) return "الملف كبير جداً";
  if (status >= 500) return "خطأ داخلي في الخادم";
  return "تعذّر تنفيذ العملية";
}

async function raw(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  const t = tokenStore.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "تعذّر الاتصال بالخادم");
  }
  if (res.status === 401 && t && !path.startsWith("/auth/")) {
    tokenStore.clear();
    window.dispatchEvent(new Event("apw-unauthorized"));
  }
  if (!res.ok) {
    let data: unknown;
    try { data = await res.json(); } catch { /* غير JSON */ }
    throw new ApiError(res.status, messageFrom(res.status, data));
  }
  return res;
}

async function json<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await raw(method, path, body);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  get: <T>(p: string) => json<T>("GET", p),
  post: <T>(p: string, b?: unknown) => json<T>("POST", p, b),
  patch: <T>(p: string, b?: unknown) => json<T>("PATCH", p, b),
  put: <T>(p: string, b?: unknown) => json<T>("PUT", p, b),
  blob: async (p: string) => (await raw("GET", p)).blob(),
};

export function decodeToken(t: string | null): { role?: Role; exp?: number } {
  if (!t) return {};
  try {
    const p = t.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(p));
  } catch {
    return {};
  }
}
