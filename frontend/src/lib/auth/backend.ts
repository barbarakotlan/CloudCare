import { ApiError, apiFetch } from "@/lib/api/client";
import type { LoginResponse, Role } from "@/lib/api/types";
import { clearSession, getToken, readSession, writeSession, type Session } from "./session";
import { AuthError, roleMismatchMessage, type AuthProvider } from "./types";

/** Default provider: Barbara's FastAPI `POST /auth/login` (JWT bearer). */
export const backendAuth: AuthProvider = {
  name: "backend",

  async login(email: string, password: string, role: Role): Promise<Session> {
    let res: LoginResponse;
    try {
      res = await apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        body: { email: email.trim(), password },
        auth: false,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        throw new AuthError("That email and password don't match. Check the demo credentials below.");
      }
      throw err;
    }
    if (res.user.role !== role) throw new AuthError(roleMismatchMessage(res.user.role));
    const session: Session = { token: res.access_token, user: { ...res.user, email: email.trim() } };
    writeSession(session);
    return session;
  },

  async logout() {
    clearSession();
  },

  getSession: readSession,
  getToken,
};
