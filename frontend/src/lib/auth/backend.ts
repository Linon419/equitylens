import type { NextRequest } from "next/server";

import { authConfig } from "./config";
import { accessCookieName, refreshCookieName } from "./cookies";
import type { AuthTokens } from "./types";

export type BackendResult = {
  response: Response;
  rotatedTokens?: AuthTokens;
};

export function backendRequest(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");
  return fetch(`${authConfig().backendUrl}/api/v1${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

function withBearer(init: RequestInit, token: string): RequestInit {
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${token}`);
  return { ...init, headers };
}

function authRequiredResponse(): Response {
  return Response.json(
    { code: "AUTH_REQUIRED", request_id: "bff" },
    { status: 401 },
  );
}

export async function refreshFromRequest(
  request: NextRequest,
): Promise<Response> {
  const refreshToken = request.cookies.get(refreshCookieName)?.value;
  if (!refreshToken) {
    return authRequiredResponse();
  }
  return backendRequest("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function authenticatedBackendRequest(
  request: NextRequest,
  path: string,
  init: RequestInit = {},
): Promise<BackendResult> {
  const accessToken = request.cookies.get(accessCookieName)?.value;
  if (!accessToken) {
    return { response: authRequiredResponse() };
  }

  const first = await backendRequest(path, withBearer(init, accessToken));
  if (first.status !== 401) {
    return { response: first };
  }

  const refresh = await refreshFromRequest(request);
  if (!refresh.ok) {
    return { response: refresh };
  }
  const tokens = (await refresh.json()) as AuthTokens;
  const retry = await backendRequest(
    path,
    withBearer(init, tokens.access_token),
  );
  return { response: retry, rotatedTokens: tokens };
}
