import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { ROLE_AR } from "./ui";
import Login from "./pages/Login";
import { QuestionsList, QuestionDetail } from "./pages/Questions";
import Notifications from "./pages/Notifications";
import Deputies from "./pages/Deputies";
import Setup from "./pages/Setup";
import StaffPage from "./pages/StaffPage";
import Audit from "./pages/Audit";

export default function App() {
  const { role, username, logout } = useAuth();
  if (!role) return <Login />;
  const admin = role === "admin";
  const link = (to: string, text: string) => (
    <NavLink to={to} className={({ isActive }) => (isActive ? "active" : "")}>{text}</NavLink>
  );
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <strong>المجلس الشعبي الولائي</strong>
          <small>لوحة الديوان</small>
        </div>
        <nav>
          {link("/questions", "الأسئلة الكتابية")}
          {link("/notifications", "الإشعارات")}
          {admin && <>
            <div className="nav-sep">الإدارة</div>
            {link("/deputies", "النواب")}
            {link("/setup", "الدورة واللجان")}
            {link("/staff", "الموظفون")}
            {link("/audit", "سجل العمليات")}
          </>}
        </nav>
        <div className="me">
          <div><strong>{username}</strong><br /><small>{ROLE_AR[role]}</small></div>
          <button className="ghost" onClick={logout}>خروج</button>
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/questions" element={<QuestionsList />} />
          <Route path="/questions/:id" element={<QuestionDetail />} />
          <Route path="/notifications" element={<Notifications />} />
          {admin && <>
            <Route path="/deputies" element={<Deputies />} />
            <Route path="/setup" element={<Setup />} />
            <Route path="/staff" element={<StaffPage />} />
            <Route path="/audit" element={<Audit />} />
          </>}
          <Route path="*" element={<Navigate to="/questions" replace />} />
        </Routes>
      </main>
    </div>
  );
}
