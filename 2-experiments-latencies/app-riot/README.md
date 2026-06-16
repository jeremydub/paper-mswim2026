/* storing mode, no multicast (matches RIOT's default MOP) */
#define RPL_CONF_MOP                 RPL_MOP_STORING_NO_MULTICAST
#define RPL_CONF_WITH_STORING        1
#define RPL_CONF_WITH_NON_STORING    0

/* OF0 - RIOT only implements OF0 (RFC 6552) */
#define RPL_CONF_OF_OCP              RPL_OCP_OF0
#define RPL_CONF_SUPPORTED_OFS       {&rpl_of0}

/* RIOT does not handle the RPL Hop-by-Hop option on data packets */
#define RPL_CONF_INSERT_HBH_OPTION   0

/* root must hold a route per node (storing mode); >= network size */
#define NETSTACK_MAX_ROUTE_ENTRIES   16
