"""Clock-drift comparison experiment for IoTeaPot (MSWiM'26).

The same UDP application is retargeted across a simulator, an emulator and the
testbeds; the client sends one request every SEND_INTERVAL and the listener
compares each send time against the expected cadence. A driftless Cooja mote
stays on schedule, while MSPSim emulation, Renode and real hardware accumulate
crystal drift. Per run, the (request, observed, expected, drift) samples are
written to a CSV under data/.

Contiki-NG only. The application is relative to the paper/ root.
"""

import csv
import datetime
import logging
import os
import re

from ioteapot import Node, setup_logging
from ioteapot.environments import CoojaSimulator, FitIotLab, Local, Renode
from ioteapot.errors import IoTeaPotError
from ioteapot.experiment import Experiment, Topology
from ioteapot.experiment.event import (
    SerialReadTrigger,
    StartNodeAction,
    StopExperimentAction,
)
from ioteapot.experiment.medium import UnitDiskRadioMedium
from ioteapot.os import contiki
from ioteapot.platforms import (
    CoojaMotePlatform,
    IotLabM3Platform,
    Nrf52840dkPlatform,
    ZolertiaFireflyPlatform,
    ZolertiaZ1Platform,
)

UDP_APP = "applications/contiki-app"

SEND_INTERVAL = 30         # s; written into project-conf via ProjectConf
CLIENT_BOOT_OFFSET = 10    # s; when the client is started
NUM_REQUESTS = 60 * 6      # sends to collect before stopping (~3 h at 30 s)
SAFETY_TIMEOUT = 3600 * 4  # s; hard stop if the trigger never fires

# board class, environment factory.
VARIANTS = [
    (CoojaMotePlatform, CoojaSimulator),                       # driftless simulation
    (ZolertiaZ1Platform, CoojaSimulator),                      # MSPSim emulation
    (ZolertiaFireflyPlatform, Renode),                         # Renode emulation
    (ZolertiaFireflyPlatform, Local),                          # local hardware
    (IotLabM3Platform, lambda: FitIotLab(site="grenoble")),    # testbed
    (Nrf52840dkPlatform, lambda: FitIotLab(site="saclay")),    # testbed
]


class DriftListener:
    """Record each 'Sending request N' time and its drift from the cadence."""

    _SENDING = re.compile(r"Sending request (\d+)")

    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.base_t = None
        self.base_id = None
        self.samples = []   # (req_id, observed_ms, expected_ms, drift_ms)

    def experiment_started(self, timestamp):
        print(f"  -> {self.csv_path}")

    def serial_message(self, node, timestamp, message, *, clocks=None):
        m = self._SENDING.search(message)
        if not m:
            return
        req_id = int(m.group(1))
        if self.base_t is None:
            self.base_t, self.base_id = timestamp, req_id
        expected = self.base_t + (req_id - self.base_id) * SEND_INTERVAL * 1000
        drift = timestamp - expected
        self.samples.append((req_id, timestamp, expected, drift))
        print(f"  request {req_id:>3d}  observed={timestamp:.1f} ms  "
              f"expected={expected:.1f} ms  drift={drift:+.1f} ms")

    def experiment_ended(self, timestamp):
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        with open(self.csv_path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["request_id", "observed_ms", "expected_ms", "drift_ms"])
            for req_id, obs, exp, drift in self.samples:
                w.writerow([req_id, f"{obs:.3f}", f"{exp:.3f}", f"{drift:.3f}"])
        drifts = [s[3] for s in self.samples]
        if drifts:
            print(f"  {len(drifts)} samples, drift min={min(drifts):+.1f} "
                  f"max={max(drifts):+.1f} final={drifts[-1]:+.1f} ms -> {self.csv_path}")
        else:
            print(f"  no samples -> {self.csv_path}")


def main():
    setup_logging(logging.INFO)
    server_app = contiki.Application(app_folder=UDP_APP, target="udp-server")
    client_app = contiki.Application(
        app_folder=UDP_APP, target="udp-client",
        project_conf=contiki.ProjectConf(SEND_INTERVAL=SEND_INTERVAL))
    # Auto-send after boot (no "send-data" command) and collect enough requests.
    client_app.environment_variables.update(N_REQUESTS=str(NUM_REQUESTS), SEND_DELAY="0")

    for board, make_env in VARIANTS:
        platform = board()
        server = Node(identifier="server", position=(0.0, 0.0, 0.0),
                      application=server_app, platform=platform)
        client = Node(identifier="client", position=(2.0, 0.0, 0.0),
                      application=client_app, platform=platform, auto_start=False)
        topology = Topology(medium=UnitDiskRadioMedium(
            transmitting_range=20, interference_range=0))
        topology.add_node(server)
        topology.add_node(client)

        exp = Experiment(topology=topology, name=f"drift-{platform}")
        exp.after(CLIENT_BOOT_OFFSET).do(StartNodeAction(node=client))
        exp.when(SerialReadTrigger.contains_(
            client, f"Sending request {NUM_REQUESTS}")).do(StopExperimentAction())
        exp.after(SAFETY_TIMEOUT).do(StopExperimentAction())

        env = make_env()
        stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        path = f"data/drift_{env.name}_{platform}_{stamp}.csv"
        print(f"\n=== clock drift on {platform} @ {env.name} ===")
        try:
            exp.run(env, event_listener=DriftListener(path))
        except IoTeaPotError as exc:
            print(f"  SKIPPED {platform}/{env.name}: {exc}")


if __name__ == "__main__":
    main()
