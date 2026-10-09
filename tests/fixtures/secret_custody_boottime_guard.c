/* Fixed disposable-guest TC experiment. Not a live host installer.
 * Immutable CLOCK_BOOTTIME deadline, no map, timer, refresh or resident loader.
 * Narrow wire profile: plain Ethernet, IPv4 without options/fragments, IPv6
 * without extensions. After expiry unknown/malformed headers fail closed;
 * ARP, IPv4 ICMP, IPv6 ICMP and non-443 TCP remain outside this gate's scope.
 * The independent existing nft qualification policy is retained unchanged.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/pkt_cls.h>
#include <linux/pkt_sched.h>
#include <linux/rtnetlink.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static void die(const char *why) { perror(why); exit(2); }
static void text(const char *path, char *buf, size_t size) {
    FILE *f = fopen(path, "r");
    if (!f || !fgets(buf, size, f)) die("GUEST_IDENTITY_READ");
    fclose(f);
}
static void guard(void) {
    /* Refuse normal host invocation before any bpf/netlink syscall. */
    if (getppid() != 1 || getuid() != 0) {
        fputs("BOOTTIME_GUEST_CHILD_REQUIRED\n", stderr); exit(2);
    }
    char buf[2048];
    text("/proc/cmdline", buf, sizeof(buf));
    if (!strstr(buf, " kc_boottime_guard=1 ")) die("BOOTTIME_GUEST_OPT_IN");
    text("/sys/class/dmi/id/sys_vendor", buf, sizeof(buf));
    if (strcmp(buf, "QEMU\n")) die("BOOTTIME_QEMU_REQUIRED");
    struct if_nameindex *all = if_nameindex();
    int count = 0;
    if (!all) die("GUEST_INTERFACES_REQUIRED");
    for (struct if_nameindex *p = all; p->if_index; p++, count++)
        if (strcmp(p->if_name, "lo") && strcmp(p->if_name, "host0")) die("EXTERNAL_INTERFACE_FORBIDDEN");
    if_freenameindex(all);
    if (count != 2) die("FIXED_GUEST_LINK_REQUIRED");
}

