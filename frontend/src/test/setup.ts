import "@testing-library/jest-dom/vitest";

process.env.BACKEND_URL ??= "http://localhost:8000";
process.env.COOKIE_SECURE ??= "false";
process.env.FRONTEND_URL ??= "https://example.com";
process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ??= "test-client";
