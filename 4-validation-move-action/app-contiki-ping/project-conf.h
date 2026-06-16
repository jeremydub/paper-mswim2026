#undef NETSTACK_CONF_RDC
#define NETSTACK_CONF_RDC nullrdc_driver

#define SEND_PACKETS                      0

#if NETSTACK_CONF_RDC == nullrdc_driver
#undef NULLRDC_CONF_802154_AUTOACK
#define NULLRDC_CONF_802154_AUTOACK       1
#define NULLRDC_CONF_SEND_802154_ACK	  1
#endif /* NETSTACK_CONF_RDC == nullrdc_driver */
