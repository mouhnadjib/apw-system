import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import type { QuestionDetail } from "../types";

/** اسم الولاية كما يُكتب في الترويسة: «ولاية الجلفة» (تُضاف كلمة «ولاية» إن لم تكن موجودة). */
export function wilayaLine(name: string | null | undefined): string {
  const n = (name ?? "").trim();
  if (!n) return "";
  return n.startsWith("ولاية") ? n : `ولاية ${n}`;
}

/** النص الكامل للسؤال للنسخ إلى أي برنامج. */
export function questionPlainText(q: Pick<QuestionDetail, "subject" | "text" | "deputy_name">): string {
  return `الموضوع: ${q.subject}\n\n${q.text}${q.deputy_name ? `\n\nالنائب: ${q.deputy_name}` : ""}`;
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      return document.execCommand("copy");
    } finally {
      ta.remove();
    }
  }
}

/** ورقة الطباعة: مخفية على الشاشة، وتظهر وحدها عند الطباعة (انظر styles.css). */
export function PrintSheet({ q }: { q: QuestionDetail }) {
  const [wilaya, setWilaya] = useState("");
  useEffect(() => {
    api.get<{ wilaya_name: string | null }>("/public/info").then((i) => setWilaya(wilayaLine(i.wilaya_name))).catch(() => {});
  }, []);
  const year = new Date().getFullYear();
  return createPortal(
    <div className="print-sheet" dir="rtl">
      <div className="ps-republic">الجمهورية الجزائرية الديمقراطية الشعبية</div>
      <div className="ps-head">
        {wilaya && <div>{wilaya}</div>}
        <div>المجلس الشعبي الولائي</div>
      </div>
      <div className="ps-line">الرقم: ................... / {year}</div>
      <div className="ps-line"><strong>الموضوع:</strong> {q.subject}</div>
      <div className="ps-line">السند: ..............................................</div>
      <div className="ps-body">{q.text}</div>
      {q.deputy_name && <div className="ps-sign">النائب: {q.deputy_name}</div>}
    </div>,
    document.body
  );
}
