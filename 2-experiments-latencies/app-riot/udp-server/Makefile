# RPL root + UDP server

APPLICATION = rpl_udp_server

# Default board; override on the command line, e.g. `make BOARD=samr21-xpro`.
# For over-the-air interop with Contiki-NG use a real IEEE 802.15.4 board.
BOARD ?= native

RIOTBASE ?= $(CURDIR)/../../../dependencies/RIOT

# --- GNRC network stack: IPv6 *router* is required for RPL forwarding ---
USEMODULE += netdev_default
USEMODULE += auto_init_gnrc_netif
USEMODULE += gnrc_ipv6_router_default
USEMODULE += gnrc_icmpv6_echo
USEMODULE += gnrc_sock_udp

# --- RPL (RIOT supports storing mode + OF0 only) ---
USEMODULE += gnrc_rpl


# Storing mode: the root keeps a downward route per node, so size the NIB to at
# least the number of nodes in the network. Target topology is ~70 nodes, so
# allow headroom (was 16).
CFLAGS += -DCONFIG_GNRC_IPV6_NIB_NUMOF=80
CFLAGS += -DCONFIG_GNRC_IPV6_NIB_OFFL_NUMOF=80

# --- Radio settings must match the Contiki-NG nodes ---
# RIOT defaults to PAN ID 0x0023 / channel 26. Uncomment and adjust so both
# stacks share the same PAN ID and channel.
CFLAGS += -DCONFIG_IEEE802154_DEFAULT_PANID=0x6767
# CFLAGS += -DCONFIG_IEEE802154_DEFAULT_CHANNEL=26

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
