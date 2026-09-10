# Deployment option: shared database on a network drive

Lets several coordinators, each with their own install of CAMCO Coordinator
on their own PC, see and edit the same live data - without setting up a
database server. This is the "quick" multi-user option; see the note at the
bottom for when to outgrow it in favor of a real database server (tracked as
a future revisit, not built yet).

## How to set it up

1. Put the database file somewhere every coordinator's PC can reach over
   your office network - typically a folder on a file server, e.g.
   `\\SERVER\CAMCO\camco_coordinator.db`.
2. On **each** coordinator's install: open **Settings > Folders**, set
   **Database File** to that exact same path, click **Save Settings**, and
   restart the app.
3. The first person to connect creates the database fresh (schema, default
   admin account) if it doesn't already exist there; everyone after that
   connects to the same live data.

Every install must point at the **exact same file** - not copies of it. If
even one coordinator's install still points at their own local file, their
changes won't show up for anyone else, and nobody will get an error telling
them so.

## What the app does automatically

SQLite's WAL journal mode (used for local installs, for its read/write
concurrency) needs shared-memory-mapped files, which most network
filesystems - SMB shares in particular - don't implement safely. Using it
over a network share risks database corruption with concurrent writers.

`app/database/session.py` detects when the configured database path is a
network location (a UNC path, or a mapped drive letter - checked via the
Windows `WNetGetConnectionW` API) and automatically switches to SQLite's
traditional `DELETE` journal mode instead, which SQLite's own documentation
recommends for network filesystems. This happens transparently - nothing to
configure, and it's logged (`Database path ... looks like a network
location - using DELETE journal mode instead of WAL`) so it's visible in the
log file if you're ever debugging why it feels different from a local
install.

## What this does *not* solve

Even with the safer journal mode, this is still SQLite doing file-level
locking over a network share, not a real database server arbitrating
concurrent transactions. SQLite's own guidance is that this is reasonable
for **light or occasional** simultaneous access, not **heavy, continuous**
multi-user editing:

- Two coordinators editing *different* order lines at the same moment:
  fine, this is the normal case and works reliably.
- Many coordinators saving edits within the same second, repeatedly, all
  day: real risk of a write timing out, retrying, or (in degenerate cases on
  flaky network filesystems) corruption. `PRAGMA synchronous=NORMAL` and the
  `DELETE` journal help, but don't eliminate this.
- **This also doesn't work offline.** Every install still needs the network
  share reachable to open the app at all - it's not "offline-first with
  occasional sync," it's "always needs the file server up."

Back up the shared file more frequently than you would a local install
(**Settings > Backup**, pointed at a location distinct from the shared
database's own folder) while running this deployment option.

## When to move on from this

If your team outgrows light/occasional concurrent use - frequent edit
collisions, growing coordinator headcount, or a need for the app to keep
working when the file server is briefly unreachable - the next step is a
real database server (PostgreSQL), which this app's architecture already
supports (no code above `app/database/session.py` assumes SQLite-specific
behavior - see `docs/ARCHITECTURE.md`). That move also requires hardening
the currently UI-only role/permission checks into a real service layer,
since multiple people sharing one backend over a network is exactly the
point `docs/SECURITY.md`'s trust-boundary note calls out as needing that
change. Tracked as a follow-up, not yet built.
