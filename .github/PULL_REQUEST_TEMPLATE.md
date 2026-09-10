## Summary

<!-- What does this change, and why? Link an issue if there is one. -->

## Verification

<!-- How did you confirm this works? Prefer real command output over "should work". -->

- [ ] `ruff check app tests alembic` passes clean
- [ ] `pytest` passes (added/updated tests for new behavior)
- [ ] If this touches a Qt dialog/page: added or updated a `pytest-qt` test in `tests/ui/`, not just its pure-function backend
- [ ] If this touches a query against `CustomerOrderLine`/`PurchaseOrderLine`/pagination: ran `pytest -m slow tests/performance -v`
- [ ] If this changes the schema: added a real Alembic migration (`alembic revision --autogenerate -m "..."`) - never an instruction to drop/recreate the database

## Notes for the reviewer

<!-- Anything non-obvious, deliberately deferred, or worth double-checking. -->

<!-- If this PR was made with Claude Code, end the description with the line CONTRIBUTING.md specifies - see "Commit messages" there. -->
