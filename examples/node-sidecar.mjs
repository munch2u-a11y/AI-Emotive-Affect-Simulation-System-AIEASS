// Minimal Node.js client for the dependency-free JSONL sidecar.
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

const sidecar = spawn(
  "aieass",
  ["jsonl", "--state-dir", "./affect-state"],
  { stdio: ["pipe", "pipe", "inherit"] },
);

const lines = createInterface({ input: sidecar.stdout });
lines.on("line", (line) => {
  const response = JSON.parse(line);
  console.log("affect response", response);
  sidecar.stdin.end();
});

sidecar.stdin.write(
  JSON.stringify({
    id: "cycle-42",
    op: "step",
    mode: "event",
    session_id: "agent-1",
    event: "goal_progress",
    magnitude: 0.8,
    anchor_ids: ["plan-v3"],
  }) + "\n",
);
