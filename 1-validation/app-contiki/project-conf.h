#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

#define SEND_INTERVAL		  5


/* --- RPL interoperability with the Embassy/smoltcp client (and future RIOT) ---
* rpl-lite is non-storing-only, so use rpl-classic (selected in the Makefile)
* and force storing mode without multicast (MOP 2). */
#define RPL_CONF_MOP                               RPL_MOP_STORING_NO_MULTICAST
/* smoltcp and RIOT only implement OF0 (OCP 0); a node rejects DIOs whose OCP
* differs from its own, so the root must advertise OF0 instead of MRHOF. */
#define RPL_CONF_SUPPORTED_OFS                     {&rpl_of0}
#define RPL_CONF_OF_OCP                            RPL_OCP_OF0

/* --- Route / neighbour table sizing for a network of up to ~70 nodes ---
* Storing mode: every router (the root in particular) keeps one downward route
* per node in its sub-DODAG, so the routing table must hold ~70 entries. The
* neighbour table must cover every next-hop (direct child) a router uses.
* Contiki's defaults are only 16; size both with headroom for the 70-node
* target. (Raises per-node RAM -- ensure the target platform has enough.) */
#define NETSTACK_CONF_MAX_ROUTE_ENTRIES                 ROUTING_CAPACITY
#define NBR_TABLE_CONF_MAX_NEIGHBORS               ROUTING_CAPACITY

/* 802.15.4 PHY/MAC must match the Embassy node (dot15d4 defaults).
* Contiki defaults already are PAN 0xabcd / channel 26 -- set explicitly. */
#define IEEE802154_CONF_PANID                      0x6767
#define IEEE802154_CONF_DEFAULT_CHANNEL            26

// #define LOG_CONF_LEVEL_RPL                         LOG_LEVEL_DBG
// #define LOG_CONF_LEVEL_TCPIP                       LOG_LEVEL_DBG
#define LOG_CONF_LEVEL_IPV6                        LOG_LEVEL_NONE

// #define LOG_CONF_LEVEL_MAC                         LOG_LEVEL_DBG
// #define LOG_CONF_LEVEL_RADIO                       LOG_LEVEL_DBG
// #define LOG_CONF_LEVEL_6LOWPAN                     LOG_LEVEL_DBG
#endif /* PROJECT_CONF_H_ */
