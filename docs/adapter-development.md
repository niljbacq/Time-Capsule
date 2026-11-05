# Adding an adapter

Recipe for a new application adapter. Written after the first one
(`terminal_xfce4`) took several rounds because the interface was guessed
instead of read. This is deliberately short; expand it as more adapters
land in Phase 5.

## Read the contracts first

- `src/session_snapshot/models/adapter_types.py`
- `src/session_snapshot/models/manifest.py`
- `src/session_snapshot/models/results.py`
- `src/session_snapshot/adapters/base.py`
- `src/session_snapshot/adapters/registry.py`
- `tests/fakes/fake_adapter.py` — working reference implementation

If code and this doc disagree, the code wins.

## The seven traps

1. **`adapter_id` regex.** Must match `^[a-z][a-z0-9_]{0,31}$` — no dots.
   `terminal.xfce4` fails; `terminal_xfce4` passes.

2. **`Capability` shape.** `{name: str, supported: bool, limitation: str | None}`.
   `capabilities()` returns `list[Capability]`, one entry per feature. There
   is no `captures=`, no `restores=`, no `limitations=` field.

3. **`AppInstance` has no `state`.** Fields are `instance_id`, `adapter_id`,
   `pid`, `app_id`, `label`. Application state belongs on `AppEntry.state`
   (a dict), populated in `capture()`.

4. **`RestorePlan` is a decision, not a launch descriptor.** Fields: `action`
   (`ActionKind`), `message`, `reason`, `missing_dependencies`,
   `unavailable_paths`. No `executable`, no `args`. Argv lives on
   `AppEntry.launch` (a `LaunchSpec`), populated in `capture()`.

5. **`restore()` takes three args** — `(snapshot, plan, ctx)`. Read argv from
   `snapshot.launch`, not from `plan`. Never `shell=True`.

6. **`Reason` has fixed members** — `OK`, `NOT_INSTALLED`, `PATH_MISSING`,
   `TIMEOUT`, `VERIFY_MISMATCH`, `UNSUPPORTED`, `EXCLUDED_BY_USER`,
   `ALREADY_RUNNING`, `ADAPTER_ERROR`. There is no `VERIFIED` and no
   `VERIFICATION_TIMEOUT`. Verified success is `Reason.OK`; verify timeout is
   `Reason.TIMEOUT`.

7. **`ctx.processes` is planning-time only.** `RestoreContext.processes` is
   captured once, before planning, and is NOT refreshed before `verify()`.
   Any process your `restore()` launches will NOT appear there. Consequence:
   `verify()` may take its own fresh look at the process tree directly
   (the terminal adapter does this in `_iter_shell_cwds()`). Everything else
   — `detect`, `capture`, `plan_restore` — must use the context snapshot
   and must not call `psutil` directly.

## Register

One import and one `registry.register(...)` line in
`src/session_snapshot/adapters/builtin.py`. Nothing under `core/`,
`services/`, `store/`, `report/`, `cli/`, or `gui/` needs to change.

## Testing pattern

Build `ProcessInfo` fixtures and pass them via context dataclasses. Do not
`patch("psutil.process_iter", ...)`. The only test that patches a helper
is `verify()` — patch the adapter's own live-scan helper, and patch
`time.monotonic` to force the timeout branch without sleeping.

See `tests/unit/test_terminal_adapter.py` for the full pattern.
