import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/auth/backend";
import { csrfCookieName, setSessionCookies } from "@/lib/auth/cookies";
import { isSameOrigin, isValidCsrf } from "@/lib/auth/security";
import type { AuthResponse } from "@/lib/auth/types";
import { isLocale } from "@/lib/i18n";

function validationError() {
  return NextResponse.json(
    { code: "VALIDATION_ERROR", request_id: "bff" },
    { status: 400 },
  );
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (
    !body ||
    !isSameOrigin(request) ||
    !isValidCsrf(
      request.cookies.get(csrfCookieName)?.value ?? null,
      body.csrf_token,
    ) ||
    typeof body.credential !== "string" ||
    !isLocale(body.preferred_locale)
  ) {
    return validationError();
  }

  const backend = await backendRequest("/auth/google", {
    method: "POST",
    body: JSON.stringify({
      credential: body.credential,
      preferred_locale: body.preferred_locale,
    }),
  });
  const payload = await backend.json();
  if (!backend.ok) {
    return NextResponse.json(payload, { status: backend.status });
  }

  const auth = payload as AuthResponse;
  const response = NextResponse.json({ user: auth.user });
  setSessionCookies(response, auth);
  response.cookies.set(csrfCookieName, "", { maxAge: 0, path: "/" });
  return response;
}
