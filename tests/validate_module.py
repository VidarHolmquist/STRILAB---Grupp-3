"""
validate_module.py

Validates one or all project modules for:
  1. Syntax correctness (py_compile)
  2. Import correctness (importlib)
  3. Interface contract (expected classes, methods, functions, and parameters)

Usage:
    python tests/validate_module.py backend/logic.py       # validate one file
    python tests/validate_module.py --all                  # validate all modules

Exit codes:
    0 - all checks passed
    1 - one or more checks failed
"""

import os
import sys
import argparse
import py_compile
import importlib
import importlib.util
import inspect

# ---------------------------------------------------------------------------
# Project root resolution — allows running from any directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Interface contracts
# Each key is a path relative to the project root.
# "classes"   -> dict of ClassName -> {"methods": [...], "init_params": [...]}
# "functions" -> dict of func_name -> {"params": [...]}
# ---------------------------------------------------------------------------
CONTRACTS: dict = {
    "backend/database.py": {
        "classes": {
            "QdrantDatabaseManager": {
                "methods": ["__init__", "is_empty", "get_all_points", "clear_database"],
                "init_params": ["self", "db_path", "collection_name"],
            },
            "QdrantCollectionWrapper": {
                "methods": ["__init__", "count"],
                "init_params": ["self", "client", "collection_name"],
            },
        },
    },
    "backend/logic.py": {
        "functions": {
            "tokenize_and_stem": {"params": ["text"]},
        },
        "classes": {
            "CustomBM25Vectorizer": {
                "methods": [
                    "fit",
                    "get_document_sparse_vector",
                    "get_query_sparse_vector",
                    "save",
                    "load",
                ],
            },
            "LocalBilingualRetriever": {
                "methods": [
                    "__init__",
                    "is_empty",
                    "retrieve",
                    "dense_search",
                    "sparse_search",
                    "hybrid_fuse",
                    "chunk_and_add_document",
                    "clear_database",
                ],
                "init_params": ["self", "db_path", "collection_name"],
            },
        },
    },
    "frontend/app.py": {
        "functions": {
            "highlight_query_terms": {"params": ["text", "query"]},
        },
    },
    "metrics/evaluate_rag.py": {
        "functions": {
            "run_retrieval": {"params": ["retriever", "query", "mode", "limit"]},
            "calculate_ap_at_k": {"params": ["retrieved_sources", "ground_truth", "k"]},
            "calculate_ndcg_at_k": {"params": ["retrieved_sources", "ground_truth", "k"]},
        },
    },
    "metrics/evaluate_generation.py": {
        "functions": {
            "calculate_faithfulness": {"params": ["generated_text", "retrieved_contexts"]},
            "calculate_requirement_adherence": {"params": ["generated_text", "requirements"]},
            "calculate_constraint_adherence": {
                "params": ["generated_text", "allowed_locations", "allowed_materials"]
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Helper: normalise path so callers can pass Windows or POSIX separators
# ---------------------------------------------------------------------------
def normalise_key(path: str) -> str:
    """Convert a file path to the forward-slash key used in CONTRACTS."""
    rel = os.path.relpath(path, PROJECT_ROOT)
    return rel.replace(os.sep, "/")


# ---------------------------------------------------------------------------
# Check 1: Syntax
# ---------------------------------------------------------------------------
def check_syntax(abs_path: str) -> tuple[bool, str]:
    try:
        py_compile.compile(abs_path, doraise=True)
        return True, "syntax OK"
    except py_compile.PyCompileError as exc:
        return False, f"syntax ERROR — {exc}"


# ---------------------------------------------------------------------------
# Check 2: Import
# ---------------------------------------------------------------------------
def check_import(abs_path: str, module_key: str) -> tuple[bool, str, object]:
    """
    Loads the module from its file path and returns (ok, message, module).
    frontend/app.py is excluded from import checking because Streamlit
    executes side-effects (st.set_page_config) at import time.
    """
    if module_key == "frontend/app.py":
        return True, "import SKIPPED (Streamlit entrypoint — side-effects at import)", None

    # Convert file path to a module name that won't clash with installed packages
    module_name = module_key.replace("/", ".").replace(".py", "").replace("\\", ".")

    try:
        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return True, "import OK", mod
    except ImportError as exc:
        return False, f"import ERROR — {exc}", None
    except Exception as exc:
        return False, f"import ERROR — {type(exc).__name__}: {exc}", None


# ---------------------------------------------------------------------------
# Check 3: Interface contract
# ---------------------------------------------------------------------------
def check_contract(mod, module_key: str) -> tuple[bool, list[str]]:
    """
    Verifies that expected classes, methods, and functions are present
    with the expected parameter names. Returns (all_ok, list_of_messages).
    """
    if mod is None:
        # Import was skipped — skip contract check too
        return True, ["contract SKIPPED"]

    contract = CONTRACTS.get(module_key)
    if contract is None:
        return True, ["no contract defined — skipping"]

    messages = []
    all_ok = True

    # --- Check free functions ---
    for func_name, spec in contract.get("functions", {}).items():
        obj = getattr(mod, func_name, None)
        if obj is None or not callable(obj):
            messages.append(f"  [FAIL] missing function '{func_name}'")
            all_ok = False
            continue

        expected_params = spec.get("params", [])
        if expected_params:
            try:
                sig = inspect.signature(obj)
                actual_params = list(sig.parameters.keys())
                missing = [p for p in expected_params if p not in actual_params]
                if missing:
                    messages.append(
                        f"  [FAIL] function '{func_name}' missing params: {missing} "
                        f"(got: {actual_params})"
                    )
                    all_ok = False
                else:
                    messages.append(f"  [OK]   function '{func_name}' — params OK")
            except (ValueError, TypeError) as exc:
                messages.append(f"  [WARN] could not inspect '{func_name}': {exc}")
        else:
            messages.append(f"  [OK]   function '{func_name}' — exists")

    # --- Check classes and their methods ---
    for class_name, class_spec in contract.get("classes", {}).items():
        cls = getattr(mod, class_name, None)
        if cls is None or not inspect.isclass(cls):
            messages.append(f"  [FAIL] missing class '{class_name}'")
            all_ok = False
            continue

        # Check methods exist
        for method_name in class_spec.get("methods", []):
            method = getattr(cls, method_name, None)
            if method is None:
                messages.append(f"  [FAIL] {class_name}.{method_name}() is missing")
                all_ok = False
            else:
                messages.append(f"  [OK]   {class_name}.{method_name}() — exists")

        # Check __init__ parameter names
        init_params = class_spec.get("init_params")
        if init_params:
            init_method = getattr(cls, "__init__", None)
            if init_method:
                try:
                    sig = inspect.signature(init_method)
                    actual_params = list(sig.parameters.keys())
                    missing = [p for p in init_params if p not in actual_params]
                    if missing:
                        messages.append(
                            f"  [FAIL] {class_name}.__init__() missing params: {missing} "
                            f"(got: {actual_params})"
                        )
                        all_ok = False
                    else:
                        messages.append(f"  [OK]   {class_name}.__init__() — params OK")
                except (ValueError, TypeError) as exc:
                    messages.append(
                        f"  [WARN] could not inspect {class_name}.__init__: {exc}"
                    )

    return all_ok, messages


# ---------------------------------------------------------------------------
# Validate one file
# ---------------------------------------------------------------------------
def validate_file(rel_path: str) -> bool:
    """
    Runs all three checks on a single file.
    Returns True if everything passed, False if any check failed.
    """
    module_key = normalise_key(rel_path)
    abs_path = os.path.join(PROJECT_ROOT, rel_path.replace("/", os.sep))

    if not os.path.isfile(abs_path):
        print(f"[ERROR] File not found: {abs_path}")
        return False

    print(f"\n--- {module_key} ---")

    # 1. Syntax
    ok_syn, msg_syn = check_syntax(abs_path)
    print(f"  [{'OK' if ok_syn else 'FAIL'}]   {msg_syn}")

    # 2. Import
    ok_imp, msg_imp, mod = check_import(abs_path, module_key)
    print(f"  [{'OK' if ok_imp else 'FAIL'}]   {msg_imp}")

    # 3. Contract
    ok_con, msgs_con = check_contract(mod, module_key)
    for m in msgs_con:
        print(m)

    file_ok = ok_syn and ok_imp and ok_con
    status = "PASS" if file_ok else "FAIL"
    print(f"  --> {status}")
    return file_ok


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Validate project modules for syntax, imports, and interface contracts."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to a single Python file to validate (relative to project root).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all modules defined in CONTRACTS.",
    )
    args = parser.parse_args()

    if not args.file and not args.all:
        parser.print_help()
        sys.exit(1)

    print("=" * 60)
    print("  MODULE VALIDATION REPORT")
    print("=" * 60)

    results = {}

    if args.all:
        for module_key in CONTRACTS:
            results[module_key] = validate_file(module_key)
    else:
        key = normalise_key(args.file)
        results[key] = validate_file(args.file)

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    all_passed = True
    for path, passed in results.items():
        label = "PASS" if passed else "FAIL"
        print(f"  [{label}]  {path}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n[OK] All validations passed.")
        sys.exit(0)
    else:
        print("\n[FAIL] One or more validations failed. Fix errors before pushing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
