export function authConfig() {
  const backendUrl = resolveBackendUrl();
  if (!backendUrl) {
    throw new Error(
      "BACKEND_URL, VERCEL_URL, or VERCEL_PROJECT_PRODUCTION_URL is required",
    );
  }

  return {
    backendUrl: backendUrl.replace(/\/$/, ""),
    cookieSecure: process.env.COOKIE_SECURE !== "false",
  };
}

function resolveBackendUrl(): string | undefined {
  const configured = process.env.BACKEND_URL?.trim();
  if (configured) return configured;

  const deploymentHost =
    process.env.VERCEL_URL?.trim() ||
    process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim();
  if (!deploymentHost) return undefined;
  return deploymentHost.includes("://")
    ? deploymentHost
    : `https://${deploymentHost}`;
}
