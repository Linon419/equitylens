import { randomBytes } from "node:crypto";
import { NextResponse } from "next/server";

import { authConfig } from "@/lib/auth/config";
import { csrfCookieName } from "@/lib/auth/cookies";

export async function GET() {
  const token = randomBytes(32).toString("base64url");
  const response = NextResponse.json({ token });
  response.cookies.set(csrfCookieName, token, {
    httpOnly: true,
    secure: authConfig().cookieSecure,
    sameSite: "strict",
    path: "/",
    maxAge: 600,
  });
  return response;
}
