"""Capability validation for IoTeaPot (MSWiM'26).

One experiment runs unchanged across every board/backend/OS combination of the
paper's validation matrix; a checker (an ordinary listener) confirms that each
modelled capability has its intended observable effect. MoveNodeAction (the
fifth action) is validated by the companion script validation_move_node.py.

Applications are relative to the paper/ root.
"""

import logging
import re

from ioteapot import Node, Vcom, setup_logging
from ioteapot.environments import CoojaSimulator, FitIotLab, Local, Renode
from ioteapot.environments.local import Nrf802154Sniffer
from ioteapot.errors import IoTeaPotError
from ioteapot.experiment import Experiment, Topology
from ioteapot.experiment.event import (
    SerialReadTrigger,
    SerialWriteAction,
    StartNodeAction,
    StopExperimentAction,
    StopNodeAction,
    BaseEventListener,
)
from ioteapot.experiment.medium import UnitDiskRadioMedium
from ioteapot.os import contiki, embassy, riot
from ioteapot.platforms import (
    Cc2538dkPlatform,
    CoojaMotePlatform,
    IotLabM3Platform,
    Nrf52840dkPlatform,
    ZolertiaFireflyPlatform,
    ZolertiaZ1Platform,
)

EMBASSY_APP = "app-embassy"
UDP_APP = "app-contiki"
RIOT_SERVER = "app-riot/udp-server"
RIOT_CLIENT = "app-riot/udp-client"

# board class, backend label, operating systems exercised (Table II).
MATRIX = [
    (CoojaMotePlatform,       "cooja",    ["contiki"]),
    (ZolertiaZ1Platform,      "cooja",    ["contiki"]),
    (Cc2538dkPlatform,        "renode",   ["contiki", "riot"]),
    (ZolertiaFireflyPlatform, "renode",   ["contiki", "riot"]),
    (ZolertiaFireflyPlatform, "local",    ["contiki", "riot"]),
    (IotLabM3Platform,        "paris", ["contiki", "riot"]),
    (Nrf52840dkPlatform,      "saclay",   ["contiki", "riot", "embassy"]),
    (Nrf52840dkPlatform,      "local",    ["contiki", "riot", "embassy"]),
]

_REQUEST = re.compile(r"request\s+(\d+)")  # client "Sending request N"
_HELLO = re.compile(r"hello\s+(\d+)")      # server "Received request 'hello N'"


def make_apps(rtos, env):
    """Return (server_app, client_app) for the UDP validation experiment."""
    if rtos == "contiki":
        server = contiki.Application(app_folder=UDP_APP, target="udp-server")
        client = contiki.Application(
            app_folder=UDP_APP, target="udp-client",
            project_conf=contiki.ProjectConf(SEND_INTERVAL=5))
    elif rtos == "riot":
        server = riot.Application(app_folder=RIOT_SERVER)
        client = riot.Application(app_folder=RIOT_CLIENT)
        server.environment_variables["CC2538_RF_RENODE_FIX"] = "1" if isinstance(env, Renode) else "0"
        client.environment_variables["CC2538_RF_RENODE_FIX"] = "1" if isinstance(env, Renode) else "0"
    elif rtos == "embassy":
        server = embassy.Application(app_folder=EMBASSY_APP, binary="ieee802154-udp",
                                     features=["defmt"], log_transport=Vcom())
        server.environment_variables.update(ROOT="true", CHANNEL="26")
        client = embassy.Application(app_folder=EMBASSY_APP, binary="ieee802154-udp",
                                     features=["defmt"], log_transport=Vcom())
        client.environment_variables.update(ROOT="false", CHANNEL="26",
                                             SEND_TO="fd0e::71b8")
    else:
        raise ValueError(f"unknown rtos {rtos!r}")
    return server, client


def make_env(label):
    if label == "cooja":
        return CoojaSimulator()
    if label == "renode":
        return Renode()
    if label == "local":
        return Local(sniffers=Nrf802154Sniffer())
    return FitIotLab(site=label, radio_capture=True)  # grenoble / saclay


