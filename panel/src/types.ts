export type Role = "admin" | "operator";
export type QStatus = "submitted" | "under_review" | "returned" | "confirmed" | "referred" | "answered";
export type NotifKind = "meeting" | "targeted" | "info";
export type TargetType = "all" | "committees" | "deputies";

export interface Committee { id: number; mandate_id: number; name: string }
export interface Mandate { id: number; label: string; start_year: number; end_year: number; active: boolean }
export interface StaffUser { id: number; username: string; full_name: string; role: Role; active: boolean }
export interface Deputy {
  id: number; mandate_id: number; full_name: string; title: string | null; phone: string;
  active: boolean; has_photo: boolean; committees: Committee[];
}
export interface Invite { code: string; expires_at: string; note: string }

export interface NotificationStaff {
  id: number; kind: NotifKind; title: string; body: string; meeting_at: string | null;
  target_type: TargetType; created_at: string; recipients: number; read: number;
}
export interface Receipt { deputy_id: number; full_name: string; read_at: string | null }

export interface QuestionRow {
  id: number; subject: string; status: QStatus; created_at: string; updated_at: string;
  deputy_id: number | null; deputy_name: string | null;
}
export interface QEvent { status: QStatus; note: string | null; created_at: string }
export interface QVersion { subject: string; text: string; created_at: string }
export interface QuestionDetail extends QuestionRow {
  text: string; return_note: string | null; has_reply: boolean; events: QEvent[]; versions: QVersion[] | null;
}
export interface AuditRow {
  id: number; at: string; actor_type: string; actor_id: number | null;
  action: string; target: string | null; ip: string | null;
}
