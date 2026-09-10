# Contributing to CAMCO Coordinator

This is CAMCO Manufacturing's internal coordination tool (see
[LICENSE](LICENSE) - proprietary, all rights reserved). This guide is for
anyone with write access working on it.

## Getting set up

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m app.main
```

See [README.md](README.md) for what the first launch does, and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the codebase is laid
out before touching anything - `app/business` and `app/repositories` hold
the rules and queries; `app/ui` should stay thin and call into them rather
than re-implementing logic inline.

## Branch and PR workflow

`main` is protected: no direct pushes, force-pushes, or deletions - every
change goes through a pull request.

```bash
git checkout -b type/short-description   # e.g. fix/po-late-days, feat/rma-export
# ... make changes ...
git push -u origin type/short-description
gh pr create
```

CI (`.github/workflows/tests.yml`) runs `ruff check` and the full `pytest`
suite on every push and PR - both must be green before merging. No required
review count is currently configured, but that's a courtesy for a small
team, not a license to skip reading your own diff before opening the PR.

## Before you open a PR

```bash
ruff check app tests alembic     # must pass clean, no warnings suppressed
pytest                           # must pass; add tests for new behavior
```

If you touched anything performance- or scale-sensitive (queries against
`CustomerOrderLine`, `PurchaseOrderLine`, pagination), also run:

```bash
pytest -m slow tests/performance -v
```

If you touched a Qt dialog or page, prefer a `pytest-qt` test
(`tests/ui/`) over only testing its pure-function backend - two real bugs
in this codebase (see `docs/ROADMAP.md`'s Phase 6/7 entries) were only
caught by driving the actual widget, not its logic in isolation.

## Code conventions

- **Type hints and docstrings** on every public function/class. A
  docstring should say *why*, not just restate the signature - see any
  existing module for the expected tone.
- **No dead code, no `# TODO: implement later`** left in a merged PR unless
  explicitly agreed as deferred (and then it belongs in
  `docs/ROADMAP.md`, not a comment nobody will find).
- **No magic numbers, no hard-coded paths or credentials.** Business
  thresholds belong in `app/config/settings.py` (`AppSettings`), not
  inline - a coordinator should be able to retune them from the Settings
  page without a code change.
- **Business rules live in one place.** If you're computing "is this
  late" or "what's the priority," check `app/business/` and
  `app/repositories/` first - don't re-derive status/priority logic in a
  UI page.
- **Every schema change is a real Alembic migration** (`alembic revision
  --autogenerate -m "..."`), never a instruction to drop and recreate the
  database. See `docs/DATABASE.md`.
- **Audit trail is append-only.** Nothing should update or delete an
  `ActivityLogEntry` row - log a new one via
  `app/services/activity_log_service.py`.

## Commit messages

End commit messages and PR descriptions with:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

...if the change was made with Claude Code; otherwise a normal descriptive
message is fine. Prefer a body that explains *why* over a diff restated in
prose - future-you debugging a production issue will thank you.

## Where to look first

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - layering and why it's
  shaped this way
- [docs/DATABASE.md](docs/DATABASE.md) - schema and derived-value rules
- [docs/ROADMAP.md](docs/ROADMAP.md) - what's built, phase by phase, and
  what's intentionally deferred
- [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) - judgment calls made where
  the original spec was ambiguous, and why
- [docs/SECURITY.md](docs/SECURITY.md) - the auth model and its trust
  boundary
- [docs/AI.md](docs/AI.md) - the optional AI Insights module, off by
  default
