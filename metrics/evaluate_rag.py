import os
import json
import sys
import math
import re
import argparse

# Resolve paths dynamically to allow running from any directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.append(PROJECT_ROOT)

from backend import LocalBilingualRetriever

SOURCE_DOCS_DIR = os.path.join(PROJECT_ROOT, "source_docs")
TEST_CASES_FILE = os.path.join(PROJECT_ROOT, "rag_test_cases.json")
DEFAULT_EXPORT_FILE = os.path.join(PROJECT_ROOT, "evaluation_results.json")

def auto_ingest_if_empty(retriever: LocalBilingualRetriever, force: bool = False):
    """
    Checks if the Chroma DB is empty or if forced, and populates it
    by reading all txt files in source_docs.
    """
    if not force and not retriever.is_empty():
        print("[OK] Database is already populated. Skipping auto-ingest.")
        return
    
    print("[INFO] Initializing / Rebuilding database index...")
    retriever.clear_database()
    
    if not os.path.exists(SOURCE_DOCS_DIR):
        print(f"[ERROR] Source documents folder '{SOURCE_DOCS_DIR}' does not exist.")
        sys.exit(1)
        
    files = [f for f in os.listdir(SOURCE_DOCS_DIR) if f.endswith(".txt")]
    if not files:
        print(f"[ERROR] No text files found in '{SOURCE_DOCS_DIR}'.")
        sys.exit(1)
        
    print(f"Indexing {len(files)} documents from '{SOURCE_DOCS_DIR}'...")
    for fname in files:
        fpath = os.path.join(SOURCE_DOCS_DIR, fname)
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        retriever.chunk_and_add_document(text, fname)
    
    # Sync internal keyword lists after ingestion
    retriever._rebuild_keyword_index()
    print("[OK] Ingestion complete!")

def run_retrieval(retriever: LocalBilingualRetriever, query: str, mode: str, limit: int) -> list:
    """
    Executes retrieval using the requested mode: 'dense', 'sparse', or 'hybrid'.
    Returns a list of search hits.
    """
    if mode == "dense":
        return retriever.dense_search(query, limit=limit)
    elif mode == "sparse":
        return retriever.sparse_search(query, limit=limit)
    elif mode == "hybrid":
        return retriever.retrieve(query, limit=limit)
    else:
        raise ValueError(f"Unknown retrieval mode: {mode}")

