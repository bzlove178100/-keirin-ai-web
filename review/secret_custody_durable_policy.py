"""Strict closed-configuration records for a synthetic guest-owned volume.

These records carry no reusable permission to open traffic. Not a production
storage installer or a power-loss/crash consistency claim.
"""
import json
import uuid


def policy(generation=0, writer_boot=None):
    return dict(schema='kc-closed-policy-v1', profile='tcp443-closed',
                activation_allowed=False, generation=generation, writer_boot=writer_boot)


def decode(data):
    if not isinstance(data, bytes) or not 1 <= len(data) <= 4096:
        raise ValueError('BOUNDED_POLICY_BYTES_REQUIRED')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('DUPLICATE_POLICY_KEY')
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=pairs)
    if not isinstance(value, dict) or set(value) != set(policy()): raise ValueError('CLOSED_POLICY_KEYS_REQUIRED')
    generation, boot = value['generation'], value['writer_boot']
    if type(generation) is not int or not 0 <= generation <= 2: raise ValueError('BOUNDED_GENERATION_REQUIRED')
    if generation == 0:
        if boot is not None: raise ValueError('SEED_POLICY_REQUIRED')
    elif not isinstance(boot, str) or str(uuid.UUID(boot)) != boot: raise ValueError('WRITER_BOOT_REQUIRED')
    if value != policy(generation, boot) or value['activation_allowed'] is not False:
        raise ValueError('CLOSED_ONLY_CONFIGURATION_REQUIRED')
    return value


def replay_reason(value, boot, now):
    """Explain why a saved receipt cannot authorize a new opening."""
    if (not isinstance(value, dict) or set(value) != {'boot', 'deadline_ns'}
            or type(value['deadline_ns']) is not int or value['deadline_ns'] <= 0):
        return 'INVALID_SAVED_LEASE'
    if value['boot'] != boot: return 'PRIOR_BOOT_LEASE_REFUSED'
    if value['deadline_ns'] <= now: return 'EXPIRED_LEASE_REFUSED'
    return 'RECEIPT_IS_NOT_AUTHORIZATION'
