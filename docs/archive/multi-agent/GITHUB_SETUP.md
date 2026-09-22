# Fork and Team Repository Setup

Replace every placeholder in angle brackets. Do not type the angle brackets.

## 1. Create the team fork

1. Sign in to GitHub and open the original Week 3 repository.
2. Select **Fork** in the upper-right corner.
3. Under **Owner**, choose the account or organization that will own the team
   fork.
4. Keep the repository name or use a clear team name.
5. Copy the default branch only unless the mentor told you that other upstream
   branches are required.
6. Select **Create fork**.

If the fork belongs to one member's personal account, that owner should open
**Settings → Collaborators** and invite the other two members with write access.
Never share one GitHub password among the team.

## 2. Clone the fork

On the fork, select **Code → HTTPS** and copy the URL. Open Git Bash in the
parent folder where you keep projects:

```bash
git clone https://github.com/<TEAM-OWNER>/<FORK-NAME>.git
cd <FORK-NAME>
```

`origin` now means the team's fork.

## 3. Configure the original repository as upstream

Copy the HTTPS URL from the original Week 3 repository, then run:

```bash
git remote add upstream https://github.com/<ORIGINAL-OWNER>/<ORIGINAL-REPOSITORY>.git
git remote -v
```

The result should show `origin` pointing to the team fork and `upstream`
pointing to the mentor's original repository.

## 4. Create the Tasks 1 and 2 branch

```bash
git switch -c salma/tasks-1-2
```

Keep the fork's `main` branch as the team's integrated version. Each team member
works on a separate branch.

## 5. Copy this ZIP into the cloned fork

1. Extract `Week3-Multi-Agent-Collaboration-Tasks1-2.zip` into a temporary
   folder.
2. Open the extracted `Week3-Multi-Agent-Collaboration` folder.
3. Copy **everything inside that folder**, including `.gitignore` and
   `.env.example`.
4. Paste it into the cloned fork folder containing `.git`.
5. Allow matching assignment scaffold files such as `README.md` to be replaced.
6. Do not copy the enclosing extracted folder itself into the repository.

The correct result has `README.md`, `src/`, `week3/`, `configs/`, `tests/`, and
`docs/` directly at the repository root. There should not be another
`Week3-Multi-Agent-Collaboration/` folder around them.

## 6. Inspect and test before committing

```bash
git status
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest tests/week3 -q
python -m week3.demo --mode fake
```

In Windows PowerShell, activation is:

```powershell
.\.venv\Scripts\Activate.ps1
```

Check `git status` again. `.env`, `.venv`, cache files, logs, and generated
outputs should remain untracked because `.gitignore` excludes them.

## 7. Commit and push

```bash
git add .
git status
git commit -m "Implement Week 3 directed graph and discussion orchestrator"
git push -u origin salma/tasks-1-2
```

Read the `git status` list before committing. It must not include `.env`, API
keys, passwords, database connection strings with real values, or generated
cache files.

## 8. Open the team pull request

On GitHub, open a pull request with:

- **Base repository:** the team's fork, not the original mentor repository.
- **Base branch:** `main`.
- **Head branch:** `salma/tasks-1-2`.

Suggested title:

```text
Implement Week 3 Tasks 1 and 2
```

Suggested description:

```text
This change adds the directed, strongly connected agent communication graph and
the discussion orchestration engine. It reuses the merged Week 2 personas and
agent runtime through a stable adapter, records initial opinions separately,
runs three fixed-snapshot discussion rounds, preserves routing and ordering
metadata, and logs execution events. The included fake demo runs without API
keys, and the Week 3 test suite verifies connectivity, routing visibility,
round scheduling, failure behavior, and the Week 2 adapter contract.

Validation:
- python -m pytest tests/week3 -q
- python -m week3.demo --mode fake
```

Ask one teammate to review it, then merge it into the fork's `main` branch.

## 9. Keep the fork synchronized

Before starting a later branch:

```bash
git switch main
git fetch upstream
git merge upstream/main
git push origin main
```

If Git reports a conflict, inspect and resolve it with the team. Do not use a
force push to erase teammates' work.
