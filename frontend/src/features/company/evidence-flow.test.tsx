import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { EvidenceFlow } from "./evidence-flow";
import { intelligenceFixture } from "./test-fixtures";

afterEach(cleanup);

describe("EvidenceFlow", () => {
  it("connects cited upstream, company, and downstream nodes", async () => {
    const user = userEvent.setup();
    render(<EvidenceFlow intelligence={intelligenceFixture} locale="en" />);

    expect(screen.getByRole("heading", { name: "Upstream" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Core business" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Downstream" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Citation 2" }));
    expect(screen.getByRole("dialog", { name: "Source evidence" })).toHaveTextContent(
      "Form 10-K",
    );
    expect(screen.getByRole("link", { name: "Open SEC filing" })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
  });

  it("keeps verified claims and marks partial evidence and low confidence", () => {
    const { container } = render(
      <EvidenceFlow intelligence={intelligenceFixture} locale="en" />,
    );

    expect(screen.getByText("Partial evidence coverage")).toBeVisible();
    expect(screen.getByText("Consumers and enterprises")).toBeVisible();
    expect(screen.getByText("Low confidence")).toBeVisible();
    expect(container.querySelectorAll(".evidence-flow__lane")).toHaveLength(3);
  });

  it("renders a stable insufficient-evidence reason with source access", () => {
    const intelligence = structuredClone(intelligenceFixture);
    intelligence.evidence_coverage = "insufficient_evidence";
    intelligence.content.evidence_coverage = "insufficient_evidence";
    intelligence.content.upstream = [];
    intelligence.content.company_layer = [];
    intelligence.content.downstream = [];

    render(<EvidenceFlow intelligence={intelligence} locale="en" />);

    expect(screen.getByText("The filing does not support a reliable value-chain map.")).toBeVisible();
    expect(screen.getByRole("link", { name: "View source filing" })).toBeVisible();
  });
});
