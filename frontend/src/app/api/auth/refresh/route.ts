import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { refreshFromRequest } from "@/lib/auth/backend";
import {
  clearSessionCookies,
  setSessionCookies,
} from "@/lib/auth/cookies";
import { isSameOrigin } from "@/lib/auth/security";
import type { AuthTokens } from "@/lib/auth/types";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return NextResponse.json(
      { code: "VALIDATION_ERROR", request_id: "bff" },
      { status: 400 },
    );
  }

  const backend = await refreshFromRequest(request);
  const payload = await backend.json();
  const response = NextResponse.json(payload, { status: backend.status });
  if (backend.ok) {
    setSessionCookies(response, payload as AuthTokens);
  }
  if (!backend.ok && backend.status !== 409) {
    clearSessionCookies(response);
  }
  return response;
}
