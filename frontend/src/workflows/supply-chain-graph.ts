const STEPS = [
  "collect",
  "extract",
  "resolve",
  "verify",
  "localize",
  "publish",
] as const;

type SupplyChainGraphStep = (typeof STEPS)[number];

export async function supplyChainGraphWorkflow(jobId: string) {
  "use workflow";

  for (const step of STEPS) {
    await runSupplyChainGraphStep(jobId, step);
  }
}

export async function runSupplyChainGraphStep(
  jobId: string,
  step: SupplyChainGraphStep,
) {
  "use step";

  const backendUrl = requiredEnv("BACKEND_URL").replace(/\/$/, "");
  const secret = requiredEnv("INTERNAL_JOB_SECRET");
  const response = await fetch(
    `${backendUrl}/api/v1/internal/jobs/${encodeURIComponent(jobId)}/supply-chain-graph/${step}`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${secret}`,
        "x-idempotency-key": `${jobId}:supply-chain-graph:${step}:v1`,
      },
    },
  );
  if (!response.ok) {
    throw new Error(`Backend graph step ${step} failed: ${response.status}`);
  }
}

function requiredEnv(name: "BACKEND_URL" | "INTERNAL_JOB_SECRET") {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}
