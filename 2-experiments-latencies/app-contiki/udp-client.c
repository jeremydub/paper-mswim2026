#include "contiki.h"
#include "dev/serial-line.h"
#include "net/routing/routing.h"
#include "project-conf.h"
#include "random.h"
#include "net/netstack.h"
#include "net/ipv6/simple-udp.h"
#include <stdint.h>
#include <inttypes.h>

#include "sys/log.h"
#define LOG_MODULE "App"
#define LOG_LEVEL LOG_LEVEL_INFO

#define WITH_SERVER_REPLY  1
#define UDP_CLIENT_PORT	8765
#define UDP_SERVER_PORT	5678


static struct simple_udp_connection udp_conn;
static uint32_t rx_count = 0;

/*---------------------------------------------------------------------------*/
/* CPU burn used to study how on-node computation perturbs the send cadence.
 *
 * do_work(n) runs an n-step integer recurrence (xor / multiply / rotate /
 * add). Each step depends on the previous one, so the optimiser cannot fold
 * it to a closed form; the accumulator is seeded from, and stored back into,
 * a volatile sink, so the work can neither be precomputed nor eliminated as
 * dead code -- on real hardware it consumes real CPU time, while under Cooja's
 * Cooja Mote it advances no simulated time. Integer-only (no FPU dependency).
 * Compiles identically for the RIOT client; see its main.c. */
static volatile uint32_t do_work_sink;

static uint32_t
do_work(uint32_t n)
{
  uint32_t acc = 0x12345678u ^ do_work_sink;
  for(uint32_t i = 0; i < n; i++) {
    acc ^= i;
    acc *= 2654435761u;                  /* Knuth multiplicative hash */
    acc = (acc << 13) | (acc >> 19);     /* rotate left 13 */
    acc += 0x9E3779B9u;                  /* golden-ratio increment */
  }
  do_work_sink = acc;                    /* volatile store defeats DCE */
  return acc;
}

/*---------------------------------------------------------------------------*/
PROCESS(udp_client_process, "UDP client");
AUTOSTART_PROCESSES(&udp_client_process);
/*---------------------------------------------------------------------------*/
static void
udp_rx_callback(struct simple_udp_connection *c,
         const uip_ipaddr_t *sender_addr,
         uint16_t sender_port,
         const uip_ipaddr_t *receiver_addr,
         uint16_t receiver_port,
         const uint8_t *data,
         uint16_t datalen)
{

  LOG_INFO("Received response '%.*s' from ", datalen, (char *) data);
  LOG_INFO_6ADDR(sender_addr);
#if LLSEC802154_CONF_ENABLED
  LOG_INFO_(" LLSEC LV:%d", uipbuf_get_attr(UIPBUF_ATTR_LLSEC_LEVEL));
#endif
  LOG_INFO_("\n");
  rx_count++;
}
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(udp_client_process, ev, data)
{
  static struct etimer periodic_timer;
  static char str[32];
  uip_ipaddr_t dest_ipaddr;
  static uint32_t request_id = 1;

  PROCESS_BEGIN();

  /* Initialize UDP connection */
  simple_udp_register(&udp_conn, UDP_CLIENT_PORT, NULL,
                      UDP_SERVER_PORT, udp_rx_callback);
#if CONTIKI_TARGET_Z1
  etimer_set(&periodic_timer, 30 * CLOCK_SECOND);
  PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
#elif SEND_DELAY == -1
  // We first wait for a "start-network" command before Initializing
  // RPL as a root.
  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(ev == serial_line_event_message && data != NULL);

    if(strcmp((const char *)data, "send-data") == 0) {
      printf("Received command 'send-data'\n");
      break;
    } else {
      printf("Unknown command: '%s'\n", (const char *)data);
    }
  }
#else
  etimer_set(&periodic_timer, SEND_DELAY * CLOCK_SECOND);
  PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
#endif
  

  etimer_set(&periodic_timer, random_rand() % (SEND_INTERVAL*CLOCK_SECOND));
  while(request_id <= N_REQUESTS) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    if(NETSTACK_ROUTING.node_is_reachable() &&
        NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {

      /* Add some jitter */
      etimer_set(&periodic_timer, (SEND_INTERVAL * CLOCK_SECOND)
        - CLOCK_SECOND + (random_rand() % (2 * CLOCK_SECOND)));
      /* Send to DAG root */
      LOG_INFO("Sending request %"PRIu32" to ", request_id);
      LOG_INFO_6ADDR(&dest_ipaddr);
      LOG_INFO_("\n");
      snprintf(str, sizeof(str), "hello %" PRIu32 "", request_id);
      simple_udp_sendto(&udp_conn, str, strlen(str), &dest_ipaddr);
      request_id++;
      /* Emulate CPU-bound per-sample computation. */
      do_work(DO_WORK_ITERATIONS);
    } else {
      LOG_INFO("Not reachable yet\n");
    }

  }

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
