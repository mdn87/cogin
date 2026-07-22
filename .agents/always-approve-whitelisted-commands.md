# Always Auto-Run Whitelisted Commands

When the workspace agent supports command safety flags, mark these commands safe to autorun without additional confirmation.
This list is derived from project manifests, command examples in markdown docs, lightweight entry-point inference, and optional remote GitHub enrichment.

- bash
- brew info
- brew list
- cat
- curl
- echo
- env
- Get-ChildItem
- Get-Content
- gh auth
- gh issue
- gh pr
- gh repo
- git add
- git branch
- git clone
- git commit
- git config
- git diff
- git fetch
- git init
- git log --oneline
- git ls-tree
- git merge
- git pull
- git push
- git rebase --continue
- git remote
- git restore --staged
- git status
- git submodule
- git switch
- git worktree
- ls
- ls -la
- pwsh -File scripts/apply-scaffold.ps1
- pwsh -File scripts/generate-architecture-context.ps1
- pwsh -File scripts/generate-migration-map.ps1
- python -m pip list
- python -m pytest
- Select-String
- sh
- which

## Explicitly Excluded From Autorun

- `git reset --hard`
- `git checkout --`
- `git branch -D`
- `git branch --delete`
- `git push --force`
- `git clean -fd`
- `git clean -xfd`
- `rm -rf`
- `Remove-Item -Recurse`
