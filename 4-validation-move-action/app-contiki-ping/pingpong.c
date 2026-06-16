#include "contiki.h"
#include "lib/random.h"
#include "sys/ctimer.h"
#include "net/ipv6/uip.h"
#include "net/ipv6/uipopt.h"
#include "net/ipv6/uip-ds6.h"
#include "net/ipv6/uip-udp-packet.h"
#include "sys/ctimer.h"
#include <stdio.h>
#include <string.h>

#include "dev/serial-line.h"
#include "net/ipv6/uip-ds6-route.h"
#include "net/ipv6/uip-ds6-nbr.h"

#define UDP_PORT 5678
#define MAX_PAYLOAD_LEN   30

#define DEBUG DEBUG_NONE
#include "net/ipv6/uip-debug.h"

#define DELAY    (30 * CLOCK_SECOND)
#define SEND_INTERVAL   (CLOCK_SECOND>>2)
#define RANDOM_SEND_INTERVAL   (random_rand() % (SEND_INTERVAL))

static struct uip_udp_conn *client_conn;
static uip_ipaddr_t dest_ipaddr;
#if SEND_PACKETS == 1
static struct ctimer periodic_timer;
static int seq_id=0;
#endif

/*---------------------------------------------------------------------------*/
PROCESS(udp_client_process, "Ping Pong");
AUTOSTART_PROCESSES(&udp_client_process);
/*---------------------------------------------------------------------------*/

static void
tcpip_handler(void)
{
  char *appdata;

  if(uip_newdata()) {
    appdata = (char *)uip_appdata;
    appdata[uip_datalen()] = 0;
    printf("R:%02x%02x:%d:%s\n", UIP_IP_BUF->srcipaddr.u8[14], UIP_IP_BUF->srcipaddr.u8[15], UIP_TTL - UIP_IP_BUF->ttl + 1,appdata);
  }
}
/*---------------------------------------------------------------------------*/
#if SEND_PACKETS == 1
static void
send_packet(void *ptr)
{
	char buf[MAX_PAYLOAD_LEN];

	struct ctimer *timer = (struct ctimer *) ptr;
	clock_time_t t = 0;

	t = SEND_INTERVAL;
	seq_id++;
	sprintf(buf, "%d:0", seq_id);
	printf("S:%02x%02x:%d:0\n", dest_ipaddr.u8[14],dest_ipaddr.u8[15], seq_id);

	ctimer_set(timer, t, send_packet, &periodic_timer);
	uip_udp_packet_sendto(client_conn, buf, strlen(buf), &dest_ipaddr, UIP_HTONS(UDP_PORT));
}
#endif
/*---------------------------------------------------------------------------*/
static void
set_global_address(void)
{
  uip_ipaddr_t ipaddr;

  uip_ip6addr(&ipaddr, UIP_DS6_DEFAULT_PREFIX, 0, 0, 0, 0, 0, 0, 0);
  uip_ds6_set_addr_iid(&ipaddr, &uip_lladdr);
  uip_ds6_addr_add(&ipaddr, 0, ADDR_AUTOCONF);

}
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(udp_client_process, ev, data)
{
  PROCESS_BEGIN();
  PROCESS_PAUSE();
  set_global_address();
  uip_ip6addr(&dest_ipaddr, 0xff02, 0, 0, 0, 0, 0, 0, 0x001a);

  printf("Node ID::%02x%02x\n", uip_lladdr.addr[6],uip_lladdr.addr[7]);

  /* new connection with remote host */
  client_conn = udp_new(NULL, UIP_HTONS(UDP_PORT), NULL); 
  if(client_conn == NULL) {
    PRINTF("No UDP connection available, exiting the process!\n");
    PROCESS_EXIT();
  }
  udp_bind(client_conn, UIP_HTONS(UDP_PORT)); 

#if SEND_PACKETS == 1
  ctimer_set(&periodic_timer, DELAY+RANDOM_SEND_INTERVAL, send_packet, &periodic_timer);
#endif

  while(1) {
    PROCESS_YIELD();
    if(ev == tcpip_event) {
      tcpip_handler();
    }
  }

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
