# cogin

This project was initialized with the shared scaffold.

## Structure

- `docs/` for architecture notes and decisions
- `src/` for implementation code
- `tests/` for automated tests

## Working Agreement

- Keep documentation close to the codebase.
- Prefer small, reviewable changes.
- Fill out `docs/project-brief.md` and `docs/architecture.md` before locking in stack-specific tooling.
- Add stack-specific setup once the project direction is confirmed.

## Git Lanes

This project follows the git "lanes" convention. Branches:

- default branch (usually `main`) — trunk
- `lane/<slug>` — work branches (or `lane/<agent>/<slug>` when an agent created it)
- `safety/YYYY-MM-DD-<topic>` — snapshots before risky changes

See `.scaffold/rules/git-lanes.md` for the full convention and
`.scaffold/skills/lane-workflow.md` for how to use `bash .scaffold/tools/lane.sh`.

