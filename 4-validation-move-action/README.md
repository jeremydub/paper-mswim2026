# 4. MoveNodeAction Validation

Companion to [`1-validation`](../1-validation), covering the fifth action type —
node mobility (`MoveNodeAction`) — on the two position-aware backends (Cooja and
Renode); the testbeds and local hardware have fixed physical placements.

## Experiment

Under a lossy unit-disk medium, a **sender** starts at the edge of a **receiver**'s
range and is relocated step by step (every 30s, nine hops of +10m) while the
receiver logs arrivals. The `MovePdr` listener reports packet delivery ratio per
30s slice; the falling PDR shows that each relocation actually takes effect.

Contiki-NG only.

## Layout

- `validation_move_action.py` — the mobility schedule and the `MovePdr` listener.
- `app-contiki-ping/` — minimal Contiki-NG ping/pong firmware.

## Running

```bash
python validation_move_action.py
```

Prints PDR per 30s slice for each backend.
