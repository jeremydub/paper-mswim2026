"""Cross-backend latency experiments (variants 1 & 2) for IoTeaPot (MSWiM'26).

One UDP application is retargeted across a simulator, an emulator and three
testbeds by changing only the platform and environment. Every cell runs under
three firmware conditions -- baseline, verbose logging (variant 1) and CPU
contention (variant 2) -- five times, and per-request end-to-end latency is
written to a CSV under data/ (one row per request, e2e_delay_ms column).

Applications are relative to the paper/ root;
"""

import csv
import datetime
import logging
import os
import re
import threading

from ioteapot import Node, setup_logging
from ioteapot.environments import CoojaSimulator, FitIotLab, Local, Renode
from ioteapot.errors import IoTeaPotError
from ioteapot.experiment import Experiment, Topology
from ioteapot.experiment.event import StopExperimentAction, BaseEventListener
from ioteapot.experiment.medium import UnitDiskRadioMedium
from ioteapot.os import contiki, riot
from ioteapot.platforms import (
    CoojaMotePlatform,
    IotLabM3Platform,
    Nrf52840dkPlatform,
    ZolertiaFireflyPlatform,
    ZolertiaZ1Platform,
)

UDP_APP = "app-contiki"
RIOT_SERVER = "app-riot/udp-server"
RIOT_CLIENT = "app-riot/udp-client"

N_REQUESTS = 80          # 80 requests x 10 s + 60 s warm-up ~ 15 min of traffic
SEND_DELAY = 60
SEND_INTERVAL = 10
DURATION = 15 * 60
REPEATS = 5

# do_work() iterations for variant 2 (CPU contention), per platform.
WORK = {
    "Cooja Mote": 200000,
    "Zolertia Z1": 5000,
    "Zolertia Firefly": 200000,
    "IoT-LAB M3": 500000,
    "nRF52840 DevKit": 400000,
}

# backend label, board class, node count, operating systems.
BACKENDS = [
    ("cooja",  CoojaMotePlatform,       16, ["contiki"]),
    ("cooja",  ZolertiaZ1Platform,      16, ["contiki"]),
    ("renode", ZolertiaFireflyPlatform, 16, ["contiki", "riot"]),
    ("local",  ZolertiaFireflyPlatform, 16, ["contiki", "riot"]),
    ("paris",  IotLabM3Platform,        16, ["contiki", "riot"]),
    ("saclay", Nrf52840dkPlatform,      10, ["contiki", "riot"]),
]

# condition label, verbose logging, CPU contention.
CONDITIONS = [("baseline", False, False), ("V1", True, False), ("V2", False, True)]

_SEND = re.compile(r"[Ss]ending request\s+(\d+)")
_RECV = re.compile(r"[Rr]eceived response\D*?(\d+)")


def make_apps(rtos, env, verbose):
    """Return (server_app, client_app) for the given OS and logging level."""
    if rtos == "contiki":
        directives = {"SEND_INTERVAL": SEND_INTERVAL}
        if verbose:
            directives["LOG_CONF_LEVEL_IPV6"] = "LOG_LEVEL_DBG"
        conf = contiki.ProjectConf(**directives)
        server = contiki.Application(app_folder=UDP_APP, target="udp-server",
                                     project_conf=conf)
        client = contiki.Application(app_folder=UDP_APP, target="udp-client",
                                     project_conf=conf)
    elif rtos == "riot":
        server = riot.Application(app_folder=RIOT_SERVER)
        client = riot.Application(app_folder=RIOT_CLIENT)
        server.environment_variables["GNRC_IPV6_DEBUG"] = "1" if verbose else "0"
        client.environment_variables["GNRC_IPV6_DEBUG"] = "1" if verbose else "0"
        server.environment_variables["CC2538_RF_RENODE_FIX"] = "1" if isinstance(env, Renode) else "0"
        client.environment_variables["CC2538_RF_RENODE_FIX"] = "1" if isinstance(env, Renode) else "0"

    else:
        raise ValueError(f"unknown rtos {rtos!r}")
    return server, client


