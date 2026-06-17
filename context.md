# Edmond — Context

> This file is the root context for AI assistants working on this codebase.
> It describes what the project is, how the code is organized, and provides
> rules and skills that must be followed during development.

## Project Overview

**Edmond** is a bilingual (English + Swedish) hybrid search engine for military
training documents. It runs fully offline on a standard CPU with no external API
dependencies.

| Stack Layer        | Technology                                      |
| :----------------- | :---------------------------------------------- |
| UI                 | Streamlit (`frontend/app.py`)                   |
| Retrieval Engine   | Custom hybrid retriever (`backend/logic.py`, `backend/database.py`) |
| Dense Embeddings   | `intfloat/multilingual-e5-small` via `sentence-transformers` |
| Sparse Search      | Custom BM25 vectorizer with bilingual stemming  |
| Vector Database    | Qdrant (local file-backed, `./local_qdrant_db`) |
| Evaluation         | Custom metric scripts (`metrics/`)              |

## Folder Context Map

- [frontend](file:///d:/CODE/Edmond/STRILAB/frontend): Web UI dashboard built with Streamlit.
- [backend](file:///d:/CODE/Edmond/STRILAB/backend): Retrieval engine and database integrations.
  - [backend/database.py](file:///d:/CODE/Edmond/STRILAB/backend/database.py): Connection and point scroll/upsert/delete wrappers for local Qdrant collection.
  - [backend/logic.py](file:///d:/CODE/Edmond/STRILAB/backend/logic.py): Bilingual stemming, BM25 vectorizer calculation, and search fusion coordination.
- [metrics](file:///d:/CODE/Edmond/STRILAB/metrics): Evaluation scripts, test cases ([rag_test_cases.json](file:///d:/CODE/Edmond/STRILAB/metrics/rag_test_cases.json)), and metrics outputs.
- [tests](file:///d:/CODE/Edmond/STRILAB/tests): Fast validation scripts that check syntax, imports, and interface contracts for each module.
  - [tests/validate_module.py](file:///d:/CODE/Edmond/STRILAB/tests/validate_module.py): Validates one or all modules; exits 0 on pass, 1 on failure.
- [requirements.txt](file:///d:/CODE/Edmond/STRILAB/requirements.txt): Python dependency specifications.


## Rules

### General
1. All Python code must target Python 3.9+.
2. Suggest creating skills for repeated workflows
3. Update context.md when new skills are created


### Style & Formatting
1. Do not use emojis in code, comments, documentation, or user interfaces.
2. Use normal, professional language in code, comments, documentation, and user interfaces; do not use edgy or overly militaristic language.
3. Code should be modular and easy to understand

### Architecture

1. <!-- ADD RULE --> _Example: Never add external API calls — the system must run fully offline._

### Security & Data

1. <!-- ADD RULE --> _Example: Never log or expose document contents to external services._

---

## Skills

| Skill Name | Summary | Steps |
| :--------- | :------ | :---- |
| `/initialise` | Initialise the repository, configure virtual environment, and install dependencies | [initialise.md](skills/initialise.md) |
| `/validate` | Validate changed module(s) — syntax, imports, and interface contracts (fast) | [validate.md](skills/validate.md) |
| `/validate-all` | Full-codebase validation across all tracked modules (fast) | [validate-all.md](skills/validate-all.md) |
| `/test` | Run the full retrieval and generation metric evaluation suite (slow) | [test.md](skills/test.md) |
| `/push` | Run `/validate-all`, commit, and push to a new feature branch for review | [push.md](skills/push.md) |

> To add a new skill, create a `[skillname].md` in the `skills/` folder
> and add a row to the table above.
