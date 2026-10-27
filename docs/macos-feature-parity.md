# Robot Ross Control Center — Mac port

Source: public `master` at `05f8e9d`, including the Mistral/Mexico browser UI.
The older Mac checkout had not received this interface. Work is in the isolated
`feature/macos-control-center` branch; the old checkout and calibration were not
overwritten. This is maintenance of existing Robot Ross software, not new
Ambient Field Lens hackathon functionality.

## Start

Double-click `launch_control_center.command`, or run it from Terminal. The page
is served at <http://localhost:7870>. The launcher prefers the dedicated `.venv`
and accepts `ROSS_PYTHON` and `HUENIT_PORT` overrides. It does not install models,
start Ollama, publish videos or accept sales orders.

To reproduce the isolated Python 3.12 environment:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-mac.txt
.venv/bin/python -m unittest discover -s tests -v
```

The repository's historical `/usr/bin/python3` also passed the control tests;
the dedicated environment supplies the newer voice SDKs without modifying
other projects. Dependency installation occupied approximately 1.4 GB; no LLM
or speech model weights were downloaded during this port.

## Feature inventory and verification

| PC feature | Mac implementation / evidence | Remaining live check |
| --- | --- | --- |
| Same Control Center layout | Live HTTP 200, original UI and SVG catalogue retained | Operator visual review |
| USB arm selection | `HUENIT_HUEARM` enumerated at `/dev/cu.usbserial-310` | Supervised motion |
| Session calibration | Mac terminal launch, portable single-key input, old readiness cleared; keyboard PTY and mocked launch tested | Run calibration beside Ross |
| Write / square / triangle / circle / demo | Positional size accepted; readiness enforced; radius and demo size bounded | Small pen drawing, then other shapes |
| SVG catalogue and drawing | Catalogue and previews served; approval command restored | Supervised chosen SVG |
| Sketch preview and approval | Success-only preview creation, stale output rejected, pending approve/cancel restored | Brain service/model configuration |
| Photo tracing / detail controls | Photo/image actions restored; more/less adjust smoothness and regenerate preview; vtracer imports | Representative photo and pen output |
| Fetch SVG | Existing fetch-only validation feeds preview or explicit direct drawing | Live approved URL |
| Chat / command confirmation | Original UI retained; missing model reported honestly, no invented success reply | Brain service/model configuration |
| Wiki / Ledger | Both original ATF pages return HTTP 200 on local port 8771; Mac launcher starts the existing ATF service only if needed | Grounded Q&A requires its configured model backend |
| System / Kokoro / Voxtral speech | All Python dependencies import; Mac playback helpers fixed | Speaker test; cached/downloaded Kokoro weights or Mistral credentials as selected |
| Voice showcase | Syntax errors repaired; local brain no longer requires an Anthropic client; Mac Q key support; no-arm dry-run restored; SVG stays SVG instead of becoming a sketch | Microphone permission, speech model, chosen brain, supervised drawing |
| Stop / busy / preview cancellation | Child process groups stopped; duplicate UI jobs rejected; correct shared temporary lock path; cancel discards pending preview | Physical controller buffering is not verified by process termination |
| OBS local recording | Installed SDK imports; recording remains opt-in in the UI, including approved sketches | OBS is installed but WebSocket port 4455 refused connection during checks; enable/configure it and camera scenes |
| YouTube delivery | Existing uploader retained; job upload now requires explicit `--upload` | OAuth and deliberate publication; nothing uploaded |
| Jog / teach-replay / suction / laser tools | Existing scripts retained; jog and teach already have POSIX terminal paths; all Python source compiles | Device/tool-specific commissioning; no laser/heat/vacuum command sent |
| Old Shopify/Salesman automation | Retained as retired legacy code, per upstream README | Not part of this Mac UI restoration; do not resume the old poller |

## Actual verification, 2026-10-26

- The initial 13 regression tests passed on macOS in both system Python 3.9 and
  the isolated Python 3.12 environment. The write-command follow-up passes 15
  tests in Python 3.12, including narrated manual writing without a model.
  These use fake providers/processes and a terminal PTY;
  they do not prove physical drawing or live voice quality.
- The isolated environment passes `pip check`; serial, image, ledger, tracing,
  microphone, Whisper, Kokoro, Mistral, Anthropic and OBS modules import.
- Live UI, status and SVG endpoints returned 200. ATF Wiki and Ledger returned
  200. No paid model request was made.
- Ollama daemon responds but its model list is empty, consistent with Miguel's
  disk cleanup. No model was restored. Model-dependent features remain pending
  a cloud/local selection; silent pen controls do not require Ollama.
- Manual write/shape/SVG jobs also work with narration enabled: a missing local
  model uses built-in narration, and Voxtral without credentials uses system
  speech. Failed command exits are surfaced in the Control Center page.
- `bob_ross.py check --no-voice` correctly reports session calibration missing.
  The arm has not moved during this port. Old poller PID 1870 remains paused.

The original UI's automatic browser opening is retained. Raw demo recordings
belong in `~/Movies/Ambient-Field-Lens/`, outside the source repository. The
demo story and daily capture plan are recorded separately in the Ambient
Field Lens working checkout's `docs/demo-production-plan.md`.

## 27 October: basic-shape X tilt correction

During operator-run 40 mm square takes, pen contact was incomplete. Inspection
found a definite defect: `huenit_draw.py` loads both saved tilt axes but travel
and draw moves used only Y. Both now apply the relative plane correction
`dz = tilt_slope_x * dx + tilt_slope * dy`. At the operator's current X slope
0.01, this restores 0.4 mm correction across a 40 mm X move. This is a possible
contributor, not a demonstrated sole cause of the failed take.

All 19 hardware-free tests pass (15 port regressions plus four new motion tests).
New checks cover positive/negative X, diagonal travel, retained Y/flat behavior
and a complete square returning to the same XYZ without accumulated plane
offset. Tests use a fake arm and forbid opening a serial port. No physical
command was sent for this fix; a supervised hardware retry remains pending.
Existing Control Center starts a fresh drawing subprocess, so the next shape
job reads the updated script without a server restart.

`z_up` is travel clearance after a correctly established paper-contact position,
not drawing pressure. Lowering it does not compensate for a mistaken contact
origin. Do not alter the operator's calibration file or order ledger as part
of this code fix. Raw failed takes remain in the private capture dataset.

### Supervised trial after the fix

Operator recalibrated (saved z_up2, tilt_y0.0325, tilt_x0.00375) and ran the same
40 mm square with the updated shape script. Operator reports it “worked
beautifully”; the post-draw image shows a closed outline with much clearer
sides. Controller reports completed/idle. A 120-second Reolink recording and
high-resolution result are archived privately as S21/S22 in the 27 October
drawing-readiness dataset. Sampled recording frames show state changes and the
completed square; exact stroke boundaries are not annotated.

This is one successful supervised trial after both recalibration and code change,
not an isolated demonstration that the code defect alone caused earlier failures.
Actual side lengths, metric camera registration and general robustness remain
unverified. Calibration and order-ledger files remain the operator's local data.

Operator's subsequent ruler check reports45 mm wide ×40 mm high for the40 mm
square (units explicitly confirmed): visual contact improved, but dimensional
accuracy did not pass. Source inspection confirms40 mm relative commands on both
axes and no wrapper enlargement at this size. Cause and measured-width-to-robot-
axis identity remain unverified. Requested opposite-edge measurements; no
firmware scaling, physical calibration or additional motion was changed.
