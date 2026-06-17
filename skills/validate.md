# Skill: `/validate`

> Validate the module(s) you just changed — checking syntax, imports, and interface
> contracts. This is a fast check (seconds) that catches obvious breakage before
> it propagates to other modules.

## When to Use

Run `/validate` any time you finish editing one or a small number of files and
want to confirm you have not broken the module's public interface.

## Steps

1. **Identify the changed file(s)**
   - Review the list of files modified in the current session.
   - If you changed more than one module, consider running `/validate-all` instead.

2. **Run validation for each changed file**
   ```bash
   python tests/validate_module.py <relative/path/to/file.py>
   ```
   Examples:
   ```bash
   python tests/validate_module.py backend/logic.py
   python tests/validate_module.py backend/database.py
   python tests/validate_module.py metrics/evaluate_rag.py
   ```

3. **Interpret results**
   Each file reports three checks:
   - **Syntax** — confirms the file can be compiled without errors.
   - **Import** — confirms the module loads without `ImportError`.
   - **Interface contract** — confirms expected classes, methods, and function
     signatures still exist (so other modules that depend on them will not break).

4. **Fix any failures before continuing**
   - If `[FAIL]` is reported on a contract check, the public interface has changed.
     Either revert the change or update the contract in `tests/validate_module.py`
     **and** update every other module that relies on the changed interface.
   - If `[FAIL]` is reported on syntax or import, fix the code error directly.

## Abort Conditions

- If validation fails and the failure cannot be immediately explained by an
  intentional, coordinated interface change, **stop and report**. Do not proceed
  to push.
