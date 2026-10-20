import { api } from "../api";
import type { AuditRow } from "../types";
import { Loading, fmtDate, useLoad } from "../ui";

const ACTION_AR: Record<string, string> = {
  login: "دخول موظف", login_failed: "محاولة دخول فاشلة", login_locked: "قفل حساب بعد محاولات فاشلة",
  device_bound: "تفعيل جهاز نائب", invite_revoked_attempts: "إلغاء رمز دعوة (محاولات خاطئة)",
  staff_created: "إنشاء حساب موظف", staff_updated: "تعديل حساب موظف",
  mandate_created: "إنشاء دورة", settings_updated: "تعديل اسم الولاية", committee_created: "إنشاء لجنة",
  deputy_created: "إضافة نائب", deputy_updated: "تعديل نائب", deputy_photo: "تغيير صورة نائب",
  invite_created: "إنشاء رمز دعوة", device_reset: "فصل جهاز نائب",
  notification_sent: "إرسال إشعار", question_created: "سؤال جديد", question_edited: "تعديل سؤال من النائب",
  question_start_review: "بدء مراجعة سؤال", question_return: "إرجاع سؤال للنائب", question_confirm: "تأكيد سؤال",
  question_refer: "إحالة سؤال إلى الوالي", question_reply: "رفع رد ممسوح",
};
const ACTOR_AR: Record<string, string> = { staff: "موظف", deputy: "نائب" };

export default function Audit() {
  const { data, error, loading, reload } = useLoad(() => api.get<AuditRow[]>("/admin/audit?limit=300"));
  return (
    <>
      <div className="page-head"><h2>سجل العمليات</h2><button onClick={reload}>تحديث</button></div>
      <Loading error={error} loading={loading && !data} />
      {data && (
        <div className="card table-wrap" style={{ padding: 0 }}>
          <table>
            <thead><tr><th>الوقت</th><th>الفاعل</th><th>العملية</th><th>الهدف</th><th>العنوان</th></tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id}>
                  <td>{fmtDate(r.at)}</td>
                  <td>{ACTOR_AR[r.actor_type] ?? r.actor_type} {r.actor_id ?? ""}</td>
                  <td>{ACTION_AR[r.action] ?? r.action}</td>
                  <td dir="ltr" style={{ textAlign: "right" }}>{r.target ?? "—"}</td>
                  <td dir="ltr" style={{ textAlign: "right" }}>{r.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
