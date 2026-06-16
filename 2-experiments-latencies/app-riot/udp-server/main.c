/*
 * RPL root + UDP server (RIOT).
 *
 * Becomes the DODAG root of an RPL network, listens for UDP datagrams and
 * echoes each one back to its sender.
 * RIOT's GNRC RPL only implements storing mode with OF0, so for Contiki-NG
 * interoperability the Contiki side must be configured for storing mode
 * (rpl-classic) with OF0 (see README.md).
 */

#include <stdio.h>

#include "net/gnrc/netif.h"
#include "net/gnrc/rpl.h"
#include "net/ipv6/addr.h"
#include "net/sock/udp.h"

#define SERVER_PORT      (5678U)
#define RPL_INSTANCE_ID  (1U)
#define DODAG_ID_ADDR    "2001:db8::1"   /* global address of the root = server */
#define PREFIX_LEN       (64U)           /* advertised to the network via DIO/PIO */
#define RECV_BUF_SIZE    (128U)

int main(void)
{
    /* grab the single network interface */
    gnrc_netif_t *netif = gnrc_netif_iter(NULL);
    if (netif == NULL) {
        puts("Error: no network interface found");
        return 1;
    }

    /* configure the DODAG ID as a global address on the interface */
    ipv6_addr_t dodag_id;
    if (ipv6_addr_from_str(&dodag_id, DODAG_ID_ADDR) == NULL) {
        puts("Error: invalid DODAG ID");
        return 1;
    }
    if (gnrc_netif_ipv6_addr_add(netif, &dodag_id, PREFIX_LEN,
                                 GNRC_NETIF_IPV6_ADDRS_FLAGS_STATE_VALID) < 0) {
        puts("Error: could not add global address");
        return 1;
    }

    /* start RPL on the interface and become the DODAG root */
    gnrc_rpl_init(netif->pid);
    if (gnrc_rpl_root_init(RPL_INSTANCE_ID, &dodag_id, false, false) == NULL) {
        puts("Error: could not initialize RPL root");
        return 1;
    }
    printf("RPL root started (DODAG ID / server address: %s)\n", DODAG_ID_ADDR);

    /* open the UDP server socket */
    sock_udp_ep_t local = SOCK_IPV6_EP_ANY;
    local.port = SERVER_PORT;

    sock_udp_t sock;
    if (sock_udp_create(&sock, &local, NULL, 0) < 0) {
        puts("Error: could not create UDP socket");
        return 1;
    }
    printf("UDP server listening on port %u\n", SERVER_PORT);

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
        printf("Received request \"%s\" from [%s]:%u\n", buf, addr_str, remote.port);

        /* echo the same payload back to the client */
        ssize_t snd = sock_udp_send(&sock, buf, res, &remote);
        if (snd < 0) {
            printf("Error: could not send reply (%d)\n", (int)snd);
        }
        else {
            // printf("Sent response \"%s\" to [%s]:%u\n", buf, addr_str,
            //        remote.port);
        }
    }

    return 0; /* never reached */
}
