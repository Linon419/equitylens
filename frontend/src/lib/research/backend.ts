import type { NextRequest } from "next/server";

import { refreshFromRequest } from "@/lib/auth/backend";
import { authConfig } from "@/lib/auth/config";
import { accessCookieName } from "@/lib/auth/cookies";
import type { AuthTokens } from "@/lib/auth/types";
import { createGuestIdentity, GUEST_COOKIE } from "./guest";

export interface ResearchBackendResult {
  response: Response;
  rotatedTokens?: AuthTokens;
  guestCookie?: string;
}

export async function researchBackendRequest(
  request: NextRequest,
  path: string,
  init: Pick<RequestInit, "method" | "body"> = {},
): Promise<ResearchBackendResult> {
  const accessToken = request.cookies.get(accessCookieName)?.value;
  const headers = forwardedHeaders(request);
  const requestInit = {
    method: init.method ?? request.method,
    body: init.body,
    headers,
  } satisfies RequestInit;

  if (!accessToken) {
    const identity = await createGuestIdentity({
      cookieValue: request.cookies.get(GUEST_COOKIE)?.value,
      forwardedFor: request.headers.get("x-forwarded-for") ?? undefined,
      realIp: request.headers.get("x-real-ip") ?? undefined,
      signingSecret: guestSigningSecret(),
    });
    headers.set("x-guest-assertion", identity.assertionToken);
    return {
      response: await sendResearchRequest(path, requestInit),
      guestCookie: identity.setCookie,
    };
  }

  headers.set("authorization", `Bearer ${accessToken}`);
  const first = await sendResearchRequest(path, requestInit);
  if (first.status !== 401) return { response: first };

  const refresh = await refreshFromRequest(request);
  if (!refresh.ok) return { response: refresh };
  const tokens = (await refresh.json()) as AuthTokens;
  headers.set("authorization", `Bearer ${tokens.access_token}`);
  return {
    response: await sendResearchRequest(path, requestInit),
    rotatedTokens: tokens,
  };
}

function sendResearchRequest(path: string, init: RequestInit): Promise<Response> {
  return fetch(`${authConfig().backendUrl}/api/v1/${path}`, {
    ...init,
    cache: "no-store",
  });
}

function forwardedHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  for (const name of ["content-type", "accept-language"] as const) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

function guestSigningSecret(): string {
  const secret = process.env.GUEST_SIGNING_SECRET?.trim();
  if (!secret) throw new Error("GUEST_SIGNING_SECRET is required");
  return secret;
}
