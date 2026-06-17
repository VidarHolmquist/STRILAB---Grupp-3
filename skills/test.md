# Skill: `/test`

> Run the full retrieval and generation metric evaluation suite. This is a slower
> operation (minutes) that measures *how well* the system performs, not just whether
> it runs. Use it to detect quality regressions and to track retrieval metrics over time.

## When to Use

- After changes to the retrieval pipeline (`backend/logic.py`, `backend/database.py`).
- Before a release or after a significant tuning change (e.g., BM25 parameters,
  embedding model, chunking strategy).
- To compare retrieval modes (dense vs. sparse vs. hybrid).

> [!NOTE]
> Do **not** use `/test` as a pre-push gate — that role belongs to `/validate-all`.
> `/test` is for intentional quality measurement, not routine correctness checks.

## Steps

1. **Set PYTHONPATH** (if not already set)
   - Windows (PowerShell): `$env:PYTHONPATH = "."`
   - Linux / macOS: `export PYTHONPATH=.`

2. **Run retrieval evaluation**
   ```bash
   python metrics/evaluate_rag.py
   ```
   This script:
   - Auto-ingests documents from `./source_docs` if the database is empty.
   - Runs retrieval queries in **dense**, **sparse**, and **hybrid** modes.
   - Computes and prints: Hit Rate, MRR, MAP, NDCG, Recall, and Snippet Containment
     at K = 1, 3, 5.
   - Saves detailed results to `metrics/evaluation_results.json` (gitignored).

   To force a full database rebuild before evaluation:
   ```bash
   python metrics/evaluate_rag.py --rebuild
   ```

3. **Run generation evaluation**
   ```bash
   python metrics/evaluate_generation.py
   ```
   This script evaluates mock generator outputs against predefined scenarios and
   computes:
   - **Faithfulness** — how much of the generated text is grounded in retrieved context.
   - **Requirement Adherence** — whether required topics/protocols appear in the output.
   - **Constraint Adherence** — whether the output contains hallucinated locations or materials.

4. **Interpret and report results**
   - Report the summary table from `evaluate_rag.py` (Hit Rate, MRR, MAP, NDCG).
   - Flag any metric that has regressed compared to the previous run in
     `metrics/evaluation_results.json`.
   - For generation evaluation, flag any scenario where constraint violations were found.

## Key Metrics Reference

| Metric | What it measures |
| :----- | :--------------- |
| Hit Rate@K | Fraction of queries where the correct document appears in top-K results |
| MRR@K | Mean Reciprocal Rank — rewards finding the right doc early |
| MAP@K | Mean Average Precision — rewards consistent high-ranking of correct docs |
| NDCG@K | Normalized Discounted Cumulative Gain — position-weighted ranking quality |
| Recall@K | Fraction of all relevant docs retrieved in top-K |
| Containment@K | Fraction of queries where the expected answer snippet appears in top-K results |

## Abort Conditions

- If `evaluate_rag.py` fails with an import or database error, run `/validate-all`
  first to ensure the codebase is intact, then run `/initialise` to check the
  database setup.
