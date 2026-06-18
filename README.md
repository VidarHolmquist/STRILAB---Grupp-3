# Strilab Grupp 3 - Testplattform 


## System Architecture & Models

To run locally on a standard CPU without external API dependencies:

| Component | Model Name | Size | Purpose |
| :--- | :--- | :---: | :--- |
| **Bilingual Embedding** | `intfloat/multilingual-e5-small` | ~100 MB | Local embedding of multi-language docs |
| **Local LLM (Target)** | `qwen2.5-coder:7b` (via Ollama/Local) | ~4.7 GB | Target generator model for RAG expansion |

*Note: The local embedding model runs natively on CPU using the HuggingFace `sentence-transformers` library.*

---

##  Project Structure

* **`frontend/app.py`**: Flask-based UI to search, preview, and review documents.
* **`frontend/templates/`** and **`frontend/static/`**: HTML templates and static assets for the Flask UI.
* **`backend/retriever.py`**: Modular hybrid search implementation (E5 Dense Search + BM25 Sparse Search + RRF Fusion).
* **`metrics/`**: Evaluation suite.
  * `evaluate_rag.py`: Evaluates retrieval metrics (Hit Rate, MRR, Recall, NDCG, MAP).
  * `evaluate_generation.py`: Simulated metrics for RAG faithfulness and constraint adherence (generation not implemented yet)
* **`source_docs/`**: Directory containing target documents to index — **`.txt`** and **`.pdf`** are supported. `.pdf` text is extracted with `pypdf`, and `.pdf` previews render via a vendored copy of Mozilla's pdf.js viewer (`frontend/static/vendor/pdfjs/`) so search-and-highlight works consistently in every browser.
* **`rag_test_cases.json`**: Ground-truth dataset containing Swedish, English, and cross-lingual test queries.

---

## Technical Details & Quickstart

### Prerequisites
* Python 3.9+
* Git installed
* Internet access (for the initial automatic model download)

### Initializing the Repository
1. **Pull the code:**
   Clone the repository and navigate into the project directory:
   ```bash
   git clone https://github.com/VidarHolmquist/STRILAB---Grupp-3.git
   cd STRILAB---Grupp-3
   ```
2. **Start the application:**
   * **Windows:** Double-click `start.bat` in File Explorer, or run it in your terminal:
     ```cmd
     .\start.bat
     ```
   * **Linux / macOS:** Make the script executable and run it in your terminal:
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   *(This automatically sets up a `.venv` virtual environment, installs all required dependencies, and launches the Flask search UI at `http://localhost:5000`).*
3. **Index documents:**
   * Populate the `source_docs/` folder with documents in `.txt` or `.pdf` format (do not delete `.gitkeep`, as it is ignored by the engine but keeps the empty folder structure tracked in Git).
   * *Tip: If the folder contains no documents, the application will automatically generate sample `.txt` documents for testing.*
   * On the search page, click **Rebuild Database Index** to generate the vector and keyword database collections.
   * Click any search result to preview it in the pane on the right and jump straight to the matching passage:
     * `.pdf` previews render through the vendored pdf.js viewer and use its built-in search to scroll to and highlight the match — this works the same in every browser.
     * `.txt` previews use the browser's native [Text Fragments](https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Fragment/Text_fragments) (`#:~:text=`) to scroll to and highlight the match — supported in Chrome/Edge, not in Firefox/Safari (the file still opens fine there, just without the auto-scroll).
   * **Ladda ned** downloads the original file.

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

* **Pre-Retrieval Optimization**
  * **Query Rewriting / Expansion:** Use a lightweight LLM call to generate search variations or split complex queries into sub-queries.
  * **HyDE (Hypothetical Document Embeddings):** Embed LLM-generated hypothetical responses to improve semantic searches.
* **Post-Retrieval Filtering & Validation**
  * **Cross-Encoder Reranker:** Integrate `BAAI/bge-reranker` to re-score the top 25 results down to the best 3-5 before feed-forwarding.
  * **Validity Check / Grading Node:** Programmatic LLM grading to check if retrieved contexts contain the answer.
  * **Fallback Loops:** If context grades are low, trigger external search fallback or return a graceful "Information not found".
