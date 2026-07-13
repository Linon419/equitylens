import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/auth/backend";
import {
  clearSessionCookies,
  refreshCookieName,
} from "@/lib/auth/cookies";
import { isSameOrigin } from "@/lib/auth/security";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return NextResponse.json(
      { code: "VALIDATION_ERROR", request_id: "bff" },
      { status: 400 },
    );
  }

  const refreshToken = request.cookies.get(refreshCookieName)?.value;
  if (refreshToken) {
    try {
      await backendRequest("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // Local logout still removes browser credentials during backend outages.
    }
  }
  const response = new NextResponse(null, { status: 204 });
  clearSessionCookies(response);
  return response;
}
