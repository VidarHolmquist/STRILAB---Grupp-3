# Skill: `/push`

> Push changes to a new feature branch after passing full validation.
> You then merge the branch via a pull request or manual merge on GitHub.

> [!IMPORTANT]
> This skill does **not** push to `main` directly. It creates a feature branch,
> pushes there, and leaves merging to you. This protects `main` from unreviewed changes.

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
   - Flag any unexpected additions (`.venv/`, `__pycache__/`, database files,
     `metrics/evaluation_results.json`). Abort if any are present.

3. **Run full validation** _(hard gate — abort on failure)_
   ```bash
   python tests/validate_module.py --all
   ```
   - All modules must report `[PASS]` before proceeding.
   - If any module fails, fix the issue and re-run. Do **not** skip or bypass.

4. **Write a commit message**
   - Use conventional commit format: `<type>: <short summary>`.
   - Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`.
   - Keep the summary under 72 characters.
   - Examples: `feat: add sparse vector fallback`, `fix: correct BM25 avgdl edge case`

5. **Determine the branch name**
   - Use the pattern: `<type>/<short-summary-with-hyphens>`
   - Examples: `feat/sparse-vector-fallback`, `fix/bm25-avgdl-edge-case`
   - The branch name should match the commit message.

6. **Commit the staged changes** _(still on main at this point)_
   ```bash
   git commit -m "<type>: <short summary>"
   ```

7. **Create a feature branch from the current commit and push**
   ```bash
   git checkout -b <type>/<short-summary>
   git push -u origin <type>/<short-summary>
   ```

8. **Switch back to main**
   ```bash
   git checkout main
   ```

9. **Verify**
   ```bash
   git log --oneline -3
   git branch -a
   ```
   - Confirm the feature branch appears in `remotes/origin/`.
   - Confirm `main` is clean (no new commit on it — the commit lives on the feature branch).

> [!NOTE]
> After pushing, go to GitHub and open a pull request from `<type>/<short-summary>`
> into `main` to review and merge.

## Abort Conditions

- If `git diff --cached --stat` shows unexpected files, **stop and unstage them**.
- If validation (`python tests/validate_module.py --all`) fails, **stop and fix** before proceeding.
- If the `git push` fails (e.g., remote rejected), **stop and report**.
