"""TSCH clock-drift fidelity experiment (variant 3) for IoTeaPot (MSWiM'26).

The same TSCH application is run as a 2x2 ablation: drift correction ON/OFF on
a driftless Cooja mote and on real hardware. Per run the listener prints (and
saves under data/) the number of synchronized nodes over time and the global
packet delivery ratio, in the format the TSCH figure script consumes.

Contiki-NG only. The application is relative to the paper/ root.
"""

import datetime
import logging
import os

from ioteapot import Node, setup_logging
from ioteapot.environments import CoojaSimulator, Local
from ioteapot.errors import IoTeaPotError
from ioteapot.experiment import Experiment, Topology
from ioteapot.experiment.event import StartNodeAction, StopExperimentAction
from ioteapot.experiment.medium import UnitDiskRadioMedium
from ioteapot.os import contiki
from ioteapot.platforms import CoojaMotePlatform, ZolertiaFireflyPlatform

TSCH_APP = "app-contiki-tsch"
N_CLIENTS = 15
DURATION = 15 * 60
REPEATS = 5

# board class, environment factory -- the two execution models contrasted.
TARGETS = [
    (CoojaMotePlatform, CoojaSimulator),
    (ZolertiaFireflyPlatform, lambda: Local(flash_concurrency=16)),
]


class TschListener:
    """Track the associated-node count over time and the global PDR."""

    def __init__(self, out_path):
        self.out_path = out_path

    def experiment_started(self, timestamp):
        self.associated = 0
        self.history = []           # (timestamp_ms, associated count)
        self.sent = self.received = 0

    def serial_message(self, node, timestamp, message, *, clocks=None):
        if "association done" in message or "leaving the network" in message:
            self.associated += 1 if "association done" in message else -1
            self.history.append((timestamp, self.associated))
            print(f"  [{timestamp:9.1f} ms] {node}: {self.associated} nodes associated")
        elif "S:" in message:
            self.sent += 1
        elif "R:" in message:
            self.received += 1

    def experiment_ended(self, timestamp):
        pct = self.received * 100 / self.sent if self.sent else 0.0
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
        with open(self.out_path, "w") as fh:
            for t, n in self.history:
                fh.write(f"  {t:9.1f} ms -> {n}\n")
            fh.write(f"PDR:{self.sent} sent, {self.received} received: {pct}%\n")
        for t, n in self.history:
            print(f"  {t:9.1f} ms -> {n}")
        print(f"PDR:{self.sent} sent, {self.received} received: {pct}%")
        print(f"  -> {self.out_path}")


def main():
    setup_logging(logging.INFO)
    coordinator_app = contiki.Application(app_folder=TSCH_APP, target="coordinator")
    for board, make_env in TARGETS:
        platform = board()
        for correction in (1, 0):  # drift correction on / off
            node_app = contiki.Application(
                app_folder=TSCH_APP, target="node",
                project_conf=contiki.ProjectConf(
                    TSCH_CONF_ADAPTIVE_TIMESYNC=1,
                    TSCH_TIMESYNC_DRIFT_CORRECTION=correction,
                    RPL_CONF_DEFAULT_LEAF_ONLY=1))
            for rep in range(REPEATS):
                topology = Topology(medium=UnitDiskRadioMedium(
                    transmitting_range=100, interference_range=100))
                topology.add_node(Node(identifier="server", position=(0.0, 0.0, 0.0),
                                       application=coordinator_app, platform=platform))
                for i in range(1, N_CLIENTS + 1):
                    topology.add_node(Node(
                        identifier=f"client-{i}", position=(i * 2.0, 0.0, 0.0),
                        application=node_app, platform=platform, auto_start=False))

                exp = Experiment(topology=topology, name=f"tsch-{platform}")
                for i in range(1, N_CLIENTS + 1):
                    exp.after(1 + i * 1.1).do(StartNodeAction(node=topology.nodes[i]))
                exp.after(DURATION).do(StopExperimentAction())

                env = make_env()
                corr = "on" if correction else "off"
                stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                path = f"data/tsch_{env.name}_{platform}_corr{corr}_{stamp}_r{rep}.txt"
                print(f"\n=== TSCH on {platform} @ {env.name}, correction {corr} (rep {rep}) ===")
                try:
                    exp.run(env, event_listener=TschListener(path))
                except IoTeaPotError as exc:
                    print(f"  SKIPPED {platform}/{env.name}/corr{corr}: {exc}")


if __name__ == "__main__":
    main()
