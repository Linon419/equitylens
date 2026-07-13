import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import {
  isLocale,
  localeCookieName,
  locales,
  resolveLocale,
} from "@/lib/i18n";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const pathLocale = pathname.split("/")[1] ?? "";

  if (isLocale(pathLocale)) {
    return NextResponse.next();
  }

  const locale = resolveLocale({
    cookieLocale: request.cookies.get(localeCookieName)?.value ?? null,
    acceptLanguage: request.headers.get("accept-language"),
  });
  const url = request.nextUrl.clone();
  url.pathname = pathname === "/" ? `/${locale}` : `/${locale}${pathname}`;

  const response = NextResponse.redirect(url);
  response.cookies.set(localeCookieName, locale, {
    maxAge: 60 * 60 * 24 * 365,
    path: "/",
    sameSite: "lax",
  });
  return response;
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\..*).*)",
  ],
};

export { locales };
