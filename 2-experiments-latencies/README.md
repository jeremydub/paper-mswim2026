# 2. Cross-Backend Latency

Reproduces, cheaply, the kind of cross-backend performance divergence that
porting cost usually makes rare. One UDP application is retargeted across a
simulator, an emulator and three testbeds by changing only the platform and
environment arguments, and end-to-end latency is compared.

## Experiment

A dense **1-hop** topology (a deliberate control that isolates execution-model
effects from multi-hop fidelity): every client sends a request every 10s for
~15 min, the root replies, and per-request E2E latency (request → response) is
recorded. Each cell runs under three firmware conditions, five times:

- **baseline** — plain stack.
- **V1 — verbose logging** — IPv6 debug logging (`LOG_LEVEL_DBG` in Contiki-NG,
  `gnrc_ipv6` debug in RIOT) adds many serial lines per packet.
- **V2 — CPU contention** — a `do_work(n)` busy loop after each transmission
  keeps the MCU busy (`n` per platform).

Backends and node counts: 16-node Cooja (CoojaMote and Z1), 16 Renode Firefly,
16 local Firefly, 16 IoT-LAB M3 (FIT IoT-LAB Paris), 10 nRF52840-DK (FIT IoT-LAB
Saclay). Contiki-NG runs everywhere; RIOT on Renode and the testbeds (Cooja is
Contiki-specific). The split this surfaces: logging and CPU-contention costs
appear on hardware and under emulation but not on a Cooja mote.

## Layout

- `experiment_latencies.py` — the sweep and the `RttListener` (writes CSV).
- `app-contiki/` — Contiki-NG UDP server/client.
- `app-riot/` — RIOT UDP server/client.

## Running

```bash
python experiment_latencies.py
```

Writes one CSV per run under `data/` (one row per request, `e2e_delay_ms`
column). The paper's latency figure is produced from these CSVs.