def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing, removing punctuation, and collapsing whitespaces."""
    cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
    return " ".join(cleaned.split())

def check_snippet_containment(retrieved_texts: list[str], expected_snippet: str) -> bool:
    """
    Checks if the expected answer snippet (supporting ellipsis '...')
    is contained within the retrieved text chunks, ignoring punctuation differences.
    """
    if not expected_snippet:
        return True
    parts = [p.strip() for p in expected_snippet.split("...") if p.strip()]
    if not parts:
        return True
    
    normalized_retrieved = normalize_text(" ".join(retrieved_texts))
    normalized_parts = [normalize_text(part) for part in parts]
    
    return all(part in normalized_retrieved for part in normalized_parts)

def calculate_ap_at_k(retrieved_sources: list[str], ground_truth: list[str], k: int) -> float:
    """Calculates Average Precision at K (AP@K) for a single query, using de-duplicated source docs."""
    # De-duplicate retrieved source documents while preserving order
    unique_retrieved = []
    seen = set()
    for s in retrieved_sources:
        if s not in seen:
            unique_retrieved.append(s)
            seen.add(s)
            
    unique_retrieved_k = unique_retrieved[:k]
    
    hits = 0
    sum_precisions = 0.0
    for idx, doc in enumerate(unique_retrieved_k):
        if doc in ground_truth:
            hits += 1
            precision_at_idx = hits / (idx + 1)
            sum_precisions += precision_at_idx
            
    denominator = min(len(ground_truth), k)
    return sum_precisions / denominator if denominator > 0 else 0.0

def calculate_ndcg_at_k(retrieved_sources: list[str], ground_truth: list[str], k: int) -> float:
    """Calculates Normalized Discounted Cumulative Gain at K (NDCG@K) for a single query."""
    # De-duplicate retrieved source documents while preserving order
    unique_retrieved = []
    seen = set()
    for s in retrieved_sources:
        if s not in seen:
            unique_retrieved.append(s)
            seen.add(s)
            
    unique_retrieved_k = unique_retrieved[:k]
    
    dcg = 0.0
    for idx, doc in enumerate(unique_retrieved_k):
        if doc in ground_truth:
            dcg += 1.0 / math.log2(idx + 2)
            
    idcg = 0.0
    num_relevant = min(len(ground_truth), k)
    for idx in range(num_relevant):
        idcg += 1.0 / math.log2(idx + 2)
        
    return dcg / idcg if idcg > 0 else 0.0

def evaluate_mode(retriever: LocalBilingualRetriever, test_cases: list, mode: str, k_values: list[int]) -> dict:
    """
    Evaluates a specific retrieval mode over the test cases for specified values of K.
    Returns metrics and a list of detailed results.
    """
    max_k = max(k_values)
    results = []
    
    # Initialize metric accumulators
    hits = {k: 0 for k in k_values}
    rr_sum = {k: 0.0 for k in k_values}
    recall_sum = {k: 0.0 for k in k_values}
    ap_sum = {k: 0.0 for k in k_values}
    ndcg_sum = {k: 0.0 for k in k_values}
    containment_hits = {k: 0 for k in k_values}
    
    for case in test_cases:
        query = case["query"]
        ground_truth = case["ground_truth_doc"]
        expected_snippet = case.get("expected_answer_snippet", "")
        
        # Convert to list of basenames for uniform handling
        gt_docs = ground_truth if isinstance(ground_truth, list) else [ground_truth]
        gt_docs = [os.path.basename(doc) for doc in gt_docs]
        
        # Retrieve up to max_k candidates
        retrieved_hits = run_retrieval(retriever, query, mode, limit=max_k)
        retrieved_sources = [os.path.basename(h.get("source", "")) for h in retrieved_hits]
        
        # Find position/rank of the FIRST matching ground truth document
        first_rank = None
        for rank_idx, hit_src in enumerate(retrieved_sources):
            if hit_src in gt_docs:
                first_rank = rank_idx + 1  # 1-indexed rank
                break
        
        # Calculate case-level metrics for top-5 preview
        snippet_contained_5 = check_snippet_containment([h.get("text", "") for h in retrieved_hits[:5]], expected_snippet)
        
        # De-duped unique sources for recall/coverage metric at 5
        seen_5 = set()
        ret_sources_5 = []
        for s in retrieved_sources[:5]:
            if s not in seen_5:
                ret_sources_5.append(s)
                seen_5.add(s)
        recall_at_5 = len(seen_5.intersection(gt_docs)) / len(gt_docs)
        
        # Record results for this test case
        results.append({
            "case_id": case["id"],
            "query": query,
            "ground_truth": ground_truth,
            "rank": first_rank,
            "snippet_contained_at_5": snippet_contained_5,
            "recall_at_5": recall_at_5,
            "retrieved": [
                {
                    "source": os.path.basename(h.get("source", "")),
                    "score": h.get("score") if "score" in h else h.get("confidence"),
                    "text_snippet": h.get("text", "")[:120] + "..." if "text" in h else ""
                } for h in retrieved_hits
            ]
        })
        
        # Calculate metrics for each K
        for k in k_values:
            # 1. Classical Hit Rate & MRR (At least one doc found)
            if first_rank is not None and first_rank <= k:
                hits[k] += 1
                rr_sum[k] += 1.0 / first_rank
                
            # 2. Recall@K (What fraction of expected docs were found)
            ret_sources_k = {os.path.basename(h.get("source", "")) for h in retrieved_hits[:k]}
            intersect_count = len(ret_sources_k.intersection(gt_docs))
            recall_sum[k] += intersect_count / len(gt_docs)
            
            # 3. MAP@K & NDCG@K
            ap_sum[k] += calculate_ap_at_k(retrieved_sources, gt_docs, k)
            ndcg_sum[k] += calculate_ndcg_at_k(retrieved_sources, gt_docs, k)
            
            # 4. Snippet Containment
            retrieved_texts_k = [h.get("text", "") for h in retrieved_hits[:k]]
            if check_snippet_containment(retrieved_texts_k, expected_snippet):
                containment_hits[k] += 1
                
    total_cases = len(test_cases)
    metrics = {}
    for k in k_values:
        metrics[f"hit_rate@{k}"] = hits[k] / total_cases if total_cases > 0 else 0
        metrics[f"mrr@{k}"] = rr_sum[k] / total_cases if total_cases > 0 else 0
        metrics[f"recall@{k}"] = recall_sum[k] / total_cases if total_cases > 0 else 0
        metrics[f"map@{k}"] = ap_sum[k] / total_cases if total_cases > 0 else 0
        metrics[f"ndcg@{k}"] = ndcg_sum[k] / total_cases if total_cases > 0 else 0
        metrics[f"containment_rate@{k}"] = containment_hits[k] / total_cases if total_cases > 0 else 0
        
    return {
        "metrics": metrics,
        "detailed_results": results
    }

def print_comparison_table(all_metrics: dict, k_values: list[int]):
    """Prints a beautiful comparison table of all metrics."""
    print("\n" + "="*95)
    print("                     RAG RETRIEVAL COMPARISON REPORT")
    print("="*95)
    
    # Table 1: Classical Single-Doc & Multi-Doc Ranks
    print("1. SEARCH RANK QUALITY METRICS (Hit Rate, MRR, MAP, NDCG)")
    header1 = f"| {'Mode':<10} |"
    for k in k_values:
        header1 += f" HR@{k:<1}    |"
    for k in k_values:
        header1 += f" MRR@{k:<1}  |"
    for k in k_values:
        header1 += f" MAP@{k:<1}  |"
    for k in k_values:
        header1 += f" NDCG@{k:<1} |"
    print(header1)
    print("|" + "-"*12 + "|" + ("-"*9 + "|") * (4 * len(k_values)))
    
    for mode in ["dense", "sparse", "hybrid"]:
        metrics = all_metrics[mode]["metrics"]
        row = f"| {mode.capitalize():<10} |"
        for k in k_values:
            row += f" {metrics[f'hit_rate@{k}']*100:>5.1f}% |"
        for k in k_values:
            row += f" {metrics[f'mrr@{k}']:>6.3f} |"
        for k in k_values:
            row += f" {metrics[f'map@{k}']:>6.3f} |"
        for k in k_values:
            row += f" {metrics[f'ndcg@{k}']:>6.3f} |"
        print(row)
        
    print("="*95)
    
    # Table 2: Concept & Content Metrics
    print("\n2. CONCEPT & CONTENT METRICS (Multi-Doc Recall and Snippet Containment)")
    header2 = f"| {'Mode':<10} |"
    for k in k_values:
        header2 += f" Recall@{k:<1} |"
    for k in k_values:
        header2 += f" Cont@{k:<1}  |"
    print(header2)
    print("|" + "-"*12 + "|" + ("-"*11 + "|") * (2 * len(k_values)))
    
    for mode in ["dense", "sparse", "hybrid"]:
        metrics = all_metrics[mode]["metrics"]
        row = f"| {mode.capitalize():<10} |"
        for k in k_values:
            row += f" {metrics[f'recall@{k}']*100:>8.1f}% |"
        for k in k_values:
            row += f" {metrics[f'containment_rate@{k}']*100:>8.1f}% |"
        print(row)
        
    print("="*95)

def print_breakdowns(detailed_results: list, test_cases: dict, k_values: list[int]):
    """Prints breakdown of performance by language and query type (Hybrid mode)."""
    metadata = {c["id"]: c for c in test_cases}
    
    groups = {
        "Language": {},
        "Query Type": {}
    }
    
    for res in detailed_results:
        case_id = res["case_id"]
        meta = metadata[case_id]
        
        lang = meta["language"]
        qtype = meta["query_type"]
        rank = res["rank"]
        
        if lang not in groups["Language"]:
            groups["Language"][lang] = {"total": 0, "hits_at_k": {k: 0 for k in k_values}, "rr_sum_at_k": {k: 0.0 for k in k_values}}
        if qtype not in groups["Query Type"]:
            groups["Query Type"][qtype] = {"total": 0, "hits_at_k": {k: 0 for k in k_values}, "rr_sum_at_k": {k: 0.0 for k in k_values}}
            
        groups["Language"][lang]["total"] += 1
        groups["Query Type"][qtype]["total"] += 1
        
        for k in k_values:
            if rank is not None and rank <= k:
                groups["Language"][lang]["hits_at_k"][k] += 1
                groups["Language"][lang]["rr_sum_at_k"][k] += 1.0 / rank
                
                groups["Query Type"][qtype]["hits_at_k"][k] += 1
                groups["Query Type"][qtype]["rr_sum_at_k"][k] += 1.0 / rank

    print("\nHYBRID MODE BREAKDOWN")
    print("="*80)
    for cat_name, cat_data in groups.items():
        print(f"\n{cat_name} breakdown:")
        print(f"| {'Group':<15} | Count | HR@3     | MRR@3  | HR@5     | MRR@5  |")
        print("|" + "-"*17 + "|" + "-"*7 + "|" + ("-"*10 + "|") * 4)
        for group_key, data in cat_data.items():
            total = data["total"]
            hr3 = (data["hits_at_k"][3] / total * 100) if total > 0 else 0
            mrr3 = (data["rr_sum_at_k"][3] / total) if total > 0 else 0
            hr5 = (data["hits_at_k"][5] / total * 100) if total > 0 else 0
            mrr5 = (data["rr_sum_at_k"][5] / total) if total > 0 else 0
            print(f"| {group_key:<15} | {total:<5} | {hr3:>7.1f}% | {mrr3:>6.3f} | {hr5:>7.1f}% | {mrr5:>6.3f} |")
    print("="*80)

def print_failure_analysis(detailed_results: list, test_cases: list, fail_k: int):
    """Identifies and explains cases where retrieval failed under Hybrid mode."""
    metadata = {c["id"]: c for c in test_cases}
    failures = []
    
    for res in detailed_results:
        rank = res["rank"]
        if rank is None or rank > fail_k:
            failures.append(res)
            
    if not failures:
        print(f"\n[OK] PERFECT RETRIEVAL! Hybrid mode hit all targets inside top-{fail_k}.")
        return
        
    print(f"\nFAILURE ANALYSIS: Top-{fail_k} Misses (Count: {len(failures)})")
    print("="*80)
    for idx, fail in enumerate(failures):
        case_id = fail["case_id"]
        meta = metadata[case_id]
        print(f"{idx+1}. [TC ID: {case_id}] [Lang: {meta['language'].upper()}] [Type: {meta['query_type'].upper()}]")
        print(f"   Query:  \"{meta['query']}\"")
        print(f"   Target: {meta['ground_truth_doc']}")
        rank_val = fail["rank"]
        print(f"   Rank:   {'Not in top-k' if rank_val is None else f'Rank {rank_val}'}")
        
        print("   Retrieved list:")
        for r_idx, r in enumerate(fail["retrieved"][:3]):
            print(f"     [{r_idx+1}] {r['source']} (Score/Confidence: {r['score']})")
        print("-" * 50)
    print("="*80)

def main():
    parser = argparse.ArgumentParser(description="Evaluate Edmond RAG system retrieval accuracy.")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild ChromaDB index from source_docs.")
    parser.add_argument("--export", type=str, default=DEFAULT_EXPORT_FILE, help="Path to export detailed results.")
    args = parser.parse_args()
    
    # Initialize retriever pointing to the correct root db path
    print("[INFO] Initializing retriever and connecting to database...")
    db_path = os.path.join(PROJECT_ROOT, "local_chroma_db")
    retriever = LocalBilingualRetriever(db_path=db_path)
    
    # Self-heal or force-ingest database index
    auto_ingest_if_empty(retriever, force=args.rebuild)
    
    # Load test cases
    if not os.path.exists(TEST_CASES_FILE):
        print(f"[ERROR] Test cases file '{TEST_CASES_FILE}' not found.")
        sys.exit(1)
        
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
        
    print(f"[INFO] Loaded {len(test_cases)} test cases from '{TEST_CASES_FILE}'.")
    
    # Evaluate configurations
    k_values = [1, 3, 5]
    all_metrics = {}
    
    print("\nRunning retrieval evaluations...")
    for mode in ["dense", "sparse", "hybrid"]:
        sys.stdout.write(f"  Evaluating {mode.upper()} mode... ")
        sys.stdout.flush()
        all_metrics[mode] = evaluate_mode(retriever, test_cases, mode, k_values)
        sys.stdout.write("Done!\n")
        
    # Print reports
    print_comparison_table(all_metrics, k_values)
    print_breakdowns(all_metrics["hybrid"]["detailed_results"], test_cases, k_values)
    print_failure_analysis(all_metrics["hybrid"]["detailed_results"], test_cases, fail_k=3)
    
    # Save results to JSON
    export_data = {
        "summary": {mode: all_metrics[mode]["metrics"] for mode in all_metrics},
        "detailed": {mode: all_metrics[mode]["detailed_results"] for mode in all_metrics}
    }
    with open(args.export, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)
    print(f"\n[OK] Detailed results saved to '{args.export}'")

if __name__ == "__main__":
    main()
