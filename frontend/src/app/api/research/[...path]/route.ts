import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import {
  accessCookieName,
  clearSessionCookies,
  setSessionCookies,
} from "@/lib/auth/cookies";
import { isSameOrigin } from "@/lib/auth/security";
import { researchBackendRequest } from "@/lib/research/backend";
import type { ResearchHttpMethod } from "@/lib/research/types";

const MAX_BODY_BYTES = 64 * 1_024;
const SYMBOL = "[A-Za-z][A-Za-z0-9.-]{0,9}";
const UUID = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const ALLOWED_REQUESTS: ReadonlyArray<[ResearchHttpMethod, RegExp]> = [
  ["GET", /^companies\/search$/],
  ["GET", new RegExp(`^companies\/${SYMBOL}$`)],
  ["GET", new RegExp(`^companies\/${SYMBOL}\/(market|financials|intelligence)$`)],
  ["GET", new RegExp(`^jobs\/${UUID}$`)],
  ["GET", /^agent-quota$/],
  ["GET", /^watchlist$/],
  ["POST", new RegExp(`^companies\/${SYMBOL}\/sync$`)],
  ["POST", new RegExp(`^jobs\/${UUID}\/retry$`)],
  ["POST", new RegExp(`^watchlist\/${SYMBOL}$`)],
  ["DELETE", new RegExp(`^watchlist\/${SYMBOL}$`)],
];

type RouteContext = { params: Promise<{ path: string[] }> };

export function isAllowedResearchRequest(method: string, path: string): boolean {
  const decoded = decodeResearchPath(path.split("/"));
  return (
    decoded !== null &&
    ALLOWED_REQUESTS.some(
      ([allowedMethod, pattern]) =>
        allowedMethod === method.toUpperCase() && pattern.test(decoded),
    )
  );
}

async function handleResearchRequest(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  const method = request.method.toUpperCase() as ResearchHttpMethod;
  const { path: rawSegments } = await context.params;
  const decodedPath = decodeResearchPath(rawSegments);
  if (
    decodedPath === null ||
    !isAllowedResearchRequest(method, decodedPath)
  ) {
    return errorResponse("RESEARCH_ROUTE_NOT_FOUND", 404);
  }
  if (method !== "GET" && !validMutationOrigin(request)) {
    return errorResponse("RESEARCH_ORIGIN_REQUIRED", 403);
  }

  const body = await readBoundedBody(request, method);
  if (body === null) return errorResponse("REQUEST_BODY_TOO_LARGE", 413);
  const encodedPath = decodedPath
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  try {
    const result = await researchBackendRequest(
      request,
      `${encodedPath}${request.nextUrl.search}`,
      { method, body },
    );
    const response = await copyUpstreamResponse(result.response);
    if (result.rotatedTokens) {
      setSessionCookies(response, result.rotatedTokens);
    }
    if (
      request.cookies.has(accessCookieName) &&
      [401, 403].includes(result.response.status)
    ) {
      clearSessionCookies(response);
    }
    if (result.guestCookie) {
      response.headers.append("set-cookie", result.guestCookie);
    }
    return response;
  } catch {
    return errorResponse("RESEARCH_UPSTREAM_UNAVAILABLE", 502);
  }
}

function decodeResearchPath(segments: string[]): string | null {
  try {
    const decoded = segments.map((segment) => decodeURIComponent(segment));
    if (
      decoded.length === 0 ||
      decoded.some(
        (segment) =>
          !segment ||
          segment === "." ||
          segment === ".." ||
          segment.includes("/") ||
          segment.includes("\\"),
      )
    ) {
      return null;
    }
    return decoded.join("/");
  } catch {
    return null;
  }
}

function validMutationOrigin(request: NextRequest): boolean {
  return (
    isSameOrigin(request) &&
    request.headers.get("sec-fetch-site") === "same-origin"
  );
}

async function readBoundedBody(
  request: NextRequest,
  method: ResearchHttpMethod,
): Promise<ArrayBuffer | undefined | null> {
  if (method === "GET") return undefined;
  const declaredLength = Number(request.headers.get("content-length") ?? 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    return null;
  }
  const body = await request.arrayBuffer();
  return body.byteLength > MAX_BODY_BYTES ? null : body;
}

async function copyUpstreamResponse(upstream: Response): Promise<NextResponse> {
  const headers = new Headers();
  for (const name of ["content-type", "retry-after"] as const) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  const body = [204, 205, 304].includes(upstream.status)
    ? null
    : await upstream.arrayBuffer();
  return new NextResponse(body, { status: upstream.status, headers });
}

function errorResponse(code: string, status: number): NextResponse {
  return NextResponse.json({ code, request_id: "bff" }, { status });
}

export const GET = handleResearchRequest;
export const POST = handleResearchRequest;
export const DELETE = handleResearchRequest;
