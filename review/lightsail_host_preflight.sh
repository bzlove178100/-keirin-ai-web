#!/bin/sh
# REVIEW-ONLY READ-ONLY PREFLIGHT.
# This script intentionally performs no network requests and no system mutation.
set -eu

failures=0
warnings=0

pass() { printf 'PASS %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1"; failures=$((failures + 1)); }
warn() { printf 'WARN %s\n' "$1"; warnings=$((warnings + 1)); }
fact() { printf 'FACT %s=%s\n' "$1" "$2"; }

require_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    pass "command:$1"
  else
    fail "command:$1:missing"
  fi
}

if [ "$(uname -s 2>/dev/null || true)" = "Linux" ]; then
  pass 'kernel:linux'
else
  fail 'kernel:not_linux'
fi

kernel_release=$(uname -r 2>/dev/null || printf 'unknown')
fact 'kernel_release' "$kernel_release"

if [ -r /etc/os-release ]; then
  os_id=$(sed -n 's/^ID=//p' /etc/os-release | head -n 1 | tr -d '"' || true)
  os_version=$(sed -n 's/^VERSION_ID=//p' /etc/os-release | head -n 1 | tr -d '"' || true)
  fact 'os_id' "${os_id:-unknown}"
  fact 'os_version' "${os_version:-unknown}"
else
  warn 'os_release:unreadable'
fi

pid1=$(cat /proc/1/comm 2>/dev/null || true)
if [ "$pid1" = "systemd" ]; then
  pass 'pid1:systemd'
else
  fail 'pid1:not_systemd'
fi

for cmd in systemctl nft ss ip findmnt stat awk sed grep cut tr head; do
  require_cmd "$cmd"
done

if command -v findmnt >/dev/null 2>&1 \
    && findmnt -n -t cgroup2 /sys/fs/cgroup >/dev/null 2>&1; then
  pass 'cgroup:v2'
else
  fail 'cgroup:v2:missing'
fi

mem_kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || true)
case "$mem_kb" in
  ''|*[!0-9]*) fail 'memory:unknown' ;;
  *)
    fact 'mem_total_kb' "$mem_kb"
    if [ "$mem_kb" -ge 900000 ]; then
      pass 'memory:reviewed_1gb_class_floor'
    else
      fail 'memory:below_reviewed_1gb_class_floor'
    fi
    ;;
esac

swap_kb=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo 2>/dev/null || true)
case "$swap_kb" in
  ''|*[!0-9]*) fail 'swap:unknown' ;;
  0) pass 'swap:disabled' ;;
  *) fact 'swap_total_kb' "$swap_kb"; fail 'swap:active' ;;
esac

if [ -r /sys/fs/cgroup/cgroup.controllers ]; then
  controllers=$(tr '\n' ' ' < /sys/fs/cgroup/cgroup.controllers | sed 's/[[:space:]][[:space:]]*/ /g')
  fact 'cgroup_controllers' "${controllers:-none}"
else
  fail 'cgroup:controllers_unreadable'
fi

if [ -r /proc/sys/kernel/core_pattern ]; then
  core_pattern=$(cat /proc/sys/kernel/core_pattern 2>/dev/null || true)
  case "$core_pattern" in
    *[[:space:]]*) fact 'core_pattern' 'configured' ;;
    '') warn 'core_pattern:empty' ;;
    *) fact 'core_pattern' "$core_pattern" ;;
  esac
else
  warn 'core_pattern:unreadable'
fi

if command -v ss >/dev/null 2>&1; then
  # Report only listening local socket addresses. No process args or environment are read.
  listeners=$(ss -H -lnt 2>/dev/null | awk '{print $4}' | sort -u || true)
  if [ -n "$listeners" ]; then
    printf '%s\n' "$listeners" | while IFS= read -r addr; do
      [ -n "$addr" ] && printf 'FACT listener=%s\n' "$addr"
    done

    unexpected=$(printf '%s\n' "$listeners" | awk '
      function port_of(s, p) {
        p=s; sub(/^.*:/,"",p); return p
      }
      {
        p=port_of($0)
        wildcard=($0 ~ /^0\.0\.0\.0:/ || $0 ~ /^\*:/ || $0 ~ /^\[::\]:/ || $0 ~ /^:::/)
        if (wildcard && p != "22") print $0
      }
    ')
    if [ -n "$unexpected" ]; then
      fail 'listeners:unexpected_wildcard'
    else
      pass 'listeners:no_unexpected_wildcard_except_bootstrap_ssh'
    fi
  else
    pass 'listeners:none'
  fi
else
  fail 'listeners:ss_missing'
fi

if [ "$(id -u)" -eq 0 ]; then
  pass 'execution:root_read_visibility'
else
  warn 'execution:not_root_some_visibility_may_be_reduced'
fi

fact 'warning_count' "$warnings"
fact 'failure_count' "$failures"

if [ "$failures" -ne 0 ]; then
  printf 'RESULT BLOCKED\n'
  exit 1
fi

printf 'RESULT PREFLIGHT_OK_NO_MUTATION\n'
