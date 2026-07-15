export async function filingIndexWorkflow(jobId: string) {
  "use workflow";

  await runFilingIndexStep(jobId);
}

export async function runFilingIndexStep(jobId: string) {
  "use step";

  const backendUrl = requiredEnv("BACKEND_URL").replace(/\/$/, "");
  const secret = requiredEnv("INTERNAL_JOB_SECRET");
  const response = await fetch(
    `${backendUrl}/api/v1/internal/jobs/${encodeURIComponent(jobId)}/filing-index`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${secret}`,
        "x-idempotency-key": `${jobId}:filing-index:v1`,
      },
    },
  );
  if (!response.ok) {
    throw new Error(`Backend filing-index step failed: ${response.status}`);
  }
}

function requiredEnv(name: "BACKEND_URL" | "INTERNAL_JOB_SECRET") {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}
