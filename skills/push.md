# Skill: `/push`

> Push changes to `main` after passing through all required checks.

## Steps

1. **Stage changes**
   ```bash
   git add -A
   ```

2. **Review diff**
   ```bash
   git diff --cached --stat
   ```
   - Confirm the changed files are intentional.
   - Flag any unexpected additions (e.g., `.venv/`, `__pycache__/`, database files).

3. **Run linter** _(if configured)_
   ```bash
   # ADD LINT COMMAND HERE — e.g.: ruff check . --fix
   ```
   - Fix any lint errors before proceeding.

4. **Run tests** _(if configured)_
   ```bash
   # ADD TEST COMMAND HERE — e.g.: python -m pytest tests/
   ```
   - All tests must pass before committing.

5. **Commit with a clean message**
   ```bash
   git commit -m "<type>: <short summary>"
   ```
   - Use conventional commit types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`.
   - Keep the summary under 72 characters.

6. **Pull latest from remote**
   ```bash
   git pull --rebase origin main
   ```
   - Resolve any merge conflicts if they arise.

7. **Push**
   ```bash
   git push origin main
   ```

8. **Verify**
   - Confirm the push succeeded with `git log --oneline -3`.

## Abort Conditions

- If lint fails and cannot be auto-fixed, **stop and report**.
- If tests fail, **stop and report** the failing test(s).
- If rebase produces conflicts, **stop and report** the conflicting files.
