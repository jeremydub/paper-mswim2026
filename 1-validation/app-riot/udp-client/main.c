/*
 * RPL client + UDP sender (RIOT).
 *
 * Joins the RPL DODAG advertised by the root (discovered automatically from
 * received DIOs), waits for a "send-data" command on the UART, waits a small
 * random startup delay, then sends a "hello N" datagram to the server roughly
 * every 5 s (jittered to [4, 5) s). A dedicated receiver thread prints each
 * reply echoed back by the server.
 *
 * Storing mode + OF0 only, for Contiki-NG interop (see README.md).
 */

#include <stdio.h>
#include <string.h>

#include "net/gnrc/netif.h"
#include "net/gnrc/rpl.h"
#include "net/ipv6/addr.h"
#include "net/sock/udp.h"
#include "ztimer.h"
#include "random.h"
#include "thread.h"
#include "stdio_base.h"
#include "net/gnrc/ipv6/nib/ft.h"
#include "net/gnrc/ipv6/nib/nc.h"

#define SERVER_ADDR        "2001:db8::1"     /* RPL root / UDP server address */
#define SERVER_PORT        (5678U)
#define CLIENT_PORT        (8765U)
#define SEND_INTERVAL_MS   (10U * 1000U)
#define PAYLOAD_SIZE       (32U)
#define RECV_BUF_SIZE      (128U)

/* shared between the send loop (main) and the receiver thread */
static sock_udp_t sock;
static char recv_thread_stack[THREAD_STACKSIZE_DEFAULT +
                              THREAD_EXTRA_STACKSIZE_PRINTF];

/* CPU burn used to study how on-node computation perturbs the send cadence.
 *
 * do_work(n) runs an n-step integer recurrence (xor / multiply / rotate /
 * add). Each step depends on the previous one, so the optimiser cannot fold
 * it to a closed form; the accumulator is seeded from, and stored back into,
 * a volatile sink, so the work can neither be precomputed nor eliminated as
 * dead code -- on real hardware it consumes real CPU time, while under
 * emulation it advances no simulated time. Integer-only (no FPU dependency).
 * Identical body to the Contiki client's do_work(). */
static volatile uint32_t do_work_sink;
 
static uint32_t do_work(uint32_t n)
{
    uint32_t acc = 0x12345678u ^ do_work_sink;
    for (uint32_t i = 0; i < n; i++) {
        acc ^= i;
        acc *= 2654435761u;                 /* Knuth multiplicative hash */
        acc = (acc << 13) | (acc >> 19);    /* rotate left 13 */
        acc += 0x9E3779B9u;                 /* golden-ratio increment */
    }
    do_work_sink = acc;                     /* volatile store defeats DCE */
    return acc;
}

/* Receiver thread: blocks on the UDP socket and prints every reply as it
 * arrives, mirroring the Contiki-NG udp_rx_callback. */
static void *recv_thread(void *arg)
{
    (void)arg;
    char buf[RECV_BUF_SIZE];
    while (1) {
        sock_udp_ep_t remote;
        ssize_t res = sock_udp_recv(&sock, buf, sizeof(buf) - 1,
                                    SOCK_NO_TIMEOUT, &remote);
        if (res < 0) {
            continue;
        }
        buf[res] = '\0';
        char addr_str[IPV6_ADDR_MAX_STR_LEN];
        ipv6_addr_to_str(addr_str, (ipv6_addr_t *)&remote.addr.ipv6,
                         sizeof(addr_str));
        printf("Received response \"%s\" from [%s]:%u\n",
               buf, addr_str, remote.port);
    }
    return NULL;
}

/* Block until the "send-data" line arrives on the UART. stdio_read() suspends
 * the thread until input is available (isrpipe-backed), so there is no busy
 * wait. */
static void wait_for_send_data_command(void)
{
    char line[32];
    size_t pos = 0;
    puts("Waiting for 'send-data' command on UART...");
    while (1) {
        char c;
        if (stdio_read(&c, 1) <= 0) {
            continue;
        }
        if (c == '\n' || c == '\r') {
            if (pos == 0) {
                continue;               /* ignore empty lines */
            }
            line[pos] = '\0';
            if (strcmp(line, "send-data") == 0) {
                puts("Received command 'send-data'");
                return;
            }
            printf("Unknown command: '%s'\n", line);
            pos = 0;
        }
        else if (pos < sizeof(line) - 1) {
            line[pos++] = c;
        }
        else {
            pos = 0;                     /* overflow: drop and resync */
        }
    }
}

