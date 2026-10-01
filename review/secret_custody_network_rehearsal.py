"""Pure, synthetic nft profiles for CI. NOT a live-host firewall installer.

Fixed documentation addresses only. No input addresses, host reads, subprocess,
credentials, persistence or live apply interface. See the transition review.
"""

TABLE = "kc_h3_fixture"
FAMILIES = (("ip", "192.0.2."), ("ip6", "2001:db8:1::"))


def profile(mode):
    if mode not in ("maintenance", "qualification"):
        raise ValueError("UNKNOWN_FIXTURE_PROFILE")
    inbound = ['iifname "lo" accept', 'ct state invalid drop']
    outbound = ['oifname "lo" accept', 'ct state invalid drop']
    for family, prefix in FAMILIES:
        # Two synthetic administration sources: phone-like and recovery-like.
        # Real Lightsail browser source ranges are still unknown.
        for suffix in ("2", "3"):
            source = prefix + suffix
            inbound.append(f'{family} saddr {source} tcp dport 22 ct state {{ new, established }} accept')
            outbound.append(f'{family} daddr {source} tcp sport 22 ct state established accept')
        # Synthetic DNS and time-sync transport, not live service discovery.
        destinations = [("tcp", 53), ("udp", 53), ("udp", 123)]
        if mode == "qualification":
            destinations.append(("tcp", 443))
        for protocol, port in destinations:
            address = prefix + "2"
            outbound.append(f'{family} daddr {address} {protocol} dport {port} ct state {{ new, established }} accept')
            inbound.append(f'{family} saddr {address} {protocol} sport {port} ct state established accept')
    # No blanket established/related exemption: removing a qualification
    # destination must also block an already-established flow to that destination.
    chunks = [f'table inet {TABLE} {{']
    for hook, rules in (("input", inbound), ("output", outbound), ("forward", [])):
        chunks.append(f'  chain {hook} {{ type filter hook {hook} priority 0; policy drop;')
        chunks.extend('    ' + rule for rule in rules)
        chunks.append('  }')
    chunks.append('}')
    return '\n'.join(chunks) + '\n'


def replacement(mode):
    # One nft -f transaction; never flush the entire ruleset. CI must verify
    # exact ownership immediately before this operation. No live race guarantee.
    return f'delete table inet {TABLE}\n' + profile(mode)


if __name__ == "__main__":
    print("STOP CI_REHEARSAL_ONLY_NO_LIVE_APPLY")
    raise SystemExit(1)
