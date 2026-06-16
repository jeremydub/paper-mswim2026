"""MoveNodeAction validation for IoTeaPot (MSWiM'26).

Companion to validation.py: replays one mobility schedule on the two
position-aware backends (Cooja and Renode). A sender at the edge of range is
relocated step by step while a receiver logs arrivals; the per-slice packet
delivery ratio shows that each relocation takes effect.

Application is relative to the paper/ root.
"""

import logging

from ioteapot import Node, setup_logging
from ioteapot.environments import CoojaSimulator, Renode
from ioteapot.errors import IoTeaPotError
from ioteapot.experiment import Experiment, Topology
from ioteapot.experiment.event import MoveNodeAction, StopExperimentAction
from ioteapot.experiment.medium import UnitDiskRadioMedium
from ioteapot.os import contiki
from ioteapot.platforms import CoojaMotePlatform, ZolertiaFireflyPlatform

PING_APP = "app-contiki-ping"


class MovePdr:
    """Packet delivery ratio per 30 s slice: shows MoveNodeAction takes effect."""

    SLICE = 30

    def experiment_started(self, timestamp):
        self.t0 = timestamp
        self.slices = {}

    def serial_message(self, node, timestamp, message, *, clocks=None):
        k = int((timestamp - self.t0) // (self.SLICE * 1000))
        sent, recv = self.slices.get(k, (0, 0))
        self.slices[k] = (sent + message.startswith("S:"),
                          recv + message.startswith("R:"))

    def experiment_ended(self, timestamp):
        print("\nPDR per 30 s slice:")
        for k in sorted(self.slices):
            sent, recv = self.slices[k]
            if sent:
                print(f"  [{k * self.SLICE:3d}-{(k + 1) * self.SLICE:3d}s] "
                      f"sent={sent:3d} recv={recv:3d} PDR={recv / sent:.2f}")


def validation_move_node():
    receiver_app = contiki.Application(app_folder=PING_APP, target="ping")
    sender_app = contiki.Application(
        app_folder=PING_APP, target="ping",
        project_conf=contiki.ProjectConf(SEND_PACKETS=1))

    listener = MovePdr()
    for board, env in [(CoojaMotePlatform, CoojaSimulator()),
                       (ZolertiaFireflyPlatform, Renode())]:
        platform = board()
        receiver = Node(identifier="server", position=(0.0, 0.0, 0.0),
                        application=receiver_app, platform=platform)
        sender = Node(identifier="client", position=(10.0, 0.0, 0.0),
                      application=sender_app, platform=platform)
        topology = Topology(medium=UnitDiskRadioMedium(
            transmitting_range=100, interference_range=0, success_ratio_rx=0.1))
        topology.add_node(receiver)
        topology.add_node(sender)

        exp = Experiment(topology=topology, name=f"move-{platform}")
        # Move the sender away from the client during the experiment, every 30 seconds
        for i in range(1, 10):
            exp.after(30 + i * 30).do(MoveNodeAction(node=sender, x=(i + 1) * 10, y=0))
        exp.after(330).do(StopExperimentAction())

        print(f"\n=== MoveNodeAction on {platform} @ {env.name} ===")
        try:
            exp.run(env, event_listener=listener)
        except IoTeaPotError as exc:
            print(f"  SKIPPED {platform}/{env.name}: {exc}")


def main():
    setup_logging(logging.INFO)
    validation_move_node()


if __name__ == "__main__":
    main()
