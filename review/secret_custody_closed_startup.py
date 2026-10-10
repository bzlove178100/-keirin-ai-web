"""Fixed synthetic TCP/443 startup gate, not a production firewall/installer."""
import copy

TABLE = 'kc_startup_guard'


def install():
    text = f'create table inet {TABLE}\n'
    for hook in ('input', 'output'):
        text += (f'add chain inet {TABLE} {hook} {{ type filter hook {hook} '
                 'priority -20; policy accept; }\n')
        for field in ('sport', 'dport'):
            text += f'add rule inet {TABLE} {hook} tcp {field} 443 counter drop\n'
    return text


def seal(report):
    """Require exactly the fixed closed policy; ignore only counters/metainfo."""
    rows = copy.deepcopy(report['nftables'])
    rows = [row for row in rows if 'metainfo' not in row]
    expected = [('table', None)]
    for hook in ('input', 'output'):
        expected += [('chain', hook), ('rule', hook), ('rule', hook)]
    if len(rows) != len(expected):
        raise ValueError('FIXED_STARTUP_OBJECTS_REQUIRED')
    ports = iter(('sport', 'dport', 'sport', 'dport'))
    handles = set()
    for row, (kind, hook) in zip(rows, expected):
        if set(row) != {kind}:
            raise ValueError('FIXED_STARTUP_OBJECT_ORDER_REQUIRED')
        obj = row[kind]
        if (obj.get('family') != 'inet' or obj.get('name' if kind == 'table' else 'table') != TABLE
                or type(obj.get('handle')) is not int or obj['handle'] <= 0
                or (kind != 'table' and obj['handle'] in handles)):
            raise ValueError('FIXED_STARTUP_IDENTITY_REQUIRED')
        if kind != 'table':
            handles.add(obj['handle'])
        if kind == 'chain':
            if (obj.get('name') != hook or obj.get('type') != 'filter' or obj.get('hook') != hook
                    or obj.get('prio') != -20 or obj.get('policy') != 'accept'):
                raise ValueError('FIXED_STARTUP_HOOK_REQUIRED')
        if kind == 'rule':
            expressions = obj.get('expr')
            if not isinstance(expressions, list) or len(expressions) != 3:
                raise ValueError('FIXED_STARTUP_RULE_REQUIRED')
            counter = expressions[1].get('counter')
            if not isinstance(counter, dict) or set(counter) != {'packets', 'bytes'}:
                raise ValueError('FIXED_STARTUP_COUNTER_REQUIRED')
            expressions[1] = {'counter': {}}
            match = {'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': next(ports)}}, 'right': 443}}
            if obj.get('chain') != hook or expressions != [match, {'counter': {}}, {'drop': None}]:
                raise ValueError('FIXED_STARTUP_DROP_REQUIRED')
    return rows
