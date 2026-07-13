import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authenticatedBackendRequest } from "@/lib/auth/backend";
import {
  clearSessionCookies,
  setSessionCookies,
} from "@/lib/auth/cookies";

export async function GET(request: NextRequest) {
  const result = await authenticatedBackendRequest(request, "/auth/me");
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
