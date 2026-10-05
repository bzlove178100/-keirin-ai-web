/* Fixed, diskless CI guest PID 1. Never run as a host service. */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/reboot.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static void fail(const char *reason) {
    printf("VM_FAIL %s errno=%d\n", reason, errno);
    fflush(stdout);
    if (getpid() != 1) exit(2);
    for (;;) pause(); /* Host supervisor owns bounded termination. */
}
static void read_text(const char *path, char *out, size_t size) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) fail("READ_REQUIRED");
    ssize_t count = read(fd, out, size - 1);
    close(fd);
    if (count <= 0 || count == (ssize_t)size - 1) fail("READ_BOUND");
    out[count] = 0;
    out[strcspn(out, "\r\n")] = 0;
}
static void write_text(const char *path, const char *value) {
    int fd = open(path, O_WRONLY | O_CLOEXEC);
    if (fd < 0 || write(fd, value, strlen(value)) != (ssize_t)strlen(value)) fail("WRITE_REQUIRED");
    close(fd);
}
static double clock_seconds(clockid_t id) {
    struct timespec t;
    if (clock_gettime(id, &t)) fail("CLOCK_REQUIRED");
    return t.tv_sec + t.tv_nsec / 1e9;
}
static void no_network(void) {
    DIR *dir = opendir("/sys/class/net");
    struct dirent *entry;
    int count = 0;
    if (!dir) fail("INTERFACES_REQUIRED");
    while ((entry = readdir(dir))) {
        if (entry->d_name[0] == '.') continue;
        if (strcmp(entry->d_name, "lo")) fail("EXTERNAL_INTERFACE_FORBIDDEN");
        count++;
    }
    closedir(dir);
    if (count != 1) fail("ONLY_LOOPBACK_REQUIRED");
}
static void record(const char *event, const char *boot, int marker) {
    no_network();
    printf("VM_RECORD {\"event\":\"%s\",\"boot\":\"%s\",\"monotonic\":%.9f,\"boottime\":%.9f,\"marker\":%d,\"only_loopback\":true}\n",
           event, boot, clock_seconds(CLOCK_MONOTONIC), clock_seconds(CLOCK_BOOTTIME), marker);
    fflush(stdout);
}
int main(void) {
    /* Refuse ordinary execution BEFORE mounts, files or power operations. */
    if (getpid() != 1 || getuid() != 0) {
        fputs("VM_GUEST_PID1_REQUIRED\n", stderr);
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    mkdir("/proc", 0755); mkdir("/sys", 0755); mkdir("/run", 0755);
    if (mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL) ||
        mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL)) fail("GUEST_MOUNTS_REQUIRED");
    char cmdline[2048], vendor[128], boot[64], modes[128];
    read_text("/proc/cmdline", cmdline, sizeof(cmdline));
    read_text("/sys/class/dmi/id/sys_vendor", vendor, sizeof(vendor));
    if (!strstr(cmdline, " kc_vm_probe=1 ") || strcmp(vendor, "QEMU")) fail("FIXED_QEMU_GUEST_REQUIRED");
    no_network();
    if (mount("tmpfs", "/run", "tmpfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, "size=1m,mode=0700")) fail("PRIVATE_RUN_REQUIRED");
    if (!access("/run/probe.marker", F_OK)) fail("FRESH_RUN_REQUIRED");
    read_text("/proc/sys/kernel/random/boot_id", boot, sizeof(boot));
    record("boot", boot, 0);
    int fd = open("/run/probe.marker", O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (fd < 0) fail("MARKER_CREATE_REQUIRED");
    close(fd);
#ifdef KC_PACKET_PROBE
    if (!strstr(cmdline, " kc_packet_probe=1 ")) fail("FIXED_PACKET_OPT_IN_REQUIRED");
    execl("/usr/bin/python3", "python3", "-I", "-B", "/probe.py", (char *)NULL);
    fail("PACKET_GUEST_EXEC_FAILED");
#endif
    for (;;) {
        int command = getchar();
        if (command == 's') {
            read_text("/sys/power/mem_sleep", modes, sizeof(modes));
            if (!strstr(modes, "deep")) fail("ACPI_DEEP_REQUIRED");
            write_text("/sys/power/mem_sleep", "deep");
            record("before_suspend", boot, !access("/run/probe.marker", F_OK));
            write_text("/sys/power/state", "mem");
            record("after_suspend", boot, !access("/run/probe.marker", F_OK));
        } else if (command == 'r') {
            record("before_reboot", boot, !access("/run/probe.marker", F_OK));
            if (reboot(LINUX_REBOOT_CMD_RESTART)) fail("GUEST_REBOOT_FAILED");
        } else if (command == EOF) {
            fail("SERIAL_CONTROL_LOST");
        }
    }
}
