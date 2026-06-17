# 3. TSCH Clock-Drift Ablation

Variant 3 of the cross-backend study. The best-effort CSMA stack is swapped for
**TSCH**, the time-slotted, channel-hopping MAC used for deterministic industrial
traffic, which holds the network synchronised by continuously estimating and
correcting crystal drift — a physical effect present on hardware but absent on a
driftless Cooja mote.

## Experiment

A **2×2 ablation**: drift correction ON/OFF × CoojaMote / hardware (Zolertia
Firefly, local). One coordinator and 15 nodes, ~15 min, five repeats. The
`TschListener` tracks the number of synchronised nodes over time and the global
packet delivery ratio.

Expected outcome (paper): with correction **on**, every node stays synchronised
everywhere; with it **off**, the CoojaMote network is undisturbed (no drift to
correct) while the hardware network never holds full synchronisation — nodes
repeatedly fall out and rejoin and PDR drops from near-100% to roughly 91%. The
two settings are therefore indistinguishable on a Cooja mote.

Contiki-NG only.

## Layout

- `experiment_tsch.py` — the ablation and the `TschListener` (writes a trace).
- `app-contiki-tsch/` — 6TiSCH coordinator/node firmware with adaptive timesync.

## Running

```bash
python experiment_tsch.py
```

Writes one association/PDR trace per run under `data/`. The paper's TSCH figure
is produced from these traces.
