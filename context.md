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
- [initialisation](file:///d:/CODE/Edmond/STRILAB/initialisation): Environment setups and platform run scripts (`setup.py`, `requirements.txt`, `start.bat`, `start.sh`).


## Rules

### General

1. All Python code must target Python 3.9+.
2. Use normal, professional language in code, comments, documentation, and user interfaces; do not use edgy or overly militaristic language.
3. Do not use emojis in code, comments, documentation, or user interfaces.

### Style & Formatting
1. <!-- ADD RULE --> _Example: Use double quotes for strings._

### Architecture

1. <!-- ADD RULE --> _Example: Never add external API calls — the system must run fully offline._

### Security & Data

1. <!-- ADD RULE --> _Example: Never log or expose document contents to external services._

---

## Skills

> Skills are reusable, named workflows the AI assistant can execute.
> Each skill has a summary here and a linked file with detailed steps.

| Skill Name | Summary | Steps |
| :--------- | :------ | :---- |
| `/push` | Push to main after running checks (lint, test, clean commit message) | [push.md](skills/push.md) |

> To add a new skill, create a `[skillname].md` in the `skills/` folder
> and add a row to the table above.
