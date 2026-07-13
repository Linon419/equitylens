import type { NextResponse } from "next/server";

import { authConfig } from "./config";
import type { AuthTokens } from "./types";

export const accessCookieName = "equitylens_access";
export const refreshCookieName = "equitylens_refresh";
export const csrfCookieName = "equitylens_auth_csrf";

function commonCookieOptions() {
  return {
    httpOnly: true,
    secure: authConfig().cookieSecure,
    sameSite: "lax" as const,
    path: "/",
  };
}

export function setSessionCookies(
  response: NextResponse,
  tokens: AuthTokens,
): void {
  const common = commonCookieOptions();
  response.cookies.set(accessCookieName, tokens.access_token, {
    ...common,
    maxAge: tokens.access_expires_in,
  });
  response.cookies.set(refreshCookieName, tokens.refresh_token, {
    ...common,
    maxAge: tokens.refresh_expires_in,
  });
}

export function clearSessionCookies(response: NextResponse): void {
  const common = commonCookieOptions();
  response.cookies.set(accessCookieName, "", { ...common, maxAge: 0 });
  response.cookies.set(refreshCookieName, "", { ...common, maxAge: 0 });
}
