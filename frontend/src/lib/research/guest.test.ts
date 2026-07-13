import { describe, expect, it } from "vitest";

import {
  createGuestIdentity,
  signGuestCookie,
  verifyGuestCookie,
} from "./guest";

const SECRET = "guest-secret-with-at-least-32-characters";
const GUEST_ID = "11111111-1111-4111-8111-111111111111";
const NOW = new Date("2026-07-13T00:00:00.000Z");

describe("guest identity", () => {
  it("round-trips a signed guest cookie", async () => {
    const cookie = await signGuestCookie(GUEST_ID, SECRET);

    await expect(verifyGuestCookie(cookie, SECRET)).resolves.toBe(GUEST_ID);
  });

  it("rejects a modified guest cookie", async () => {
    const cookie = await signGuestCookie(GUEST_ID, SECRET);

    await expect(verifyGuestCookie(`${cookie}x`, SECRET)).resolves.toBeNull();
  });

  it("creates a five-minute backend assertion with a daily IP hash", async () => {
    const identity = await createGuestIdentity({
      forwardedFor: "203.0.113.10, 10.0.0.1",
      signingSecret: SECRET,
      now: NOW,
    });

    expect(identity.guestId).toMatch(/^[0-9a-f-]{36}$/);
    expect(identity.assertion.expiresAt).toBe("2026-07-13T00:05:00.000Z");
    expect(identity.assertion.ipHash).toHaveLength(64);
    expect(identity.setCookie).toContain("HttpOnly");

    const [encoded] = identity.assertionToken.split(".");
    const payload = JSON.parse(
      new TextDecoder().decode(base64UrlDecode(encoded)),
    );
    expect(Object.keys(payload)).toEqual([
      "guest_id",
      "ip_hash",
      "issued_at",
      "expires_at",
    ]);
    expect(payload.guest_id).toBe(identity.guestId);
    expect(payload.ip_hash).toBe(identity.assertion.ipHash);
  });

  it("resumes a valid cookie without issuing another cookie", async () => {
    const cookieValue = await signGuestCookie(GUEST_ID, SECRET);

    const identity = await createGuestIdentity({
      cookieValue,
      realIp: "198.51.100.9",
      signingSecret: SECRET,
      now: NOW,
    });

    expect(identity.guestId).toBe(GUEST_ID);
    expect(identity.setCookie).toBeUndefined();
  });
});

function base64UrlDecode(value: string): Uint8Array {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return Uint8Array.from(atob(padded), (character) => character.charCodeAt(0));
}
