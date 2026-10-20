import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, decodeToken, tokenStore } from "./api";
import type { Role } from "./types";

interface AuthCtx {
  role: Role | null;
  username: string;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}
const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(tokenStore.get());
  const [username, setUsername] = useState(tokenStore.user());
  const payload = decodeToken(token);
  const expired = payload.exp !== undefined && payload.exp * 1000 <= Date.now();

  const logout = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    setUsername("");
  }, []);

  useEffect(() => {
    const h = () => { setToken(null); setUsername(""); };
    window.addEventListener("apw-unauthorized", h);
    return () => window.removeEventListener("apw-unauthorized", h);
  }, []);

  // خروج تلقائي عند انتهاء صلاحية الرمز
  useEffect(() => {
    if (!payload.exp) return;
    const ms = payload.exp * 1000 - Date.now();
    if (ms <= 0) return logout();
    const id = window.setTimeout(logout, Math.min(ms, 2 ** 31 - 1));
    return () => window.clearTimeout(id);
  }, [payload.exp, logout]);

  const login = useCallback(async (u: string, p: string) => {
    const r = await api.post<{ access_token: string }>("/auth/staff/login", { username: u, password: p });
    tokenStore.set(r.access_token);
    tokenStore.setUser(u);
    setUsername(u);
    setToken(r.access_token);
  }, []);

  const value = useMemo<AuthCtx>(
    () => ({ role: token && !expired ? payload.role ?? null : null, username, login, logout }),
    [token, expired, payload.role, username, login, logout]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
