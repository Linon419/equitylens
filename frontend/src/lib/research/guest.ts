export const GUEST_COOKIE = "equitylens_guest";

const ASSERTION_LIFETIME_MS = 5 * 60 * 1_000;
const COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export interface GuestIdentity {
  guestId: string;
  assertionToken: string;
  assertion: { ipHash: string; expiresAt: string };
  setCookie?: string;
}

export async function signGuestCookie(
  guestId: string,
  secret: string,
): Promise<string> {
  validateUuid(guestId);
  return `${guestId}.${await hmacHex(secret, guestId)}`;
}

export async function verifyGuestCookie(
  value: string,
  secret: string,
): Promise<string | null> {
  const separator = value.lastIndexOf(".");
  if (separator < 0) return null;
  const guestId = value.slice(0, separator);
  const signature = value.slice(separator + 1);
  if (!UUID_PATTERN.test(guestId) || !isHexDigest(signature)) return null;
  return (await verifyHmacHex(secret, guestId, signature)) ? guestId : null;
}

export async function createGuestIdentity(input: {
  cookieValue?: string;
  forwardedFor?: string;
  realIp?: string;
  signingSecret: string;
  now?: Date;
}): Promise<GuestIdentity> {
  validateSecret(input.signingSecret);
  const now = input.now ?? new Date();
  const existingId = input.cookieValue
    ? await verifyGuestCookie(input.cookieValue, input.signingSecret)
    : null;
  const guestId = existingId ?? crypto.randomUUID();
  const ip = normalizedClientIp(input.forwardedFor, input.realIp);
  const usageDate = now.toISOString().slice(0, 10);
  const ipHash = await hmacHex(
    input.signingSecret,
    `${usageDate}:${ip}`,
  );
  const expiresAt = new Date(now.getTime() + ASSERTION_LIFETIME_MS);
  const payload = {
    guest_id: guestId,
    ip_hash: ipHash,
    issued_at: now.toISOString(),
    expires_at: expiresAt.toISOString(),
  };
  const encoded = base64UrlEncode(
    new TextEncoder().encode(JSON.stringify(payload)),
  );
  const assertionToken = `${encoded}.${await hmacHex(
    input.signingSecret,
    encoded,
  )}`;

  return {
    guestId,
    assertionToken,
    assertion: { ipHash, expiresAt: payload.expires_at },
    setCookie: existingId
      ? undefined
      : serializeGuestCookie(
          await signGuestCookie(guestId, input.signingSecret),
        ),
  };
}

function normalizedClientIp(forwardedFor?: string, realIp?: string): string {
  const candidate = forwardedFor?.split(",", 1)[0]?.trim() || realIp?.trim();
  if (!candidate) return "0.0.0.0";
  const withoutBrackets = candidate.replace(/^\[|\]$/g, "").toLowerCase();
  return withoutBrackets.startsWith("::ffff:")
    ? withoutBrackets.slice("::ffff:".length)
    : withoutBrackets;
}

function serializeGuestCookie(value: string): string {
  const secure = process.env.NODE_ENV === "production" ? "; Secure" : "";
  return `${GUEST_COOKIE}=${value}; Max-Age=${COOKIE_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax; Path=/${secure}`;
}

async function hmacHex(secret: string, value: string): Promise<string> {
  validateSecret(secret);
  const signature = await crypto.subtle.sign(
    "HMAC",
    await importHmacKey(secret),
    new TextEncoder().encode(value),
  );
  return bytesToHex(new Uint8Array(signature));
}

async function verifyHmacHex(
  secret: string,
  value: string,
  signature: string,
): Promise<boolean> {
  validateSecret(secret);
  try {
    return await crypto.subtle.verify(
      "HMAC",
      await importHmacKey(secret),
      hexToBytes(signature),
      new TextEncoder().encode(value),
    );
  } catch {
    return false;
  }
}

function importHmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

function base64UrlEncode(value: Uint8Array): string {
  let binary = "";
  for (const byte of value) binary += String.fromCharCode(byte);
  return btoa(binary)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
}

function bytesToHex(value: Uint8Array): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

function hexToBytes(value: string): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(value.length / 2);
  for (let index = 0; index < value.length; index += 2) {
    bytes[index / 2] = Number.parseInt(value.slice(index, index + 2), 16);
  }
  return bytes;
}

function isHexDigest(value: string): boolean {
  return /^[0-9a-f]{64}$/i.test(value);
}

function validateUuid(value: string): void {
  if (!UUID_PATTERN.test(value)) throw new Error("guest ID must be a UUID");
}

function validateSecret(value: string): void {
  if (value.length < 32) {
    throw new Error("GUEST_SIGNING_SECRET requires at least 32 characters");
  }
}
