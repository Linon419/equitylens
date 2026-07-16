export function authConfig() {
  const backendUrl = process.env.BACKEND_URL?.trim();
  if (!backendUrl) {
    throw new Error("BACKEND_URL is required");
  }

  return {
    backendUrl: backendUrl.replace(/\/$/, ""),
    cookieSecure: process.env.COOKIE_SECURE !== "false",
  };
}