enum { ACCEPT, DROP, IPV4, IPV6, PORTS, LABEL_COUNT };
static struct bpf_insn ins[128];
static int used, labels[LABEL_COUNT], fixpos[32], fixlabel[32], fixes;
static void emit(unsigned char code, int dst, int src, int off, int imm) {
    if (used >= 128) die("PROGRAM_BOUND");
    ins[used++] = (struct bpf_insn){.code=code, .dst_reg=dst, .src_reg=src, .off=off, .imm=imm};
}
static void mov(int dst, int imm) { emit(BPF_ALU64|BPF_MOV|BPF_K, dst, 0, 0, imm); }
static void reg(int dst, int src) { emit(BPF_ALU64|BPF_MOV|BPF_X, dst, src, 0, 0); }
static void branch(int op, int dst, int imm, int label) {
    if (fixes >= 32) die("BRANCH_BOUND");
    fixpos[fixes] = used; fixlabel[fixes++] = label;
    emit(BPF_JMP|op|BPF_K, dst, 0, 0, imm);
}
static void load(int offset, int length) {
    reg(1, 6); mov(2, offset); reg(3, 10);
    emit(BPF_ALU64|BPF_ADD|BPF_K, 3, 0, 0, -64); mov(4, length);
    emit(BPF_JMP|BPF_CALL, 0, 0, 0, BPF_FUNC_skb_load_bytes);
    branch(BPF_JNE, 0, 0, DROP);
}
static void byte(int offset) { emit(BPF_LDX|BPF_MEM|BPF_B, 0, 10, offset, 0); }
static void half(int offset) { emit(BPF_LDX|BPF_MEM|BPF_H, 0, 10, offset, 0); }
static int program(uint64_t deadline) {
    reg(6, 1);
    emit(BPF_JMP|BPF_CALL, 0, 0, 0, BPF_FUNC_ktime_get_boot_ns);
    emit(BPF_LD|BPF_DW|BPF_IMM, 7, 0, 0, (uint32_t)deadline);
    emit(0, 0, 0, 0, deadline >> 32);
    fixpos[fixes] = used; fixlabel[fixes++] = ACCEPT;
    emit(BPF_JMP|BPF_JLT|BPF_X, 0, 7, 0, 0);
    load(0, 14); half(-52);
    branch(BPF_JEQ, 0, htons(ETH_P_ARP), ACCEPT);
    branch(BPF_JEQ, 0, htons(ETH_P_IP), IPV4);
    branch(BPF_JEQ, 0, htons(ETH_P_IPV6), IPV6);
    branch(BPF_JA, 0, 0, DROP);
    labels[IPV4] = used;
    load(14, 20); byte(-64); branch(BPF_JNE, 0, 0x45, DROP);
    half(-58); emit(BPF_ALU64|BPF_AND|BPF_K, 0, 0, 0, htons(0x3fff));
    branch(BPF_JNE, 0, 0, DROP);
    byte(-55); branch(BPF_JEQ, 0, IPPROTO_ICMP, ACCEPT);
    branch(BPF_JNE, 0, IPPROTO_TCP, DROP);
    load(34, 4); branch(BPF_JA, 0, 0, PORTS);
    labels[IPV6] = used;
    load(14, 40); byte(-64); emit(BPF_ALU64|BPF_AND|BPF_K, 0, 0, 0, 0xf0);
    branch(BPF_JNE, 0, 0x60, DROP);
    byte(-58); branch(BPF_JEQ, 0, IPPROTO_ICMPV6, ACCEPT);
    branch(BPF_JNE, 0, IPPROTO_TCP, DROP);
    load(54, 4);
    labels[PORTS] = used;
    half(-64); branch(BPF_JEQ, 0, htons(443), DROP);
    half(-62); branch(BPF_JEQ, 0, htons(443), DROP);
    labels[ACCEPT] = used; mov(0, TC_ACT_OK); emit(BPF_JMP|BPF_EXIT, 0, 0, 0, 0);
    labels[DROP] = used; mov(0, TC_ACT_SHOT); emit(BPF_JMP|BPF_EXIT, 0, 0, 0, 0);
    for (int i = 0; i < fixes; i++) {
        int delta = labels[fixlabel[i]] - fixpos[i] - 1;
        if (delta < 0 || delta > INT16_MAX) die("FORWARD_BRANCH_REQUIRED");
        ins[fixpos[i]].off = delta;
    }
    char log[65536] = {0};
    union bpf_attr attr = {0};
    attr.prog_type = BPF_PROG_TYPE_SCHED_CLS;
    attr.insn_cnt = used; attr.insns = (uintptr_t)ins;
    attr.license = (uintptr_t)"GPL";
    attr.log_buf = (uintptr_t)log; attr.log_size = sizeof(log); attr.log_level = 1;
    strcpy(attr.prog_name, "kc_boot_guard");
    int fd = syscall(__NR_bpf, BPF_PROG_LOAD, &attr, sizeof(attr));
    if (fd < 0) { fprintf(stderr, "BPF_VERIFIER %s\n", log); die("BPF_LOAD_REQUIRED"); }
    return fd;
}

