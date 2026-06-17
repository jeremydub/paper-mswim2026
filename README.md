# IoTeaPot — MSWiM 2026 experiment artifact

Public artifact for the paper *IoTeaPot: A Backend-Agnostic Framework for
Portable WSN Experimentation* (MSWiM 2026).

[IoTeaPot](https://github.com/jeremydub/ioteapot) separates an experiment's
*specification* (topology, firmware/applications, radio medium, event schedule,
observation contract) from its *execution backend*. 

This repository collects the experiment scripts, the firmware applications they
build, and per-experiment documentation used in the paper, plus one additional
experiment not in the paper.

## Contents

| Folder | Paper section | Purpose |
| --- | --- | --- |
| [`1-validation/`](1-validation) | Capability Validation | One UDP experiment + trace checker run unchanged on all 16 board/backend/OS cells, showing every modelled capability has its intended observable effect (functional correctness, not performance). |
| [`2-experiments-latencies/`](2-experiments-latencies) | Cross-Backend Experiments | End-to-end latency of one UDP app retargeted across simulator, emulator and three testbeds, under a baseline and two firmware variants (verbose logging, CPU contention). |
| [`3-experiment-tsch/`](3-experiment-tsch) | Cross-Backend Experiments (Variant 3) | TSCH clock-drift ablation: drift correction ON/OFF on a driftless Cooja mote vs. real hardware. |
| [`4-validation-move-action/`](4-validation-move-action) | Capability Validation | `MoveNodeAction` (node mobility) validation on the two position-aware backends; companion to `1-validation`. |
| [`5-experiment-drift/`](5-experiment-drift) | *(not in paper)* | Long-run host-vs-device clock-drift comparison across all backends. |

Each numbered folder holds its own `README.md`, the experiment script, and one
or more firmware applications (`app-contiki`, `app-riot`, `app-embassy`, …).

## Dependencies

Firmware is built from pinned OS/stack sources, added as git submodules:

| Submodule | Source | Pin |
| --- | --- | --- |
| `contiki-ng/` | contiki-ng/contiki-ng | commit `6a35472` |
| `RIOT/` | jeremydub/RIOT | branch `mswim2026` |
| `embassy/` | jeremydub/embassy | branch `mswim2026` |

## Setup

```bash
# 1. install the framework
pip3 install -U git+https://github.com/jeremydub/ioteapot

# 2. fetch RTOS sources/dependencies
git submodule update --init --recursive
```

Then run any experiment with `python <folder>/<script>.py`; see each folder's
`README.md` for specifics.
