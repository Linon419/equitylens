import "@testing-library/jest-dom/vitest";
import { webcrypto } from "node:crypto";

Object.defineProperty(globalThis, "crypto", {
  configurable: true,
  value: webcrypto,
});

class TestResizeObserver implements ResizeObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  configurable: true,
  value: TestResizeObserver,
});

process.env.BACKEND_URL ??= "http://localhost:8000";
process.env.COOKIE_SECURE ??= "false";
process.env.FRONTEND_URL ??= "https://example.com";
process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ??= "test-client";
process.env.GUEST_SIGNING_SECRET ??=
  "guest-secret-with-at-least-32-characters";