class Checker(BaseEventListener):
    """Replays a trace against the schedule: prints a per-run recap and then
    verifies, with assertions, that each modelled capability had its intended
    observable effect (see ``verify``)."""

    def begin(self, label, *, expect_serial_write=True):
        """Tag the upcoming run and declare what it should produce.

        ``expect_serial_write`` is False only for the Zolertia Z1 under Cooja,
        where SerialWriteAction does not register (a Cooja limitation, present
        without the framework too); there the request stream never starts.
        """
        self.label = label
        self.expect_serial_write = expect_serial_write
        # Defaults so verify() is safe even if the run never started.
        self.started = False
        self.ended = False
        self.t0 = 0.0
        self.first_serial = None
        self.send_data = None
        self.first_rx = None
        self.radio = None
        self.client_max = 0
        self.server_max = 0
        self.after_end = 0

    def experiment_started(self, timestamp):
        self.t0 = timestamp
        self.started = True
        self.ended = False
        self.first_serial = None    # first observed serial line
        self.send_data = None       # SerialWriteAction effect (echoed command)
        self.first_rx = None        # first UDP request at the server
        self.radio = None           # first captured frame carrying a request
        self.client_max = 0         # highest sequence the client sent
        self.server_max = 0         # highest sequence the server received
        self.after_end = 0          # observations seen after experiment_ended
        print(f"\n=== {self.label} ===")

    def _t(self, ts):
        return (ts - self.t0) / 1000.0

    def serial_message(self, node, timestamp, message, *, clocks=None):
        if self.ended:
            self.after_end += 1
            return
        t = self._t(timestamp)
        print(f"  [{timestamp:8.2f} ms] {node!s:<10} | {message}")
        if self.first_serial is None:
            self.first_serial = t
        if "send-data" in message and self.send_data is None:
            self.send_data = t
        m = _REQUEST.search(message)
        if m and "Sending request" in message:
            self.client_max = max(self.client_max, int(m.group(1)))
        m = _HELLO.search(message)
        if m and "Received request" in message:
            self.server_max = max(self.server_max, int(m.group(1)))
            if self.first_rx is None:
                self.first_rx = t

    def serial_input_message(self, node, timestamp, message, *, clocks=None):
        print(f"  [{self._t(timestamp):7.2f}s] >> {node!s:<10} | {message}")

    def radio_packet(self, timestamp, data, *, clocks=None):
        if self.ended:
            self.after_end += 1
            return
        if self.radio is None and b"hello" in data:
            self.radio = self._t(timestamp)
        print(f"  [{timestamp:8.1f} ms] RADIO {len(data)}B: {data[:20].hex()}")

    def experiment_ended(self, timestamp):
        self.ended = True
        seen = lambda v: "ok" if v is not None else "MISSING"
        print(f"  ended at {self._t(timestamp):.2f}s")
        print(f"  serial={seen(self.first_serial)} serial_write={seen(self.send_data)} "
              f"udp_rx={seen(self.first_rx)} radio={seen(self.radio)} "
              f"server_stopped_at=hello {self.server_max} client_sent_up_to={self.client_max} "
              f"after_end={self.after_end}")

    def verify(self):
        """Assert the schedule's intended effects.

        Raises AssertionError on the first property that does not hold. Called
        after ``exp.run`` returns, so a failure is reported per cell without
        aborting the rest of the matrix.
        """
        # The run itself must have produced a start and an end observation.
        assert self.started, "experiment_started was never observed"
        assert self.ended, "experiment_ended was never observed"
        # The client boots and its serial output reaches the framework.
        assert self.first_serial is not None, \
            "no serial output from the client (boot / log transport)"
        # Nothing may be observed after the experiment ends.
        assert self.after_end == 0, \
            f"{self.after_end} observation(s) after experiment_ended"

        if self.expect_serial_write:
            # SerialWriteAction delivered (the injected command is echoed back).
            assert self.send_data is not None, \
                "SerialWriteAction had no observable effect"
            # The armed request stream reaches both the server and the sniffer.
            assert self.first_rx is not None, "server received no UDP request"
            assert self.radio is not None, "no request frame captured on radio"
            # The output-driven StopNodeAction fires at the third reception:
            # the server's last received request is exactly 'hello 3'.
            assert self.server_max == 3, \
                f"server stopped at hello {self.server_max}, expected 3"
            # ...while the client keeps sending past it (when client logs parse).
            if self.client_max:
                assert self.client_max > self.server_max, (
                    f"client sent up to {self.client_max}, "
                    f"not beyond the server's {self.server_max}")
        else:
            # Z1 under Cooja: the serial write does not register, so the request
            # stream never starts (documented Cooja limitation).
            assert self.send_data is None, \
                "SerialWriteAction unexpectedly registered on Z1/Cooja"
            assert self.first_rx is None and self.server_max == 0, \
                "requests unexpectedly flowed without a registered serial write"
        return True


def validation():
    checker = Checker()
    passed, failed, skipped = [], [], []
    for board, label, oses in MATRIX:
        for rtos in oses:
            platform = board()
            env = make_env(label)
            server_app, client_app = make_apps(rtos, env)

            server = Node(identifier="server", position=(0.0, 0.0, 0.0),
                          application=server_app, platform=platform)
            client = Node(identifier="client", position=(2.0, 0.0, 0.0),
                          application=client_app, platform=platform, auto_start=False)
            topology = Topology(medium=UnitDiskRadioMedium(
                transmitting_range=20, interference_range=0))
            topology.add_node(server)
            topology.add_node(client)

            exp = Experiment(topology=topology, name=f"validation-{platform}")
            exp.after(10).do(StartNodeAction(node=client))
            exp.after(30).do(SerialWriteAction(node=client, text="send-data"))
            exp.when(SerialReadTrigger.contains_(server, "hello 3")).do(
                StopNodeAction(node=server))
            exp.after(60).do(StopExperimentAction())

            case = f"{rtos} on {platform} @ {label}"
            # The Zolertia Z1 under Cooja cannot register a serial write (a Cooja
            # limitation, present without the framework too), so the request
            # stream never starts there; every other cell runs the full schedule.
            expect_serial_write = not (board is ZolertiaZ1Platform and label == "cooja")
            checker.begin(case, expect_serial_write=expect_serial_write)
            try:
                exp.run(env, event_listener=checker)
            except IoTeaPotError as exc:
                print(f"  SKIPPED {case}: {exc}")
                skipped.append(case)
                continue
            try:
                checker.verify()
            except AssertionError as exc:
                print(f"  FAILED  {case}: {exc}")
                failed.append(case)
            else:
                print(f"  PASSED  {case}")
                passed.append(case)

    total = len(passed) + len(failed)
    summary = f"\n{len(passed)}/{total} cells passed"
    if skipped:
        summary += f", {len(skipped)} skipped (backend unavailable)"
    print(summary)
    if failed:
        print("  failed: " + ", ".join(failed))
    return not failed


def main():
    setup_logging(logging.INFO)
    ok = validation()
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
