import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authenticatedBackendRequest } from "@/lib/auth/backend";
import {
  clearSessionCookies,
  setSessionCookies,
} from "@/lib/auth/cookies";
import { isSameOrigin } from "@/lib/auth/security";
import { isLocale } from "@/lib/i18n";

export async function PATCH(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body || !isSameOrigin(request) || !isLocale(body.preferred_locale)) {
    return NextResponse.json(
      { code: "VALIDATION_ERROR", request_id: "bff" },
      { status: 400 },
    );
  }

  const result = await authenticatedBackendRequest(
    request,
    "/auth/me/preferences",
    {
      method: "PATCH",
      body: JSON.stringify({ preferred_locale: body.preferred_locale }),
    },
  );
  const payload = await result.response.json();
  const response = NextResponse.json(payload, {
    status: result.response.status,
  });
  if (result.rotatedTokens) {
    setSessionCookies(response, result.rotatedTokens);
  }
  if (result.response.status === 401 || result.response.status === 403) {
    clearSessionCookies(response);
  }
  return response;
}
