# Security Review (Phase 7)

Scope: the local authentication flow, data-handling surfaces (import files,
database queries), and the trust model appropriate for a single-user
Windows desktop application, per spec rule 27 and the master prompt's
"Cybersecurity Engineer" role.

## Authentication

- Passwords are hashed with PBKDF2-HMAC-SHA256, 260,000 iterations, a
  16-byte random salt per user (`app/security/auth.py`). The scheme name and
  iteration count are stored in the hash string itself
  (`pbkdf2_sha256$260000$<salt>$<hash>`), so a future upgrade to a stronger
  KDF (e.g. Argon2) can support both old and new hashes during a migration
  window without forcing every user to reset their password on the same day.
- Password comparison uses `hmac.compare_digest` - constant-time, not
  short-circuiting on the first differing byte (timing-attack resistant).
- Account lockout: configurable max failed attempts and lockout duration
  (`SecuritySettings`), tested against the exact boundary (locks on the
  Nth attempt, not the N+1th) in `tests/integration/test_auth.py`.
- The first-run default admin account gets a random 12-hex-character
  temporary password, logged to the local log file only (never printed to
  console, never transmitted) - never a fixed default credential.
- **New this phase**: an idle-timeout session lock
  (`app/ui/idle_lock.py`, `app/ui/dialogs/lock_screen_dialog.py`). The
  `SecuritySettings.session_idle_minutes` field existed since Phase 1 but
  was never enforced - a real gap, since an unattended unlocked coordinator
  workstation is a legitimate exposure. It's wired into `MainWindow`, off by
  default (0 = disabled, matching the pre-existing default so no behavior
  changes for anyone who hasn't configured it), and the lock screen cannot
  be dismissed by Escape or the window close button - only by re-entering
  the current user's password.

## Injection / data handling

- Every database query in the codebase goes through SQLAlchemy's query
  builder (`select(...)`, ORM relationship loading) with bound parameters -
  there is no string-formatted or concatenated SQL anywhere in `app/`
  (verified by scanning for `f"...SELECT`, `.format(` and `%`-style query
  construction; none found). SQL injection is not a realistic risk here.
- Excel/CSV import (`app/imports/readers.py`) opens workbooks with
  `data_only=True`: cached values are read, formulas are never
  re-evaluated by the app, and `.xlsm` macros are never executed - openpyxl
  has no macro-execution capability at all. A malicious spreadsheet can at
  worst supply bad *data*, which the import validator already rejects with
  a row-level error rather than silently accepting it.
- Source files are opened read-only and never written back to (spec rule
  55) - an imported spreadsheet cannot be corrupted by the app itself.

## Role enforcement - a documented trust boundary, not a gap

`AuthenticatedUser.can_edit` / `.is_admin` gate every mutating UI control
(New/Edit/Delete buttons are hidden entirely for VIEWER, spec rule 27's
read-only role). This is enforced at the **UI layer**, not re-checked again
inside the repository/service layer that actually writes to the database.

For a single-user local desktop application - the only deployment this
codebase targets today - that's an appropriate, deliberate boundary: the
"attacker" who could reach a mutating repository call despite a hidden
button is the same person who already has a full copy of the SQLite file
and the Windows user account it's running under, so a service-layer role
check would not meaningfully raise the bar. It becomes a real gap the
moment this app is ever exposed multi-user over a network (e.g. a shared
database server, an API) rather than run as one person's local process -
at that point, role checks belong in a service layer that mediates *all*
writes regardless of which client is asking, and that's called out as
prerequisite work in `docs/ARCHITECTURE.md`'s security-model section before
any such deployment.

## Logging

- The rotating log file can contain the first-run temporary admin password
  (by design, so an admin can retrieve it) and general application errors.
  It never contains a real user's password, hash, or session token -
  `app/security/auth.py` is the only place a plaintext password is ever
  handled, and it is never logged.

## Recommendations tracked for later phases

- If/when network multi-user access is added: move mutation authorization
  into a service layer, not just the UI (see trust-boundary note above).
- If/when SSO (Active Directory / Entra ID) is added: `AuthenticatedUser`
  and `UserRole` already form the seam a new backend would populate -
  `app/security/auth.py`'s docstring calls this out explicitly.
