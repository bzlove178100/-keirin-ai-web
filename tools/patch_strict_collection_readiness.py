from __future__ import annotations

from pathlib import Path

INDEX = Path("index.html")

CSP_OLD = "script-src 'unsafe-inline';"
CSP_NEW = "script-src 'self' 'unsafe-inline';"
SCRIPT_ANCHOR = "\n<script>\n"
SCRIPT_LOADER = "\n<script src=\"prospective-tools-core.js\"></script>\n<script>\n"
BLOCK_START = "const COLLECTION_MIN_DISTINCT_PREDICTION_TIMES = 5;"
BLOCK_END = "function refreshHistoryDatasetView(message = '') {"

STRICT_BLOCK = r'''const COLLECTION_MIN_DISTINCT_PREDICTION_TIMES = 5;

function timezoneAwarePredictionTimestamp(value) {
  if (typeof value !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function fallbackProspectiveCollectionStatus(records) {
  const latestByRace = new Map();
  for (const record of Array.isArray(records) ? records : []) {
    const metadata = record?.metadata || {};
    const eligibility = metadata?.training_eligibility || {};
    const training = record?.training_input;
    const eligible = metadata?.evaluation_scope === 'prospective' &&
      metadata?.temporal_order === 'prediction_before_result' &&
      eligibility?.supervised_training === true &&
      training && typeof training === 'object' && !Array.isArray(training) &&
      training?.schema_version === 'keirin-training-input-v1' &&
      training?.evaluation_scope === 'prospective' &&
      Array.isArray(training?.players) && training.players.length >= 4 &&
      validOutcomeCombo(record?.outcome_combo);
    if (!eligible) continue;
    const raceId = String(record?.race_id || '').trim();
    if (!raceId) continue;
    const candidateTime = timezoneAwarePredictionTimestamp(record?.prediction_timestamp);
    const candidateKey = candidateTime == null ? -Infinity : candidateTime;
    const current = latestByRace.get(raceId);
    const currentTime = current ? timezoneAwarePredictionTimestamp(current?.prediction_timestamp) : null;
    const currentKey = currentTime == null ? -Infinity : currentTime;
    if (!current || candidateKey > currentKey) latestByRace.set(raceId, record);
  }

  const distinctTimes = new Set();
  for (const record of latestByRace.values()) {
    const predicted = timezoneAwarePredictionTimestamp(record?.prediction_timestamp);
    if (predicted != null) distinctTimes.add(predicted);
  }
  const distinctCount = distinctTimes.size;
  return {
    eligible_unique_races: latestByRace.size,
    distinct_prediction_times: distinctCount,
    minimum_distinct_prediction_times: COLLECTION_MIN_DISTINCT_PREDICTION_TIMES,
    remaining_distinct_prediction_times: Math.max(0, COLLECTION_MIN_DISTINCT_PREDICTION_TIMES - distinctCount),
    collection_threshold_met: distinctCount >= COLLECTION_MIN_DISTINCT_PREDICTION_TIMES,
    chronological_evaluation_may_run: false,
    blocked_reason: 'strict_validator_unavailable',
    validation_source: 'fallback_count_only'
  };
}

function prospectiveCollectionStatus(records) {
  const strict = globalThis.ProspectiveTools?.collectionStatus;
  if (typeof strict !== 'function') return fallbackProspectiveCollectionStatus(records);
  return {...strict(Array.isArray(records) ? records : []), validation_source:'prospective-tools-core'};
}

'''

REFRESH_OLD = '''  const collection = prospectiveCollectionStatus(historyDatasetRecords);
  show('dataset-prospective-count',`${collection.distinct_prediction_times}/${collection.minimum_distinct_prediction_times}件`);
  show(
    'dataset-prospective-remaining',
    collection.collection_threshold_met ? '最低条件到達' : `あと${collection.remaining_distinct_prediction_times}件`,
    collection.collection_threshold_met ? 'ok' : ''
  );'''

REFRESH_NEW = '''  const collection = prospectiveCollectionStatus(historyDatasetRecords);
  const strictReady = collection.chronological_evaluation_may_run === true;
  const timeMinimum = collection.collection_threshold_met === true;
  show('dataset-prospective-count',`${collection.distinct_prediction_times}/${collection.minimum_distinct_prediction_times}件`);
  show(
    'dataset-prospective-remaining',
    strictReady ? '時系列分割 準備可' : timeMinimum ? '5時点到達・分割未達' : `あと${collection.remaining_distinct_prediction_times}時点`,
    strictReady ? 'ok' : 'pending'
  );
  const readinessDetail = collection.validation_source === 'fallback_count_only'
    ? '厳密な前向き検証器を読み込めませんでした。件数表示は参考値です。'
    : strictReady
      ? '厳密な前向き検証で時系列分割の技術条件を確認しました。統計的な十分性・モデル優位性・収益性を意味しません。'
      : timeMinimum
        ? `5つの異なる適格予測時刻には到達していますが、時系列分割は未達です（${collection.blocked_reason || '要追加データ'}）。`
        : `厳密な前向き検証で、最低5つの異なる適格予測時刻まであと${collection.remaining_distinct_prediction_times}時点です。`;
  show('dataset-collection-detail',readinessDetail,strictReady ? 'note ok' : timeMinimum ? 'note pending' : 'note');'''


def replace_helper_block(text: str) -> str:
    start = text.find(BLOCK_START)
    end = text.find(BLOCK_END)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("collection helper block not found")
    current = text[start:end]
    if current == STRICT_BLOCK:
        return text
    return text[:start] + STRICT_BLOCK + text[end:]


def patch(text: str) -> str:
    if CSP_NEW not in text:
        if CSP_OLD not in text:
            raise RuntimeError("script CSP anchor not found")
        text = text.replace(CSP_OLD, CSP_NEW, 1)

    if 'src="prospective-tools-core.js"' not in text:
        if SCRIPT_ANCHOR not in text:
            raise RuntimeError("inline script anchor not found")
        text = text.replace(SCRIPT_ANCHOR, SCRIPT_LOADER, 1)

    text = replace_helper_block(text)

    if REFRESH_NEW not in text:
        if REFRESH_OLD not in text:
            raise RuntimeError("collection refresh block not found")
        text = text.replace(REFRESH_OLD, REFRESH_NEW, 1)
    return text


def main() -> int:
    original = INDEX.read_text(encoding="utf-8")
    updated = patch(original)
    if updated == original:
        print("strict collection readiness already applied")
        return 0
    INDEX.write_text(updated, encoding="utf-8")
    print("strict collection readiness applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
