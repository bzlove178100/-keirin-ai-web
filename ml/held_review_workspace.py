"""Bounded, append-only in-memory workspace for synthetic held-event review.

Export/import preserves all supplied holds and decisions. This is not a global
ledger, a session checkpoint, a provenance verifier, or an ordinary history.
"""
from copy import deepcopy

from ml.held_history_review import create_review, evaluate_reviews, REPORT_SCHEMA
from ml.model_history import _canonical, _digest

SCHEMA = 'synthetic-held-review-bundle-v1'
MAX_BYTES = 32 * 1024 * 1024
MAX_HOLDS = 20
MAX_REVIEWS = 40


class ReviewConflict(ValueError):
    pass


def _bounded(holds, reviews):
    if (not isinstance(holds, list) or not isinstance(reviews, list) or
            len(holds) > MAX_HOLDS or len(reviews) > MAX_REVIEWS):
        raise ValueError('review_bundle_record_limit')


class ReviewWorkspace:
    def __init__(self):
        self.holds = []
        self.reviews = []
        self.report = evaluate_reviews([], [], synthetic=True)

    def bundle(self):
        payload = {'schema_version': SCHEMA, 'synthetic_only': True,
                   'held_records': self.holds, 'reviews': self.reviews}
        return deepcopy({'payload': payload, 'sha256': _digest(payload)})

    def state(self):
        report = {key: value for key, value in self.report.items()
                  if key not in ('source_histories', 'reviews')}
        records = []
        for record in self.holds:
            digest = _digest(record)
            case = next(case for case in report['cases'] if digest in case['held_history_sha256s'])
            receipts = [r for r in self.reviews if r['source_history_sha256'] == digest]
            records.append({'sha256': digest, 'schema_version': record['schema_version'],
                            'race_identity': case['race_identity'],
                            'prediction_timestamp': record['prediction_timestamp'],
                            'settlement': record['settlement'],
                            'decisions': [r['decision'] for r in receipts]})
        return deepcopy({'revision': self.bundle()['sha256'], 'records': records, 'report': report})

    def _expect(self, revision):
        if revision != self.bundle()['sha256']:
            raise ReviewConflict('review_workspace_changed')

    def _commit(self, holds, reviews):
        # Validate before deduplication; never silently discard invalid inputs.
        _bounded(holds, reviews)
        report = evaluate_reviews(holds, reviews, synthetic=True)
        unique_holds = {_digest(record): record for record in holds}
        unique_reviews = {_digest(record): record for record in reviews}
        holds = [unique_holds[key] for key in sorted(unique_holds)]
        reviews = [unique_reviews[key] for key in sorted(unique_reviews)]
        payload = {'schema_version': SCHEMA, 'synthetic_only': True,
                   'held_records': holds, 'reviews': reviews}
        if len(_canonical({'payload': payload, 'sha256': _digest(payload)}).encode()) > MAX_BYTES:
            raise ValueError('review_bundle_too_large')
        if len(holds) != report['input_held_records'] or len(reviews) != report['input_reviews']:
            report = evaluate_reviews(holds, reviews, synthetic=True)
        self.holds, self.reviews, self.report = deepcopy((holds, reviews, report))
        return self.state()

    def load(self, value, revision):
        self._expect(revision)
        if isinstance(value, dict) and set(value) == {'payload', 'sha256'}:
            payload = value['payload']
            if (not isinstance(payload, dict) or
                    set(payload) != {'schema_version', 'synthetic_only', 'held_records', 'reviews'} or
                    payload['schema_version'] != SCHEMA or payload['synthetic_only'] is not True):
                raise ValueError('review_bundle_schema_invalid')
            if value['sha256'] != _digest(payload):
                raise ValueError('review_bundle_digest_mismatch')
            holds, reviews = payload['held_records'], payload['reviews']
        elif isinstance(value, dict) and value.get('schema_version') == REPORT_SCHEMA:
            holds, reviews = value.get('source_histories'), value.get('reviews')
            _bounded(holds, reviews)
            expected = evaluate_reviews(holds, reviews, synthetic=True)
            if _canonical(value) != _canonical(expected):
                raise ValueError('review_report_mismatch')
        else:
            holds, reviews = value if isinstance(value, list) else [value], []
        _bounded(holds, reviews)
        # Validate this input as a complete batch before merging with current state.
        evaluate_reviews(holds, reviews, synthetic=True)
        # Identical imports are idempotent, even when the workspace is at its limit.
        combined_holds = {_digest(r): r for r in self.holds + holds}
        combined_reviews = {_digest(r): r for r in self.reviews + reviews}
        return self._commit(list(combined_holds.values()), list(combined_reviews.values()))

    def review(self, source_sha256, evidence, decision, revision):
        self._expect(revision)
        source = next((r for r in self.holds if _digest(r) == source_sha256), None)
        if source is None:
            raise ValueError('review_source_not_in_batch')
        receipt = create_review(source, evidence, decision, synthetic=True)
        combined = {_digest(r): r for r in self.reviews + [receipt]}
        return self._commit(self.holds, list(combined.values()))
