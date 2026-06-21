# demo-medical-2026-01

**架空のデモ用引受ルールセット**。実在保険会社の引受基準ではない（§23 非スコープ）。

- `rules.yaml` — ルール定義（DSL, §12.3）
- `metadata.json` — version / product_code / disclaimer

## ルール一覧

| id | priority | 条件（要約） | result |
|----|----------|-------------|--------|
| DEMO-UW-001 | 100 | 年齢 > 70 | `NOT_ELIGIBLE_CANDIDATE` |
| DEMO-UW-002 | 95 | 年齢 < 20 | `NOT_ELIGIBLE_CANDIDATE` |
| DEMO-UW-030 | 60 | 告知/健診の矛盾あり | `REFER` |
| DEMO-UW-017 | 50 | 高血圧(≥160/100) かつ 治療状況不明 | `REFER` |
| DEMO-UW-018 | 45 | HbA1c ≥ 6.5 | `REFER` |

## 判定優先順位（§12.4）

`NOT_ELIGIBLE_CANDIDATE > REFER > ELIGIBLE_CANDIDATE`。

加えて、ルール結果に関わらず以下の場合は強制的に `REFER` 以上へ倒す（決定論ガード）:
必須文書不足 / 重要項目不足 / 重要項目 confidence < 0.75 / 未解決の矛盾 /
構造化抽出の検証失敗 / 根拠(evidence)の無い重要項目の使用。

**最終 recommendation は LLM ではなく決定論ルールエンジンが決める。**
