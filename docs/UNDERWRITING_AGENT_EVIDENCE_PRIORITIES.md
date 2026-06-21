# Underwriting Agent Evidence And Priorities

Last updated: 2026-06-21.

## Scope

This project should remain a demo underwriting support system, not a broad
insurance decisioning platform. The near-term implementation target is an
evidence-backed referral workbench:

1. confirm whether the case is complete enough to review;
2. extract and normalize medical/exam facts;
3. detect deterministic rule hits, contradictions, and missing information;
4. surface ambiguous free-text findings for human review;
5. produce an auditable preliminary assessment with evidence references.

このプロジェクトは、広範な保険判断プラットフォームではなく、査定支援デモに留める。直近の実装対象は、根拠付きの回付支援ワークベンチである。

1. ケースがレビュー可能な状態か確認する。
2. 医療・健診 fact を抽出・正規化する。
3. 決定論的 rule hit、矛盾、不足情報を検出する。
4. 自由記述の曖昧 finding を人手確認項目として出す。
5. evidence 参照付きの preliminary assessment を返す。

## Evidence

| Source | Evidence | Implication For This Demo |
|---|---|---|
| Daido Life / Accenture patent announcement | AI provides a preliminary assessment from medical records and exam results, with key data points and visualization for underwriter review. | Emphasize extracted facts, cautionary points, and underwriter-facing review support. Do not represent the AI output as final underwriting. |
| Swiss Re Underwriting Assistant | The assistant works with automated underwriting engines, referral rule systems, manuals, multiple languages, and workbench integration. It organizes structured/unstructured applicant data and highlights gaps for expert review. | Keep deterministic rules as the backbone. Add agent findings for gaps and ambiguous text. Make outputs workbench-ready. |
| Pacific Life Re underwriting workflow | Rules engines can support straight-through processing for simple cases; remaining cases require evidence and human underwriter review. | Preserve `ELIGIBLE_CANDIDATE` for clean cases, and improve triage/referral quality for non-STP cases. |
| NAIC AI materials and model bulletin | Insurer AI use requires governance, transparency, testing, risk controls, and oversight, especially for regulated decision processes. | Implement traceable artifacts, regression tests, and explicit human-review disclaimers. Avoid autonomous decline or opaque LLM decisions. |
| Japan FSA AI Discussion Paper 1.1 | The FSA frames sound AI use in financial institutions as an area for constructive dialogue, risk management, and governance. | Keep the demo explainable and auditable, with data-quality and model-output guardrails. |

Sources:

- https://newsroom.accenture.sg/asia-pacific/news/2021/daido-life-insurance-company-granted-patent-for-ai-based-medical-underwriting-solution-developed-with-accenture
- https://www.swissre.com/reinsurance/life-and-health/solutions/magnumxp/underwriting-assistant.html
- https://www.swissre.com/risk-knowledge/advancing-societal-benefits-digitalisation/reimagining-life-insurance-underwriting.html
- https://www.pacificlifere.com/insights-articles/the-future-of-underwriting-is-now.html
- https://content.naic.org/insurance-topics/artificial-intelligence
- https://content.naic.org/sites/default/files/cmte-h-big-data-artificial-intelligence-wg-ai-model-bulletin.pdf.pdf
- https://www.fsa.go.jp/news/r7/sonota/20260303/aidp.html

## Priority Order

### P1: Evidence-Backed Referral Findings

Add `agent_findings` that detect ambiguous free text such as follow-up exams,
observation, doctor comments, planned retesting, and unspecified medication.
These findings may raise a clean case to `REFER_INFO_REQUEST` or add missing
information to an already referred case. They must not lower deterministic rule
outcomes.

`agent_findings` を追加し、「再検査予定」「経過観察中」「医師から指摘」「服薬名のみで病名不明」などの曖昧な自由記述を拾う。clean case は `REFER_INFO_REQUEST` に上げてもよいが、決定論 rule の outcome を下げてはいけない。

Why first:

- It addresses the current v2 gap called out in the implementation spec.
- It is visible in the demo without adding new external data sources.
- It matches real underwriting assistant value: focus the human underwriter on what to review.
- It can be regression-tested with fixtures.

### P2: Persisted Assessment Artifacts

Persist `canonical_facts`, `rule_result`, `agent_assessment`, `decision_result`,
and `execution_trace` as separate artifacts. This improves auditability and
debuggability without changing user-facing behavior.

`canonical_facts`, `rule_result`, `agent_assessment`, `decision_result`, `execution_trace` を個別 artifact として保存する。ユーザー向け挙動を広げずに、監査性とデバッグ性を上げる。

### P3: Workbench-Ready Report Shape

Make the report more usable for underwriters by grouping:

- deterministic rule hits;
- agent findings;
- contradictions;
- missing information;
- evidence by document/page;
- human-review lane.

査定者が読むレポートとして、rule hits、agent findings、contradictions、missing information、document/page evidence、人手回付レーンを整理する。

## Explicitly Out Of Scope For Now

- Pricing, premium calculation, or risk score calibration.
- Mortality/morbidity predictive modeling.
- External EHR/lab integrations.
- Autonomous approval or autonomous final decline.
- Broad multi-agent orchestration beyond the current MCP workflow.
- Production AI governance program implementation beyond demo traceability and tests.

## Implementation Guardrails

- Deterministic rules remain the only source of hard rule outcomes.
- Agent findings can only add concerns or recommended follow-up.
- Agent findings cannot remove rule hits, contradictions, or required information.
- Any finding must have at least one source: `field_path`, `free_text`, or `evidence_refs`.
- If a scenario override path is invalid, fail fast.
- If an expected artifact is missing, fail fast.
- Tests must prove both positive behavior and non-downgrade behavior.

