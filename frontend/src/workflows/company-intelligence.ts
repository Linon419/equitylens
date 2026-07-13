const STEPS = [
  "download",
  "parse",
  "analyze",
  "verify",
  "localize",
] as const;

type CompanyIntelligenceStep = (typeof STEPS)[number];

export async function companyIntelligenceWorkflow(jobId: string) {
  "use workflow";

  for (const step of STEPS) {
    await runBackendStep(jobId, step);
  }
}

export async function runBackendStep(
  jobId: string,
  step: CompanyIntelligenceStep,
) {
  "use step";

  const backendUrl = requiredEnv("BACKEND_URL").replace(/\/$/, "");
  const secret = requiredEnv("INTERNAL_JOB_SECRET");
  const response = await fetch(
    `${backendUrl}/api/v1/internal/jobs/${encodeURIComponent(jobId)}/${step}`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${secret}`,
        "x-idempotency-key": `${jobId}:${step}:v1`,
      },
    },
  );
  if (!response.ok) {
    throw new Error(`Backend step ${step} failed: ${response.status}`);
  }
}

function requiredEnv(name: "BACKEND_URL" | "INTERNAL_JOB_SECRET") {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}