struct request { struct nlmsghdr n; struct tcmsg t; char data[1024]; };
static void attr(struct request *r, int type, const void *data, size_t size) {
    size_t pos = NLMSG_ALIGN(r->n.nlmsg_len), length = RTA_LENGTH(size);
    if (pos + RTA_ALIGN(length) > sizeof(*r)) die("NETLINK_BOUND");
    struct rtattr *a = (void *)((char *)r + pos);
    a->rta_type = type; a->rta_len = length;
    if (size) memcpy(RTA_DATA(a), data, size);
    r->n.nlmsg_len = pos + RTA_ALIGN(length);
}
static void attach(int index, int fd, int direction) {
    struct request r = {0};
    r.n.nlmsg_len = NLMSG_LENGTH(sizeof(r.t));
    r.n.nlmsg_type = direction ? RTM_NEWTFILTER : RTM_NEWQDISC;
    r.n.nlmsg_flags = NLM_F_REQUEST|NLM_F_ACK|NLM_F_CREATE|NLM_F_EXCL;
    r.n.nlmsg_seq = 1;
    r.t.tcm_family = AF_UNSPEC; r.t.tcm_ifindex = index;
    r.t.tcm_parent = direction ? TC_H_MAKE(TC_H_CLSACT, direction) : TC_H_CLSACT;
    r.t.tcm_handle = direction ? 1 : TC_H_MAKE(TC_H_CLSACT, 0);
    if (!direction) attr(&r, TCA_KIND, "clsact", 7);
    else {
        r.t.tcm_info = TC_H_MAKE(1 << 16, htons(ETH_P_ALL));
        attr(&r, TCA_KIND, "bpf", 4);
        size_t start = NLMSG_ALIGN(r.n.nlmsg_len);
        attr(&r, TCA_OPTIONS, NULL, 0);
        attr(&r, TCA_BPF_FD, &fd, sizeof(fd));
        attr(&r, TCA_BPF_NAME, "kc_boot_guard", 14);
        uint32_t flags = TCA_BPF_FLAG_ACT_DIRECT;
        attr(&r, TCA_BPF_FLAGS, &flags, sizeof(flags));
        ((struct rtattr *)((char *)&r + start))->rta_len = r.n.nlmsg_len - start;
    }
    int sock = socket(AF_NETLINK, SOCK_RAW|SOCK_CLOEXEC, NETLINK_ROUTE);
    struct timeval wait = {.tv_sec=3};
    if (sock < 0 || setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &wait, sizeof(wait))) die("NETLINK_SOCKET");
    struct sockaddr_nl kernel = {.nl_family=AF_NETLINK};
    if (sendto(sock, &r, r.n.nlmsg_len, 0, (void *)&kernel, sizeof(kernel)) != (ssize_t)r.n.nlmsg_len) die("NETLINK_SEND");
    char reply[8192];
    ssize_t n = recv(sock, reply, sizeof(reply), 0);
    close(sock);
    if (n < (ssize_t)NLMSG_LENGTH(sizeof(struct nlmsgerr))) die("NETLINK_ACK_REQUIRED");
    struct nlmsghdr *h = (void *)reply;
    if (h->nlmsg_type != NLMSG_ERROR || h->nlmsg_seq != 1 || h->nlmsg_len > (size_t)n) die("NETLINK_ACK_IDENTITY");
    struct nlmsgerr *error = NLMSG_DATA(h);
    if (error->error) { errno = -error->error; die("EXCLUSIVE_TC_ATTACH_REQUIRED"); }
}

int main(int argc, char **argv) {
    guard();
    if (argc != 2 || !*argv[1] || strspn(argv[1], "0123456789") != strlen(argv[1])) die("DECIMAL_DEADLINE_REQUIRED");
    errno = 0;
    uint64_t deadline = strtoull(argv[1], NULL, 10);
    struct timespec t;
    if (errno || clock_gettime(CLOCK_BOOTTIME, &t)) die("DEADLINE_CLOCK_REQUIRED");
    uint64_t now = (uint64_t)t.tv_sec * 1000000000 + t.tv_nsec;
    if (deadline <= now || deadline - now > 8000000000ULL) die("BOUNDED_FUTURE_DEADLINE_REQUIRED");
    unsigned index = if_nametoindex("host0");
    if (!index) die("HOST0_REQUIRED");
    int fd = program(deadline);
    attach(index, fd, 0);
    attach(index, fd, TC_H_MIN_INGRESS); attach(index, fd, TC_H_MIN_EGRESS);
    struct bpf_prog_info info = {0};
    union bpf_attr a = {0};
    a.info.bpf_fd = fd; a.info.info_len = sizeof(info); a.info.info = (uintptr_t)&info;
    if (syscall(__NR_bpf, BPF_OBJ_GET_INFO_BY_FD, &a, sizeof(a))) die("BPF_IDENTITY_REQUIRED");
    close(fd); /* Filters own the program; no persistent userspace enforcer. */
    printf("{\"deadline_ns\":%llu,\"program_id\":%u,\"ifindex\":%u,\"tag\":\"",
           (unsigned long long)deadline, info.id, index);
    for (size_t i=0; i<sizeof(info.tag); i++) printf("%02x", info.tag[i]);
    puts("\",\"loader_exits\":true}");
    return 0;
}
