import { timingSafeEqual } from "node:crypto";

import { NextResponse } from "next/server";
import { start } from "workflow/api";

import { companyIntelligenceWorkflow } from "@/workflows/company-intelligence";

export async function POST(request: Request) {
  const secret = process.env.INTERNAL_JOB_SECRET?.trim();
  const authorization = request.headers.get("authorization");
  if (!secret || !validBearerToken(authorization, secret)) {
    return NextResponse.json(
      { code: "INTERNAL_JOB_AUTH_REQUIRED" },
      { status: 401 },
    );
  }

  let payload: { job_id?: unknown };
  try {
    payload = (await request.json()) as { job_id?: unknown };
  } catch {
    return NextResponse.json({ code: "INVALID_JOB_PAYLOAD" }, { status: 400 });
  }
  const jobId = typeof payload.job_id === "string" ? payload.job_id.trim() : "";
  const idempotencyKey = request.headers.get("x-idempotency-key");
  if (!jobId || idempotencyKey !== jobId) {
    return NextResponse.json(
      { code: "INVALID_JOB_IDEMPOTENCY_KEY" },
      { status: 400 },
    );
  }

  const run = await start(companyIntelligenceWorkflow, [jobId]);
  return NextResponse.json({ run_id: run.runId }, { status: 202 });
}

function validBearerToken(value: string | null, expected: string) {
  if (!value?.startsWith("Bearer ")) {
    return false;
  }
  const supplied = Buffer.from(value.slice("Bearer ".length));
  const target = Buffer.from(expected);
  return supplied.length === target.length && timingSafeEqual(supplied, target);
}
