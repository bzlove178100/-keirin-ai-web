'use strict';

(() => {
  const core = globalThis.ProspectiveTools;
  if (!core) throw new Error('ProspectiveTools core not loaded');

  const byId = (id) => document.getElementById(id);
  const snapshotFile = byId('snapshot-file');
  const snapshotStatus = byId('snapshot-status');
  const outcome = byId('outcome');
  const settlementOdds = byId('settlement-odds');
  const resultTime = byId('result-time');
  const setNow = byId('set-now');
  const buildHistoryButton = byId('build-history');
  const downloadHistoryButton = byId('download-history');
  const historyStatus = byId('history-status');
  const historySummary = byId('history-summary');
  const historyFiles = byId('history-files');
  const eligibleCount = byId('eligible-count');
  const distinctCount = byId('distinct-count');
  const remainingCount = byId('remaining-count');
  const partitionReady = byId('partition-ready');
  const collectionStatus = byId('collection-status');
  const collectionSummary = byId('collection-summary');

  let loadedSnapshot = null;
  let generatedEnvelope = null;

  function setClass(element, className) {
    element.className = className;
  }

  function localInputValue(date) {
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }

  function localInputToAwareIso(value) {
    if (!value) throw new Error('結果確認・記録時刻を入力してください');
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) throw new Error('結果確認・記録時刻を確認してください');
    return date.toISOString();
  }

  async function readJsonFile(file) {
    if (!file) throw new Error('ファイルが選択されていません');
    if (file.size > 10_000_000) throw new Error('10MB以下のJSONファイルを使用してください');
    return JSON.parse(await file.text());
  }

  function updateBuildState() {
    buildHistoryButton.disabled = !loadedSnapshot;
  }

  snapshotFile.addEventListener('change', async () => {
    loadedSnapshot = null;
    generatedEnvelope = null;
    downloadHistoryButton.disabled = true;
    historySummary.textContent = '-';
    const file = snapshotFile.files && snapshotFile.files[0];
    if (!file) {
      snapshotStatus.textContent = '未選択';
      setClass(snapshotStatus, 'note');
      updateBuildState();
      return;
    }
    try {
      const parsed = await readJsonFile(file);
      core.validateSnapshot(parsed);
      loadedSnapshot = parsed;
      const race = (parsed.race_data || {}).race || {};
      const captured = new Date(parsed.captured_at).toLocaleString('ja-JP');
      const knownOdds = Object.keys((((parsed.race_data || {}).odds || {}).trifecta) || {}).length;
      snapshotStatus.textContent = `確認済み：${race.date || '-'} ${race.venue || '-'} ${race.race_number || '-'}R / 予測 ${captured} / 既知3連単オッズ ${knownOdds}/210`;
      setClass(snapshotStatus, 'note ok');
    } catch (error) {
      snapshotStatus.textContent = `読み込み不可：${error.code || error.message || 'invalid snapshot'}`;
      setClass(snapshotStatus, 'note error');
    }
    updateBuildState();
  });

  setNow.addEventListener('click', () => {
    resultTime.value = localInputValue(new Date());
  });

  buildHistoryButton.addEventListener('click', () => {
    generatedEnvelope = null;
    downloadHistoryButton.disabled = true;
    try {
      const record = core.buildHistory(loadedSnapshot, {
        outcomeCombo: outcome.value.trim(),
        settlementOdds: Number(settlementOdds.value),
        resultTimestamp: localInputToAwareIso(resultTime.value),
      });
      generatedEnvelope = core.historyEnvelope(record);
      const oddsCount = Object.keys((((record.training_input || {}).odds || {}).trifecta) || {}).length;
      historyStatus.textContent = '生成成功。DB保存・外部通信は行っていません。';
      setClass(historyStatus, 'note ok');
      historySummary.textContent = JSON.stringify({
        race_id: record.race_id,
        prediction_timestamp: record.prediction_timestamp,
        result_observed_timestamp: record.metadata.result_timestamp,
        outcome_combo: record.outcome_combo,
        settlement_odds: record.settlement_odds,
        phase32_probability_count: record.trifecta_scores.length,
        known_prediction_time_odds_count: oddsCount,
        supervised_training_eligible: record.metadata.training_eligibility.supervised_training,
        evaluation_scope: record.metadata.evaluation_scope,
      }, null, 2);
      downloadHistoryButton.disabled = false;
    } catch (error) {
      historyStatus.textContent = `生成できません：${error.code || error.message || 'invalid input'}`;
      setClass(historyStatus, 'note error');
      historySummary.textContent = '-';
    }
  });

  downloadHistoryButton.addEventListener('click', () => {
    if (!generatedEnvelope) return;
    const record = generatedEnvelope.payload.records[0];
    const safeVenue = String((record.metadata || {}).venue || 'venue').replace(/[^0-9A-Za-z\u3040-\u30ff\u3400-\u9fff_-]+/g, '-');
    const filename = `backtest-history-${record.metadata.date || 'date'}-${safeVenue}-${record.metadata.race_number || 'R'}R.json`;
    const blob = new Blob([JSON.stringify(generatedEnvelope, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  historyFiles.addEventListener('change', async () => {
    const files = [...(historyFiles.files || [])];
    if (!files.length) return;
    collectionStatus.textContent = '確認中…';
    setClass(collectionStatus, 'note');
    try {
      const parsed = await Promise.all(files.map(readJsonFile));
      const records = parsed.flatMap(core.recordsFromJson);
      const status = core.collectionStatus(records);
      eligibleCount.textContent = String(status.eligible_unique_races);
      distinctCount.textContent = String(status.distinct_prediction_times);
      remainingCount.textContent = String(status.remaining_distinct_prediction_times);
      partitionReady.textContent = status.chronological_evaluation_may_run ? '準備可' : '未達';
      collectionStatus.textContent = status.chronological_evaluation_may_run
        ? '時系列分割の技術条件を満たしています。これは精度・収益性の証明ではありません。'
        : `まだ評価開始条件を満たしていません：${status.blocked_reason || 'insufficient data'}`;
      setClass(collectionStatus, status.chronological_evaluation_may_run ? 'note ok' : 'note warn');
      collectionSummary.textContent = JSON.stringify(status, null, 2);
    } catch (error) {
      collectionStatus.textContent = `確認できません：${error.code || error.message || 'invalid history'}`;
      setClass(collectionStatus, 'note error');
      collectionSummary.textContent = '-';
    }
  });
})();
