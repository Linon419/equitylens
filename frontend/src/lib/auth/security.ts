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
  const frontendUrl = process.env.FRONTEND_URL;
  if (!origin || !frontendUrl) {
    return false;
  }
  try {
    return new URL(origin).origin === new URL(frontendUrl).origin;
  } catch {
    return false;
  }
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
