# Skill: `/validate-all`

> Run validation across every tracked module in the codebase. Use this when many
> files have changed, before a push, or after a significant refactor.

## When to Use

- Before running `/push` (this is the gate check the push skill uses).
- After a refactor that touches multiple modules.
- When you are unsure which files were affected by a change.

## Steps

1. **Run full validation**
   ```bash
   python tests/validate_module.py --all
   ```

2. **Review the summary**
   The script prints a per-module `[PASS]` or `[FAIL]` summary at the end.
   Exit code `0` means all modules passed. Exit code `1` means at least one
   module failed.

3. **Fix any failures**
   - A `syntax` failure means a file has a Python syntax error — fix it directly.
   - An `import` failure means a module cannot be loaded — check for missing
     dependencies or broken relative imports.
   - A `contract` failure means an expected class, method, or function parameter
     is missing. Either:
     a. The change was unintentional — revert it.
     b. The change was intentional — update the contract in
        `tests/validate_module.py` AND fix every caller of the changed interface.

4. **Re-run until clean**
   ```bash
   python tests/validate_module.py --all
   ```
   Proceed only once exit code is `0` and the summary shows all `[PASS]`.

## Abort Conditions

- If any module fails and the root cause cannot be determined, **stop and report**
  before making further changes.
