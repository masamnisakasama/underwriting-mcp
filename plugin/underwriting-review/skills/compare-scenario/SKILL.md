---
name: compare-scenario
description: 完了済み査定結果に条件変更を当て、before/afterと変化したルールを比較する。
---

# Compare Scenario

Use the managed MCP server named `underwriting-decision`.

1. Identify the completed `job_id`. If it is unclear, ask the user for the job id.
2. Convert the user's requested changes into explicit `field` and `value` pairs.
3. Do not infer ambiguous values. Present a concrete change proposal when needed.
4. Call `simulate_underwriting_change`.
5. Show before, after, and changed rules as a table.
6. State that the original result was not modified.
