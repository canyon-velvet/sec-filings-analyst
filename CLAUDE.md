# sec-filings-analyst
Agentic RAG chat over any company's SEC filings, proven by evals on FinanceBench. Read `SPEC.md` first.

## Rules
- Keep PRs ≤ ~200 changed lines (excluding lockfiles and generated eval results). Split bigger work into stacked PRs.
- Never push to `main`; work on a branch and open a PR.
- Unit tests make no network calls; use the fakes in `tests/fakes/`.
- Update `SPEC.md` (checkboxes, decisions, progress log) in the same PR as the work.
- Keep `SPEC.md` under ~100 lines: one line per decision; longer rationale goes in `docs/adr/`.
- Never read or print `.env`; add new variables to `.env.example`.

## Workflow
- Design: use `/mattpocock-skills:codebase-design` for module interfaces and seams, and `/mattpocock-skills:domain-modeling` for terms and decisions (`GLOSSARY.md`, `docs/adr/`).
- `/to-spec` and `/to-tickets` only run when the user types them: when one is due, stop and tell the user exactly which one to run.
- Spec: the user runs `/mattpocock-skills:to-spec` → GitHub issue labelled `ready-for-agent`.
- Tickets: the user runs `/mattpocock-skills:to-tickets` → vertical-slice issues with blocking links, each one fitting a ≤200-line PR.
- Build with `/mattpocock-skills:tdd` whenever possible; confirm the seams with the user before writing the first test.
- Before every `git push`, run all three reviews against `origin/main` and fix what they find. Then write `git rev-parse HEAD` to `.git/claude-review-ok`.
  1. `/mattpocock-skills:code-review`: standards + spec
  2. `/code-review`: correctness bugs
  3. `/security-review`: security
- PR body: `/mattpocock-skills:pr`, with `Closes #<issue>`.

## Agent skills

### Issue tracker

GitHub Issues in canyon-velvet/sec-filings-analyst, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five labels (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/`. See `docs/agents/domain.md`.
