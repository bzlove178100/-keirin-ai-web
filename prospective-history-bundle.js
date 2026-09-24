(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ProspectiveHistoryBundle = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const SCHEMA_VERSION = 'prospective-private-history-bundle-v1';

  function recordsFromJson(value) {
    const records = [];
    function visit(node) {
      if (Array.isArray(node)) {
        node.forEach(visit);
        return;
      }
      if (!node || typeof node !== 'object') return;
      if (node.mode === 'dry_run' && node.payload && typeof node.payload === 'object') {
        visit(node.payload);
        return;
      }
      if (Array.isArray(node.records)) {
        node.records.forEach(visit);
        return;
      }
      if (node.history_record && typeof node.history_record === 'object') {
        visit(node.history_record);
        return;
      }
      if (typeof node.race_id === 'string') records.push(node);
    }
    visit(value);
    return records;
  }

  function canonical(value) {
    if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
    if (value && typeof value === 'object') {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
    }
    return JSON.stringify(value);
  }

  function dedupeExact(records) {
    const seen = new Set();
    const unique = [];
    for (const record of records) {
      const key = canonical(record);
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(record);
    }
    return unique;
  }

  function buildBundle(values, options = {}) {
    const flattened = (Array.isArray(values) ? values : [values]).flatMap(recordsFromJson);
    const records = dedupeExact(flattened);
    const createdAt = options.createdAt || new Date().toISOString();
    const createdMs = Date.parse(createdAt);
    if (!Number.isFinite(createdMs)) throw new Error('created_at_invalid');
    return {
      mode: 'dry_run',
      payload: { records },
      private_bundle: {
        schema_version: SCHEMA_VERSION,
        created_at: new Date(createdMs).toISOString(),
        input_record_count: flattened.length,
        record_count: records.length,
        exact_duplicates_removed: flattened.length - records.length,
        db_write_enabled: false,
        external_fetch_enabled: false,
        production_prediction_enabled: false,
        note: 'Local private history bundle. Keep real-race histories outside the public repository.'
      }
    };
  }

  function safeDateStamp(date) {
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  function attachBrowserUi() {
    if (typeof document === 'undefined') return;
    const input = document.getElementById('history-files');
    const button = document.getElementById('save-history-bundle');
    const status = document.getElementById('history-bundle-status');
    if (!input || !button || !status) return;

    let currentBundle = null;
    const setStatus = (text, className = 'note') => {
      status.textContent = text;
      status.className = className;
    };

    input.addEventListener('change', async () => {
      currentBundle = null;
      button.disabled = true;
      const files = [...(input.files || [])];
      if (!files.length) {
        setStatus('履歴ファイルを選択すると、端末内で1つの私有JSONにまとめられます。');
        return;
      }
      try {
        const parsed = [];
        for (const file of files) {
          if (file.size > 10_000_000) throw new Error(`${file.name}: 10MBを超えています`);
          parsed.push(JSON.parse(await file.text()));
        }
        currentBundle = buildBundle(parsed);
        const meta = currentBundle.private_bundle;
        setStatus(
          `統合準備：${meta.record_count}件 / 完全重複除外 ${meta.exact_duplicates_removed}件。外部通信・DB保存は行いません。`,
          'note ok'
        );
        button.disabled = meta.record_count === 0;
      } catch (error) {
        setStatus(`統合できません：${error.message || 'invalid history JSON'}`, 'note error');
      }
    });

    button.addEventListener('click', () => {
      if (!currentBundle) return;
      const blob = new Blob([JSON.stringify(currentBundle, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `prospective-history-bundle-${safeDateStamp(new Date())}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  return {
    SCHEMA_VERSION,
    recordsFromJson,
    dedupeExact,
    buildBundle,
    attachBrowserUi
  };
});

if (typeof document !== 'undefined' && globalThis.ProspectiveHistoryBundle) {
  globalThis.ProspectiveHistoryBundle.attachBrowserUi();
}
