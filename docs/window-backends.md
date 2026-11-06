# Window backends

How Linux Session Snapshot captures and restores window placement, and
what is empirically verified vs. what is a documented limitation.

## X11 (Xfwm4)

Verified on Linux Mint XFCE, Xfwm4, 1366x768, workspace area 1366x735.

### Reading windows

- `wmctrl -l -G` — main source, parsed by `windows/parsers.py`
- `xprop` — window type and pid
- `wmctrl -d` — workspace list

### Placing windows

`X11Backend.place_window(window_id, workspace, state, geometry)` runs, in
order:

1. `wmctrl -i -r <id> -b remove,maximized_vert,maximized_horz`
2. `wmctrl -i -r <id> -b remove,fullscreen`
3. `wmctrl -i -r <id> -t <workspace>` (if workspace is not None)
4. One of:
   - normal + geometry: `wmctrl -i -r <id> -e 10,<x>,<y>,<w>,<h>`
   - maximized: `wmctrl -i -r <id> -b add,maximized_vert,maximized_horz`
   - fullscreen: `wmctrl -i -r <id> -b add,fullscreen`

The `10` in `-e 10,x,y,w,h` is ICCCM StaticGravity. Verified on Xfwm4:
setting `Geometry(400, 200, 500, 350)` produced exact `x=400 y=200 w=500
h=350` on read-back, delta (0, 0, 0, 0). If a different WM shows a
consistent dy or dw offset, the signal to try is gravity `0`
(NorthWestGravity). Do not change the constant without an empirical
backend test on the target WM.

Maximize verified: `state="maximized"`, `geometry=None` → read-back
`state="maximized"`, geometry auto-set by the WM to the workspace area.

### Client/server apps

Some apps use a single server process that owns every window. `xfce4-terminal`
is the canonical case (also Firefox when it reuses an existing instance):

- `xfce4-terminal --window --working-directory X` launches a **client**
  that handshakes with the running server and exits within ~100ms.
- The launched pid is dead by the time `apply_saved_windows()` runs.
- No ancestor of that pid owns a window — the server does, and the server
  is not in the launched process's ancestry.
- `candidate_windows()` returns `[]`; `plan_placements()` returns the exact
  warning "expected N window(s) but found 0; window placement skipped".
- Status stays `RESTORED` (per invariant: placement is cosmetic).

This is the **honest** behavior. The terminal adapter's `window_placement`
capability is marked unsupported with a limitation describing exactly this.
If terminal placement becomes important, the fix is a cwd-hint fallback in
`apply_saved_windows` — match by saved cwd rather than pid — at the cost of
coupling the generic placement code to specific app process models. Deferred;
terminals are the common case and the limitation is documented.

### Testing pattern

The direct wmctrl E2E used to validate placement (2026-11-06):

1. Launch a **1:1 app** (own process owns own window): `xclock`, `xterm`.
   Not `xfce4-terminal`, not `firefox` when a server is running.
2. `backend.place_window(id, workspace=1, state="normal",
   geometry=Geometry(400, 200, 500, 350))`
3. Read back via `backend.list_windows()`, compare with ±20/±30 tolerance.
4. Terminate. **Do not just `proc.wait()`** — poll `wmctrl -l` until the
   window disappears before starting the next case. The X server can lag
   window destruction by a poll cycle or two, and a stale window from case
   N is silently reused as case N+1's target (verified: same window id
   appeared across two consecutive cases in the 2026-11-06 run, because
   terminate() returned before the X server removed the window).

### Environment detection

`SessionService` constructs `X11Backend()` via `factory.py` and passes it to
`SessionManager` (for save-time capture) and `RestoreEngine` (for
post-restore placement). `X11Backend.available()` checks the `DISPLAY`
environment variable and that `wmctrl` is on PATH.