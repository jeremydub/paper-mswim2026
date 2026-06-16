# RPL client + UDP sender

APPLICATION = rpl_udp_client

# Default board; override on the command line, e.g. `make BOARD=samr21-xpro`.
# For over-the-air interop with Contiki-NG use a real IEEE 802.15.4 board.
BOARD ?= native

RIOTBASE ?= $(CURDIR)/../../../dependencies/RIOT

# --- GNRC network stack: IPv6 *router* is required for RPL ---
USEMODULE += netdev_default
USEMODULE += auto_init_gnrc_netif
USEMODULE += gnrc_ipv6_router_default
USEMODULE += gnrc_icmpv6_echo
USEMODULE += gnrc_sock_udp

# --- RPL (RIOT supports storing mode + OF0 only) ---
USEMODULE += gnrc_rpl

ROUTING_CAPACITY ?= 70
# Storing mode: every router holds a downward route per node in its sub-DODAG,
# so a node just below the root can hold almost the whole network. Size the NIB
# forwarding table (off-link entries) and neighbour cache for the ~70-node
# target, matching the server. Defaults are only 8/4.
CFLAGS += -DCONFIG_GNRC_IPV6_NIB_NUMOF=$(ROUTING_CAPACITY)
CFLAGS += -DCONFIG_GNRC_IPV6_NIB_OFFL_NUMOF=$(ROUTING_CAPACITY)


# --- PRNG: per-node seed + startup/send-interval jitter ---
USEMODULE += random

# --- UART standard input: blocking read of the "send-data" command ---
USEMODULE += stdin

# Join the DODAG without waiting for a DODAG_CONF; improves interop robustness.
CFLAGS += -DCONFIG_GNRC_RPL_DODAG_CONF_OPTIONAL_ON_JOIN

# --- Radio settings must match the Contiki-NG nodes ---
# RIOT defaults to PAN ID 0x0023 / channel 26. Uncomment and adjust so both
# stacks share the same PAN ID and channel.
CFLAGS += -DCONFIG_IEEE802154_DEFAULT_PANID=0x6767
# CFLAGS += -DCONFIG_IEEE802154_DEFAULT_CHANNEL=26

# --- CPU-load ---------------------------------------------------
# Iterations of the do_work() integer mix run before each UDP send, to
# emulate CPU-bound per-sample computation. 0 keeps the baseline. Override
# on the command line, e.g. `make DO_WORK_ITERATIONS=20000`.
DO_WORK_ITERATIONS ?= 0
N_REQUESTS ?= 5
CFLAGS += -DDO_WORK_ITERATIONS=$(DO_WORK_ITERATIONS)
CFLAGS += -DN_REQUESTS=$(N_REQUESTS)

# --- Application data
SEND_DELAY ?= -1
CFLAGS += -DSEND_DELAY=$(SEND_DELAY)

# --- Experiment feature gates
GNRC_IPV6_DEBUG ?= 0
CC2538_RF_RENODE_FIX ?= 0
CFLAGS += -DGNRC_IPV6_DEBUG=$(GNRC_IPV6_DEBUG)
CFLAGS += -DCC2538_RF_RENODE_FIX=$(CC2538_RF_RENODE_FIX)

ifeq ($(CC2538_RF_RENODE_FIX),1)
	# --- timers ---
	USEMODULE += ztimer
	USEMODULE += ztimer_msec
	# ---- Renode cc2538 workaround --------------------------------------
	CFLAGS += -DCONFIG_IEEE802154_CSMA_BACKOFFS=0
	CFLAGS += -DCONFIG_IEEE802154_DEFAULT_CSMA_CA_MIN=0
	CFLAGS += -DCONFIG_IEEE802154_DEFAULT_CSMA_CA_RETRIES=-1
	USEMODULE += netdev_ieee802154_submac
endif

# ---- Wire-level interop with Contiki-NG ----------------------------
# Pin the 802.15.4 channel to 26 (matches Contiki / Wireshark capture)
CFLAGS += -DCONFIG_IEEE802154_DEFAULT_CHANNEL=26


DEVELHELP ?= 1
QUIET ?= 1

include $(RIOTBASE)/Makefile.include