def make_env(label):
    if label == "cooja":
        return CoojaSimulator()
    if label == "renode":
        return Renode()
    if label == "local":
        return Local(flash_concurrency=16)
    return FitIotLab(site=label)  # paris / saclay


class RttListener(BaseEventListener):
    """Pair each client's 'Sending request N' with its 'Received response N'
    and write per-request end-to-end latency (ms) to a CSV."""

    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.lock = threading.Lock()
        self.order = []   # (node, seq) in first-seen order
        self.req = {}     # (node, seq) -> [request_ms, response_ms]

    def experiment_started(self, timestamp):
        print(f"  -> {self.csv_path}")

    def serial_message(self, node, timestamp, message, *, clocks=None):
        nid = str(node)
        m = _SEND.search(message)
        if m:
            seq = int(m.group(1))
            with self.lock:
                r = self.req.get((nid, seq))
                if r is None:
                    self.req[(nid, seq)] = [timestamp, None]
                    self.order.append((nid, seq))
                else:
                    r[0] = timestamp  # last send wins on retransmit
            return
        m = _RECV.search(message)
        if m:
            seq = int(m.group(1))
            with self.lock:
                r = self.req.get((nid, seq))
                if r is not None and r[1] is None:
                    r[1] = timestamp

    def experiment_ended(self, timestamp):
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        sent = delivered = 0
        with self.lock, open(self.csv_path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["source_node", "packet_id", "request_ms", "e2e_delay_ms"])
            for nid, seq in sorted(self.order, key=lambda k: self.req[k][0]):
                request_ms, response_ms = self.req[(nid, seq)]
                sent += 1
                delivered += response_ms is not None
                w.writerow([
                    nid, seq, f"{request_ms:.3f}",
                    "" if response_ms is None else f"{response_ms - request_ms:.3f}",
                ])
        pdr = delivered / sent if sent else 0.0
        print(f"  {delivered}/{sent} delivered (PDR={pdr:.2f})")


def main():
    setup_logging(logging.INFO)
    for label, board, n_nodes, oses in BACKENDS:
        platform = board()
        env = make_env(label)
        for rtos in oses:
            for cond, verbose, contention in CONDITIONS:
                work = WORK[str(platform)] if contention else 0
                for rep in range(REPEATS):
                    server_app, client_app = make_apps(rtos, env ,verbose)
                    client_app.environment_variables.update(
                        DO_WORK_ITERATIONS=str(work), N_REQUESTS=str(N_REQUESTS),
                        SEND_DELAY=str(SEND_DELAY), ROUTING_CAPACITY=str(n_nodes),
                        BACKEND=label)
                    server_app.environment_variables.update(
                        ROUTING_CAPACITY= str(n_nodes + 2), BACKEND=label)

                    topology = Topology(medium=UnitDiskRadioMedium(
                        transmitting_range=100, interference_range=0))
                    topology.add_node(Node(identifier="server", position=(0.0, 0.0, 0.0),
                                           application=server_app, platform=platform))
                    for i in range(n_nodes - 1):
                        topology.add_node(Node(
                            identifier=f"client{i + 1}",
                            position=(0.5 * (i + 1), 0.0, 0.0),
                            application=client_app, platform=platform))

                    exp = Experiment(topology=topology, name=f"{label}-{platform}")
                    exp.after(DURATION).do(StopExperimentAction())

                    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                    path = (f"data/data_{rtos}_{env.name}_{platform}_work{work}_"
                            f"{'debug' if verbose else 'nodebug'}_{stamp}_r{rep}.csv")
                    print(f"\n=== {rtos} / {platform} @ {env.name} / {cond} (rep {rep}) ===")
                    try:
                        exp.run(env, event_listener=RttListener(path))
                    except IoTeaPotError as exc:
                        print(f"  SKIPPED {label}/{platform}/{rtos}/{cond}: {exc}")


if __name__ == "__main__":
    main()
