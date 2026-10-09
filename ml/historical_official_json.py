"""Offline intake of separately saved official header/result JSON responses.

No fetching or synthetic HTML. Receipts are operator evidence, not source
authentication. Raw response bytes and their receipts must remain private.
"""
from __future__ import annotations

import copy
import hashlib
import json
from urllib.parse import parse_qsl, urlparse

from ml.historical_official_detail import _constant, _object, _observation, _scope
from ml.historical_training import digest, timestamp


def _capture(raw, receipt, request_type):
    if not isinstance(raw, bytes) or not raw or len(raw) > 5_000_000:
        raise ValueError("invalid_capture_size")
    sha = hashlib.sha256(raw).hexdigest()
    if (not isinstance(receipt, dict) or type(receipt.get('bytes')) is not int
            or type(receipt.get('status')) is not int or receipt['status'] != 200
            or receipt.get('sha256') != sha or receipt['bytes'] != len(raw)
            or receipt.get('method') != 'GET'):
        raise ValueError("capture_receipt_mismatch")
    parameters = []
    for field in ('url', 'final_url'):
        url = urlparse(receipt.get(field, ''))
        pairs = parse_qsl(url.query, keep_blank_values=True)
        params = dict(pairs)
        if (url.scheme != 'https' or url.netloc != 'keirin.jp' or url.path != '/pc/json'
                or url.fragment or len(pairs) != 2 or set(params) != {'encp', 'type'}
                or not params['encp'].strip() or params['type'] != request_type):
            raise ValueError("unexpected_json_source_url")
        parameters.append(params)
    if parameters[0] != parameters[1]:
        raise ValueError("json_capture_redirect_parameters_changed")
    if timestamp(receipt.get('request_started_at')) > timestamp(receipt.get('download_completed_at')):
        raise ValueError("invalid_capture_chronology")
    data = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_object, parse_constant=_constant)
    if not isinstance(data, dict) or type(data.get('resultCd')) is not int or data['resultCd'] != 0:
        raise ValueError("source_data_error:" + request_type)
    return data, sha, parameters[0]['encp']


def ingest_json_result(header_bytes, header_receipt, result_bytes, result_receipt,
                       race_date, venue_code, race_number):
    """Bind JSJ001/JSJ012 by equal observed selection token, then check scope."""
    _scope(race_date, venue_code, race_number, 'result')
    header, hh, hp = _capture(header_bytes, header_receipt, 'JSJ001')
    payload, rh, rp = _capture(result_bytes, result_receipt, 'JSJ012')
    if hp != rp:
        raise ValueError("json_capture_selection_mismatch")
    if header['C0201data'].get('encSelParaR') != hp:
        raise ValueError("json_header_selection_mismatch")
    if payload.get('tyakujyunDispFlg') is not True or payload.get('haraiGakuDispFlg') is not True:
        raise ValueError("result_not_published")
    hashes = {'PC0201': hh, 'PJ0326': rh}
    # Both blocks must have been captured after the listed race start. Use the
    # latest completion as the conservative time this paired observation exists.
    observed_at = max((header_receipt['download_completed_at'], result_receipt['download_completed_at']), key=timestamp)
    result = _observation(header, payload, digest(hashes), result_receipt['final_url'],
                          observed_at, race_date, venue_code, race_number, 'result')
    if min(timestamp(r['download_completed_at']) for r in (header_receipt, result_receipt)) < max(map(timestamp, result['listed_start_times_jst'])):
        raise ValueError("json_capture_before_listed_start")
    result.update(capture_format='paired_official_json', source_hash_basis='digest_of_capture_sha256_map',
                  source_capture_sha256=hashes,
                  source_capture_receipts={name: {key: copy.deepcopy(receipt[key]) for key in
                      ('url', 'final_url', 'method', 'request_started_at', 'download_completed_at', 'bytes', 'status', 'sha256')}
                      for name, receipt in (('PC0201', header_receipt), ('PJ0326', result_receipt))})
    result.pop('record_sha256_without_hash_field')
    result['record_sha256_without_hash_field'] = digest(result)
    return result
