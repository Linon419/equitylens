import { timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";

const internalOrigin = "https://equitylens.local";

export function safeReturnPath(value: unknown, fallback: string): string {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//")
  ) {
    return fallback;
  }

  try {
    const parsed = new URL(value, internalOrigin);
    return parsed.origin === internalOrigin
      ? `${parsed.pathname}${parsed.search}${parsed.hash}`
      : fallback;
  } catch {
    return fallback;
  }
}

export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) {
    return false;
  }
  try {
    const suppliedOrigin = new URL(origin).origin;
    return expectedOrigins(request).some(
      (expectedOrigin) => expectedOrigin === suppliedOrigin,
    );
  } catch {
    return false;
  }
}

function expectedOrigins(request: NextRequest): string[] {
  const origins = new Set<string>();
  const configured = process.env.FRONTEND_URL?.trim();
  if (configured) {
    origins.add(new URL(configured).origin);
  }

  const host = firstHeaderValue(request.headers.get("x-forwarded-host"))
    ?? firstHeaderValue(request.headers.get("host"));
  if (host) {
    const forwardedProtocol = firstHeaderValue(
      request.headers.get("x-forwarded-proto"),
    );
    const protocol = forwardedProtocol === "http" || forwardedProtocol === "https"
      ? forwardedProtocol
      : request.nextUrl.protocol.replace(":", "");
    origins.add(`${protocol}://${host}`);
  }

  origins.add(request.nextUrl.origin);
  return [...origins];
}

function firstHeaderValue(value: string | null): string | null {
  return value?.split(",", 1)[0]?.trim() || null;
}

export function isValidCsrf(
  cookieValue: string | null,
  bodyValue: unknown,
): boolean {
  if (!cookieValue || typeof bodyValue !== "string") {
    return false;
  }
  const left = Buffer.from(cookieValue);
  const right = Buffer.from(bodyValue);
  return left.length === right.length && timingSafeEqual(left, right);
}
