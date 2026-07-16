import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { accessCookieName } from "@/lib/auth/cookies";
import {
  isLocale,
  localeCookieName,
  locales,
  resolveLocale,
} from "@/lib/i18n";
import { createGuestIdentity, GUEST_COOKIE } from "@/lib/research/guest";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const pathLocale = pathname.split("/")[1] ?? "";

  if (isLocale(pathLocale)) {
    return withGuestIdentity(request, NextResponse.next());
  }

  const locale = resolveLocale({
    cookieLocale: request.cookies.get(localeCookieName)?.value ?? null,
    acceptLanguage: request.headers.get("accept-language"),
  });
  const url = request.nextUrl.clone();
  url.pathname =
    pathname === "/" ? `/${locale}/dashboard` : `/${locale}${pathname}`;

  const response = NextResponse.redirect(url);
  response.cookies.set(localeCookieName, locale, {
    maxAge: 60 * 60 * 24 * 365,
    path: "/",
    sameSite: "lax",
  });
  return withGuestIdentity(request, response);
}

async function withGuestIdentity(
  request: NextRequest,
  response: NextResponse,
): Promise<NextResponse> {
  if (request.cookies.has(accessCookieName)) return response;
  const identity = await createGuestIdentity({
    cookieValue: request.cookies.get(GUEST_COOKIE)?.value,
    forwardedFor: request.headers.get("x-forwarded-for") ?? undefined,
    realIp: request.headers.get("x-real-ip") ?? undefined,
    signingSecret: guestSigningSecret(),
  });
  if (identity.setCookie) {
    response.headers.append("set-cookie", identity.setCookie);
  }
  return response;
}

function guestSigningSecret(): string {
  const secret = process.env.GUEST_SIGNING_SECRET?.trim();
  if (!secret) throw new Error("GUEST_SIGNING_SECRET is required");
  return secret;
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\..*).*)",
  ],
};

export { locales };
