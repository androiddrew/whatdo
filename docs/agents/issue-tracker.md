# Issue tracker: Gitea

Issues and specs for this repo live as Gitea issues on the self-hosted
server at git.runcible.io (repo: `androiddrew/laya-server`). Use the `tea`
CLI for the common operations; fall back to the Gitea REST API (which is
GitHub-compatible) via curl for anything `tea` doesn't cover.

## Setup (one-time)

- Install `tea` (Gitea's official CLI): https://gitea.com/gitea/tea
- Run `tea login add` to store a login + personal access token for `git.runcible.io`.
- Run `tea` commands from inside the clone so it infers the repo, or pass
  `--repo androiddrew/laya-server --login <name>`.

## Conventions

- **Create an issue**: `tea issues create --title "..." --description "..."` (this `tea` uses `--description`/`-d`, not `--body`). For long/multi-line bodies write the markdown to a file and pass `--description-file <path>` (`-` for stdin).
- **List issues**: `tea issues list --state open --labels "..." --output simple` with appropriate `--state`/`--labels` filters.
- **Read an issue**: `tea issues <index>` (append `--comments` where your `tea` version supports it).
- **Comment on an issue**: `tea comment <index> "..."`
- **Close / reopen**: `tea issues close <index>` / `tea issues reopen <index>`
- **Apply / remove labels**: if your `tea` version lacks issue-label editing, use the Gitea REST API with a token:
  ```bash
  curl -H "Authorization: token $GITEA_TOKEN" -X POST \
    https://git.runcible.io/api/v1/repos/androiddrew/laya-server/issues/<index>/labels \
    -d '{"labels":["needs-triage"]}'
  ```
  (Use `DELETE .../issues/<index>/labels/<label-id>` to remove a label.)

Infer the repo from `git remote -v`; `tea` does this automatically when run inside a clone
with a configured login.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature
requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `tea pulls`
equivalents (`tea pulls list`, `tea pulls <index>`) and, where `tea` falls short, the Gitea
REST API under `.../api/v1/repos/androiddrew/laya-server/pulls`.

## When a skill says "publish to the issue tracker"

Create a Gitea issue.

## When a skill says "fetch the relevant ticket"

Run `tea issues <index>` (or `GET https://git.runcible.io/api/v1/repos/androiddrew/laya-server/issues/<index>`).

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. Create with `tea issues create --labels wayfinder:map`.
- **Child ticket**: an issue that references the map. Gitea has no native sub-issue graph, so add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, assign the ticket to the driving dev.
- **Blocking**: Gitea supports issue dependencies (repo `enable_issue_dependencies`, on by default). Add a "blocked by" edge in the UI or via `POST .../api/v1/repos/androiddrew/laya-server/issues/<child>/dependencies` with the full `IssueMeta` body `{"owner":"androiddrew","repo":"laya-server","index":<blocker>}` — note the field is `repo`, **not** `name`, and an `{"index":...}`-only body 404s. Verify/list edges with `GET .../issues/<child>/dependencies`. Otherwise fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`tea issues list --state open`, scoped to the map's task list), drop any with an open blocker or an assignee; first in map order wins.
- **Claim**: assign the issue to yourself (`tea issues edit <n> --assignees @me` where supported, else via the API), the session's first write.
- **Resolve**: `tea comment <n> "<answer>"`, then `tea issues close <n>`, then append a context pointer to the map's Decisions-so-far.