int main(void)
{
    /* grab the single network interface */
    gnrc_netif_t *netif = gnrc_netif_iter(NULL);
    if (netif == NULL) {
        puts("Error: no network interface found");
        return 1;
    }

    /* Seed the PRNG from this node's L2 (EUI-64) address so the post-command
     * startup jitter below -- and RPL's trickle timers -- differ per node, the
     * way Contiki seeds its PRNG per node. */
    uint32_t seed = 0;
    for (unsigned i = 0; i < netif->l2addr_len; i++) {
        seed = (seed << 8) ^ netif->l2addr[i];
    }
    random_init(seed);

    /* start RPL: the node joins the DODAG on the first DIO it hears and
     * autoconfigures a global address from the advertised prefix */
    gnrc_rpl_init(netif->pid);

    // /* --- TEST: static global addr + default route, bypassing RPL PIO --- */
    // ipv6_addr_t my_addr;
    // ipv6_addr_from_str(&my_addr, "2001:db8::2");
    // gnrc_netif_ipv6_addr_add(netif, &my_addr, 64,
    //                          GNRC_NETIF_IPV6_ADDRS_FLAGS_STATE_VALID);


    // /* Server L2 (EUI-64) - matches the src bytes in the radio log: 00 00 00 00 01 00 00 00 */
    // static const uint8_t server_l2[] = { 0x00,0x00,0x00,0x00,0x01,0x00,0x00,0x00 };

    // ipv6_addr_t server_ll;
    // ipv6_addr_from_str(&server_ll, "fe80::200:1:0:0");   /* CONFIRM from server log */

    // gnrc_ipv6_nib_nc_set(&server_ll, netif->pid, server_l2, sizeof(server_l2));

    // ipv6_addr_t defroute;
    // ipv6_addr_from_str(&defroute, "::");
    // gnrc_ipv6_nib_ft_add(&defroute, 0, &server_ll, netif->pid, 0);

    puts("RPL initialized, joining the DODAG...");

    /* resolve the server endpoint once */
    sock_udp_ep_t remote = { .family = AF_INET6, .port = SERVER_PORT };
    if (ipv6_addr_from_str((ipv6_addr_t *)&remote.addr.ipv6, SERVER_ADDR) == NULL) {
        puts("Error: invalid server address");
        return 1;
    }

    /* bind a UDP socket to a fixed local port so the server's reply reaches
     * us, then start the receiver thread that listens on it */
    sock_udp_ep_t local = SOCK_IPV6_EP_ANY;
    local.port = CLIENT_PORT;
    if (sock_udp_create(&sock, &local, NULL, 0) < 0) {
        puts("Error: could not create UDP socket");
        return 1;
    }
    thread_create(recv_thread_stack, sizeof(recv_thread_stack),
                  THREAD_PRIORITY_MAIN - 1, 0, recv_thread, NULL, "udp_rx");
    
    // ztimer_sleep(ZTIMER_MSEC, SEND_DELAY * 1000U);
    // uint32_t startup_delay_ms = random_uint32_range(0, SEND_INTERVAL_MS);
    // printf("Startup delay: %u ms\n", (unsigned)startup_delay_ms);
    // ztimer_sleep(ZTIMER_MSEC, startup_delay_ms);
    wait_for_send_data_command();


    ztimer_now_t last_wakeup = ztimer_now(ZTIMER_MSEC);
    unsigned n = 1;
    while (n <= N_REQUESTS) {

        char payload[PAYLOAD_SIZE];
        int len = snprintf(payload, sizeof(payload), "hello %u", n);

        printf("Sending request %u to [%s]:%u\n", n, SERVER_ADDR, SERVER_PORT);
        ssize_t res = sock_udp_send(&sock, payload, len, &remote);
        if (res < 0) {
            printf("Error: sending request %u failed (%d)\n", n, (int)res);
        }
        /* Emulate CPU-bound per-sample computation before transmitting. */
        do_work(DO_WORK_ITERATIONS);

        n++;
        /* Jittered cadence in [SEND_INTERVAL-1s, SEND_INTERVAL) = [4, 5) s,
         * matching the Contiki client's per-message jitter
         * `(SEND_INTERVAL*CLOCK_SECOND) - CLOCK_SECOND + random_rand()%CLOCK_SECOND`.
         * periodic_wakeup advances last_wakeup by this amount, so the long-run
         * rate stays drift-free while individual intervals vary. */
        uint32_t period_ms = (SEND_INTERVAL_MS - 1000U)
                           + random_uint32_range(0, 2000U);
        ztimer_periodic_wakeup(ZTIMER_MSEC, &last_wakeup, period_ms);
    }

    return 0; /* never reached */
}
