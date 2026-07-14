import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const styles = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");

describe("supply-chain graph accessibility styles", () => {
  it("removes graph motion when the browser requests reduced motion", () => {
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styles).toContain(".supply-chain-toolbar input::after");
    expect(styles).toContain(".supply-chain-node.is-focus button { transition: none; }");
    expect(styles).toContain(".supply-chain-node.is-focus button { transform: none; }");
  });
});
