# Sample demo cases (Case A / B / C)

これらは **mock モード用の fixture**（§4 / §27-4）。

各ケース:

- `case.json` — ケースメタ（case_id, product_code, applicant_age, expected_documents, document_hashes）
- `canonical-facts.json` — 確定 canonical facts。**本来は Textract + Bedrock 抽出（§27-7,8, AWS 段階）で生成される**出力契約を、抽出未実装の段階でも end-to-end を回せるよう fixture 化したもの。
- `expected-result.json` — 期待される最終判定（integration test の基準）。

| Case | 年齢 | 主な所見 | 期待判定 |
|------|-----|---------|---------|
| case-a | 40 | 健康・全項目あり | `ELIGIBLE_CANDIDATE`（引受候補） |
| case-b | 52 | 高血圧 + 治療状況不明 + 告知/健診の矛盾 | `REFER`（要査定） |
| case-c | 75 | 加入上限超過 + 高血圧 + HbA1c高値 + 矛盾 | `NOT_ELIGIBLE_CANDIDATE`（引受不可候補） |

実 PDF（`scripts/generate_sample_pdfs.py`）は AWS Textract 段階（§27-7）で追加する。
それまでは canonical-facts.json が抽出結果の代替となる。
