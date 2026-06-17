# 1. Capability Validation

Establishes **functional correctness**: each modelled capability produces its
intended observable effect on every backend. One UDP experiment runs *unchanged*
across all sixteen board/backend/OS cells of the paper's validation matrix, and a
checker (an ordinary event listener) replays each trace against assertions
derived from the schedule.

## Experiment

Next to an always-on UDP **server**, a held-off UDP **client** (`auto_start=False`)
starts at `T=10s`; a serial write at `T=30s` arms one numbered request every 5s
(logged by the client, captured by a sniffer, logged by the server); the server's
third reception stops it mid-traffic; a time trigger ends the run at `T=60s`.

One minute exercises both trigger types (time + serial-read), four of the five
action types (start node, serial write, stop node, stop experiment), and all five
observation events. The fifth action, `MoveNodeAction`, is validated separately in
[`4-validation-move-action`](../4-validation-move-action).

The matrix spans CoojaMote and Zolertia Z1 on Cooja; CC2538-DK and Firefly on
Renode; Firefly and nRF52840-DK on local hardware; IoT-LAB M3 and nRF52840-DK on
FIT IoT-LAB — with Contiki-NG, RIOT and/or Embassy per cell. Where a board recurs
it runs the *identical* firmware binary, so portability is checked on one image,
not on re-implementations.

## Layout

- `validation.py` — the experiment, the matrix, and the `Checker` listener.
- `app-contiki/` — Contiki-NG UDP server/client (RPL + UDP).
- `app-riot/` — RIOT UDP server/client.
- `app-embassy/` — Rust/Embassy UDP app (nRF52840-DK only, its sole supported
  802.15.4 board so far).

## Running

```bash
python validation.py
```

Each cell prints its trace and a recap, then `PASSED` / `FAILED` from the
checker's assertions (see `Checker.verify`); a final line reports how many cells
passed, and the process exits non-zero if any failed. Cells whose backend is not
attached (no hardware / no testbed reservation) are reported as `SKIPPED` and
excluded from the count, so the simulator/emulator cells can be checked on their
own. On the Zolertia Z1 under Cooja the serial write does not register — a Cooja
limitation, present without the framework too — so that cell asserts the request
stream stays silent rather than running the full schedule.
