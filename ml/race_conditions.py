"""Declared pre-race conditions for the standard 7/9-rider offline model.

This is an internal contract, not a provider parser or a claim that omitted
conditions have been independently checked.
"""


def require_standard_conditions(conditions):
    if (not isinstance(conditions, dict) or
            set(conditions) != {'race_status', 'withdrawn_car_numbers'}):
        raise ValueError('race_conditions_contract_invalid')
    if conditions['race_status'] != 'scheduled':
        raise ValueError('nonstandard_race_requires_review')
    if not isinstance(conditions['withdrawn_car_numbers'], list):
        raise ValueError('race_conditions_contract_invalid')
    if conditions['withdrawn_car_numbers']:
        raise ValueError('withdrawal_requires_review')
