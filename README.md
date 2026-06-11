# Strilab Grupp 3 - Testplattform 


## System Architecture & Models

To run Edmond locally on a standard CPU without external API dependencies:

| Component | Model Name | Size | Purpose |
| :--- | :--- | :---: | :--- |
| **Bilingual Embedding** | `intfloat/multilingual-e5-small` | ~100 MB | Local embedding of multi-language docs |
| **Local LLM (Target)** | `qwen2.5-coder:7b` (via Ollama/Local) | ~4.7 GB | Target generator model for RAG expansion |

*Note: The local embedding model runs natively on CPU using the HuggingFace `sentence-transformers` library.*

---

##  Project Structure

* **`app.py`**: Streamlit-based UI to search, preview, and review documents.
* **`retriever.py`**: Modular hybrid search implementation (E5 Dense Search + BM25 Sparse Search + RRF Fusion).
* **`metrics/`**: Evaluation suite.
  * `evaluate_rag.py`: Evaluates retrieval metrics (Hit Rate, MRR, Recall, NDCG, MAP).
  * `evaluate_generation.py`: Simulated metrics for RAG faithfulness and constraint adherence (generation not implemented yet)
* **`source_docs/`**: Directory containing target **`.txt`** documents to index.
* **`rag_test_cases.json`**: Ground-truth dataset containing Swedish, English, and cross-lingual test queries.

---

## Technical Details & Quickstart

### Prerequisites
* Python 3.9+
* Git installed
* Internet access (for the initial automatic model download)

### Initializing the Repository
1. **Pull the code:**
   ```bash
   git fetch origin
   git checkout <branch-or-pr-name>
   ```
2. **Start the application:**
   * **Windows:** Double-click or run `start.bat` in your terminal.
   * **Linux / macOS:** Run `start.sh` in your terminal.
   *(This automatically sets up a `.venv` virtual environment, installs dependencies, and launches the UI).*
3. **Index documents:**
   * Populate the `source_docs/` folder with text documents (e.g., files from `synthetic_data` or *övningsplaner*, obs: needs to be `.txt`).
   * Open the Streamlit admin panel sidebar and click **Rebuild Database Index** to generate vector and keyword databases.

### Running Evaluations
* **To evaluate retrieval performance:**
  ```bash
  python metrics/evaluate_rag.py
  ```
* **To run generation checks:**
  ```bash
  python metrics/evaluate_generation.py
  ```

---

## Evaluation Protocols & Baseline Results

The testing scripts reside in the `metrics/` folder and calculate metrics against the `rag_test_cases.json` suite.

### Glossary
* **Sparse (BM25):** Exact keyword overlap matching.
* **Hybrid:** Combines keyword and dense semantic vector search.
* **HR@1 (Hit Rate @ 1):** Did the system retrieve the correct document as the absolute first result?
* **MRR@5 (Mean Reciprocal Rank @ 5):** Evaluates rank placement; how high up in the top-5 list the target document appears.
* **Recall@5:** The percentage of ground-truth documents retrieved inside the top-5 results.

### Baseline Results
*(Evaluated using hybrid retrieval, no document metadata filtering, and baseline document chunking)*

| Metric | Score |
| :--- | :---: |
| Sparse (BM25) HR@1 | 74.3% |
| Sparse (BM25) MRR@5 | 0.772 |
| Hybrid HR@1 | 74.3% |
| Hybrid MRR@5 | 0.801 |
| Hybrid Recall@5 | 85.7% |

---

## Initial Retrieval Roadmap & Implementation Stages

### Advanced RAG Extensions
*Goal: Optimize precision, handle complex queries, and eliminate hallucinations.*

* **Stage 1: Pre-Retrieval Optimization**
  * **Query Rewriting / Expansion:** Use a lightweight LLM call to generate search variations or split complex queries into sub-queries.
  * **HyDE (Hypothetical Document Embeddings):** Embed LLM-generated hypothetical responses to improve semantic searches.
* **Stage 2: Post-Retrieval Filtering & Validation**
  * **Cross-Encoder Reranker:** Integrate `BAAI/bge-reranker` to re-score the top 25 results down to the best 3-5 before feed-forwarding.
  * **Validity Check / Grading Node:** Programmatic LLM grading to check if retrieved contexts contain the answer.
  * **Fallback Loops:** If context grades are low, trigger external search fallback or return a graceful "Information not found".
