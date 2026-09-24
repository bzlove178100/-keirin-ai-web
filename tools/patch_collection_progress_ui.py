from __future__ import annotations

from pathlib import Path

INDEX = Path("index.html")

UI_ANCHOR = '''    <article class="pick"><h3>収録レース</h3><p id="dataset-record-count">0件</p></article>
    <article class="pick"><h3>重複除外</h3><p id="dataset-duplicate-count">0件</p></article>'''
UI_REPLACEMENT = '''    <article class="pick"><h3>収録レース</h3><p id="dataset-record-count">0件</p></article>
    <article class="pick"><h3>重複除外</h3><p id="dataset-duplicate-count">0件</p></article>
    <article class="pick"><h3>前向き実データ</h3><p id="dataset-prospective-count">0/5件</p></article>
    <article class="pick"><h3>比較準備</h3><p id="dataset-prospective-remaining">あと5件</p></article>'''

DETAIL_ANCHOR = '''  </div>

  <button id="save-dataset" class="secondary" type="button" disabled>統合履歴JSONを端末へ保存</button>'''
DETAIL_REPLACEMENT = '''  </div>
  <p id="dataset-collection-detail" class="note">5件は時系列比較を開始する技術上の最低予測時点数です。統計的な十分性や収益性を意味しません。</p>

  <button id="save-dataset" class="secondary" type="button" disabled>統合履歴JSONを端末へ保存</button>'''

FUNCTION_ANCHOR = '''function refreshHistoryDatasetView(message = '') {'''
FUNCTION_BLOCK = r'''const COLLECTION_MIN_DISTINCT_PREDICTION_TIMES = 5;

function timezoneAwarePredictionTimestamp(value) {
  if (typeof value !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function prospectiveCollectionEligible(record) {
  const metadata = record?.metadata || {};
  const eligibility = metadata?.training_eligibility || {};
  const training = record?.training_input;
  return metadata?.evaluation_scope === 'prospective' &&
    metadata?.temporal_order === 'prediction_before_result' &&
    eligibility?.supervised_training === true &&
    training && typeof training === 'object' && !Array.isArray(training) &&
    training?.schema_version === 'keirin-training-input-v1' &&
    training?.evaluation_scope === 'prospective' &&
    Array.isArray(training?.players) && training.players.length >= 4 &&
    validOutcomeCombo(record?.outcome_combo);
}

function prospectiveCollectionStatus(records) {
  const latestByRace = new Map();
  for (const record of Array.isArray(records) ? records : []) {
    if (!prospectiveCollectionEligible(record)) continue;
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
  let eligibleUniqueRaces = 0;
  let invalidPredictionTimes = 0;
  for (const record of latestByRace.values()) {
    const predicted = timezoneAwarePredictionTimestamp(record?.prediction_timestamp);
    if (predicted == null) {
      invalidPredictionTimes++;
      continue;
    }
    eligibleUniqueRaces++;
    distinctTimes.add(predicted);
  }

  const distinctCount = distinctTimes.size;
  const remaining = Math.max(0, COLLECTION_MIN_DISTINCT_PREDICTION_TIMES - distinctCount);
  return {
    eligible_unique_races: eligibleUniqueRaces,
    distinct_prediction_times: distinctCount,
    minimum_distinct_prediction_times: COLLECTION_MIN_DISTINCT_PREDICTION_TIMES,
    remaining_distinct_prediction_times: remaining,
    collection_threshold_met: remaining === 0,
    invalid_prediction_times: invalidPredictionTimes
  };
}

'''

REFRESH_ANCHOR = '''  show('dataset-record-count',`${historyDatasetRecords.length}件`);
  show('dataset-duplicate-count',`${historyDatasetDuplicateCount}件`);'''
REFRESH_REPLACEMENT = '''  show('dataset-record-count',`${historyDatasetRecords.length}件`);
  show('dataset-duplicate-count',`${historyDatasetDuplicateCount}件`);
  const collection = prospectiveCollectionStatus(historyDatasetRecords);
  show('dataset-prospective-count',`${collection.distinct_prediction_times}/${collection.minimum_distinct_prediction_times}件`);
  show(
    'dataset-prospective-remaining',
    collection.collection_threshold_met ? '最低条件到達' : `あと${collection.remaining_distinct_prediction_times}件`,
    collection.collection_threshold_met ? 'ok' : ''
  );'''


def replace_once(text: str, anchor: str, replacement: str, label: str) -> str:
    if replacement in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(anchor, replacement, 1)


def patch(text: str) -> str:
    text = replace_once(text, UI_ANCHOR, UI_REPLACEMENT, "dataset cards")
    text = replace_once(text, DETAIL_ANCHOR, DETAIL_REPLACEMENT, "dataset detail")
    if "function prospectiveCollectionStatus(records)" not in text:
        if FUNCTION_ANCHOR not in text:
            raise RuntimeError("anchor not found: refreshHistoryDatasetView")
        text = text.replace(FUNCTION_ANCHOR, FUNCTION_BLOCK + FUNCTION_ANCHOR, 1)
    # Strict-readiness UI has its own refresh block. Do not reinsert the legacy count-only block.
    if "collection.chronological_evaluation_may_run" not in text:
        text = replace_once(text, REFRESH_ANCHOR, REFRESH_REPLACEMENT, "dataset refresh")
    return text


def main() -> int:
    original = INDEX.read_text(encoding="utf-8")
    updated = patch(original)
    if updated == original:
        print("collection progress UI already applied")
        return 0
    INDEX.write_text(updated, encoding="utf-8")
    print("collection progress UI applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
