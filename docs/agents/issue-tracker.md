# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues on `androiddrew/whatdo`.
Use the [`gh` CLI](https://cli.github.com/) for the common operations; fall back
to the GitHub REST API (`gh api`) for anything the porcelain commands don't cover.

## Setup (one-time)

- Install `gh` (GitHub's official CLI): https://cli.github.com/
- Run `gh auth login` to authenticate (stores a token in `~/.config/gh`).
- Run `gh` commands from inside the clone so it infers the repo, or pass
  `--repo androiddrew/whatdo`.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. For
  long/multi-line bodies write the markdown to a file and pass
  `--body-file <path>` (`-` for stdin).
- **List issues**: `gh issue list --state open --label "..."` with appropriate
  `--state`/`--label` filters.
- **Read an issue**: `gh issue view <number>` (append `--comments` to include the
  discussion).
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Close / reopen**: `gh issue close <number>` / `gh issue reopen <number>`
- **Apply / remove labels**: `gh issue edit <number> --add-label "needs-triage"`
  (`--remove-label` to remove). Labels must exist first; create them with
  `gh label create <name>`.

Infer the repo from `git remote -v`; `gh` does this automatically when run inside
a clone with a configured login.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature
requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the
`gh pr` equivalents (`gh pr list`, `gh pr view <number>`, `gh pr edit <number>
--add-label ...`).

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number>` (or `gh api repos/androiddrew/whatdo/issues/<number>`).

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. Create with `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue that references the map. Add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, assign the ticket to the driving dev. (GitHub has a native sub-issues feature; the task-list convention is the portable fallback used here.)
- **Blocking**: GitHub has no native issue-dependency graph — record blockers as a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's task list), drop any with an open blocker or an assignee; first in map order wins.
- **Claim**: assign the issue to yourself (`gh issue edit <n> --add-assignee @me`), the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer to the map's Decisions-so-far.
