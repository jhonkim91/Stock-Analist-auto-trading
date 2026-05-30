// 로컬 로그인 토큰 관리 (localStorage). 정적 export/SSR 안전하게 window 가드.

const TOKEN_KEY = "sa-auth-token";
const ID_KEY = "sa-auth-id";
export const UNAUTHORIZED_EVENT = "sa-unauthorized";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getUserId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ID_KEY);
  } catch {
    return null;
  }
}

export function setSession(token: string, id: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
    window.localStorage.setItem(ID_KEY, id);
  } catch {
    /* 저장 불가 환경 무시 */
  }
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(ID_KEY);
  } catch {
    /* 무시 */
  }
}

export function notifyUnauthorized(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
}
