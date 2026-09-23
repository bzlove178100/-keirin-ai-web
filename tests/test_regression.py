import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_golden_manifest_contract():
    data = json.loads((ROOT / "tests/golden/ito9-replay.expected.json").read_text(encoding="utf-8"))
    assert data["usage"] == "diagnostic_regression_only"
    assert data["evaluation_scope"] == "replay_or_legacy"
    assert data["engine_version"] == "phase32-hit-priority-all210-v1"
    assert data["trifecta_score_count"] == 210
    assert data["unique_trifecta_score_count"] == 210
    assert abs(float(data["probability_mass"]) - 1.0) <= 0.02
    assert data["selected_pick_count"] == 15
    assert data["unique_selected_pick_count"] == 15
    assert all(v == 3 for v in data["category_pick_counts"].values())


def test_iwaki_raw_fixture_keeps_kdreams_no_ticket_marker():
    data = json.loads((ROOT / "tests/golden/iwakitaira11-raw-kdreams-input.json").read_text(encoding="utf-8"))
    odds = data["odds"]["trifecta"]
    assert len(odds) == 60
    assert data["prediction_context"]["source"].startswith("K-Dreams")
    bad = [k for k, v in odds.items() if float(v) == 9999.9]
    assert bad == ["2-6-3"]


def test_web_history_and_backtest_contract_present():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    required = [
        "phase32-hit-priority-all210-v1",
        "結果確定 → 履歴JSON生成",
        "履歴生成 → バックテスト（保存なし）",
        "履歴データセット（複数レース）",
        "evaluation_scope",
        "replay_or_legacy",
        "prospective",
    ]
    for text in required:
        assert text in html, f"missing web contract marker: {text}"


def test_prediction_safety_contracts_remain_off():
    data_source = (ROOT / "supabase/functions/predict-engine-dev/data_source_contract.ts").read_text(encoding="utf-8")
    persistence = (ROOT / "supabase/functions/predict-engine-dev/persistence_contract.ts").read_text(encoding="utf-8")
    assert "DATA_SOURCE_MODE='caller_supplied_only'" in data_source
    assert "PRODUCTION_DATA_SOURCE_CONNECTED=false" in data_source
    assert "DB_WRITE_ENABLED=false" in persistence
    assert "PERSISTENCE_MODE='disabled_until_validation'" in persistence


def test_predict_endpoint_keeps_kdreams_sanitizer_before_scoring():
    source = (ROOT / "supabase/functions/predict-engine-dev/index.ts").read_text(encoding="utf-8")
    required = [
        "kdreams_9999_9_unbet_as_unavailable",
        "Number(value)===9999.9",
        "delete (trifecta as Record<string,unknown>)[key]",
        "ignored_count:ignored.length",
        "Unknown odds are never inferred",
        "K-Dreams 9999.9 no-ticket displays are excluded",
        "production_prediction_enabled:false",
    ]
    for text in required:
        assert text in source, f"missing predict sanitizer marker: {text}"
    sanitize_pos = source.index("const sanitized=sanitizeKnownOdds(payload)")
    quality_pos = source.index("const inputQuality=assessInputQuality(normalized)")
    predict_pos = source.index("buildFullPredictionWithWeights(normalized)")
    assert -1 not in (sanitize_pos, quality_pos, predict_pos)
    assert sanitize_pos < quality_pos < predict_pos


def test_history_builder_safety_scope_and_training_eligibility_contract():
    source = (ROOT / "supabase/functions/history-builder-dev/index.ts").read_text(encoding="utf-8")
    required = [
        "db_write_enabled:false",
        "external_fetch_enabled:false",
        "production_prediction_enabled:false",
        "replay_or_legacy",
        "prospective",
        "unknown result time is allowed only for replay_or_legacy",
        "prediction_timestamp must be earlier than result_timestamp for prospective evaluation",
        "exclude from prospective accuracy claims",
        "keirin-training-input-v1",
        "backtest-record-v2",
        "training_input:trainingInput",
        "training_eligibility",
        "supervised_training:supervisedTraining",
        "contains K-Dreams no-ticket marker 9999.9",
        "evaluation_scope==='prospective'&&temporal_order==='prediction_before_result'&&trainingInput!==null",
    ]
    for text in required:
        assert text in source, f"missing history/training safety marker: {text}"


def test_history_pipeline_safety_temporal_and_training_capture_contract():
    source = (ROOT / "supabase/functions/history-pipeline-dev/index.ts").read_text(encoding="utf-8")
    required = [
        "buildTrainingInput",
        "db_write_enabled:false",
        "external_fetch_enabled:false",
        "production_prediction_enabled:false",
        "evaluation_scopes:['prospective','replay_or_legacy']",
        "unknown result time is allowed only for replay_or_legacy",
        "snapshot.captured_at must be earlier than settlement.result_timestamp for prospective evaluation",
        "snapshot is not eligible for prospective evaluation",
        "training_input:trainingInput",
        "supervised_training_eligible",
        "supervised training is disabled",
        "No database writes or external result fetches occur",
    ]
    for text in required:
        assert text in source, f"missing pipeline training/safety marker: {text}"


def test_training_input_module_removes_no_ticket_markers_and_excludes_targets():
    source = (ROOT / "supabase/functions/history-pipeline-dev/training_input.ts").read_text(encoding="utf-8")
    required = [
        "keirin-training-input-v1",
        "ignored_combos",
        "Number(raw[key])===9999.9",
        "delete raw[key]",
        "removed_combos",
        "evaluation_scope:evaluationScope",
    ]
    for text in required:
        assert text in source, f"missing training input marker: {text}"
    forbidden = ["outcome_combo", "settlement_odds", "result_timestamp"]
    for text in forbidden:
        assert text not in source, f"target leakage field present in training input builder: {text}"


def test_backtest_contract_separates_scope_roi_and_probability_quality():
    source = (ROOT / "supabase/functions/backtest-engine-dev/index.ts").read_text(encoding="utf-8")
    required = [
        "backtest-v3-settlement-aware-multiclass",
        "db_write_enabled:false",
        "production_prediction_enabled:false",
        "xs.length!==210",
        "keys.size===210",
        "Math.abs(mass-1)<=0.02",
        "prospective_records",
        "replay_or_legacy_records",
        "settlement_odds",
        "multiclass_log_loss",
        "multiclass_brier_sum",
        "calibration_bins",
        "replay/legacy records are diagnostic only",
    ]
    for text in required:
        assert text in source, f"missing backtest contract marker: {text}"


if __name__ == "__main__":
    test_golden_manifest_contract()
    test_iwaki_raw_fixture_keeps_kdreams_no_ticket_marker()
    test_web_history_and_backtest_contract_present()
    test_prediction_safety_contracts_remain_off()
    test_predict_endpoint_keeps_kdreams_sanitizer_before_scoring()
    test_history_builder_safety_scope_and_training_eligibility_contract()
    test_history_pipeline_safety_temporal_and_training_capture_contract()
    test_training_input_module_removes_no_ticket_markers_and_excludes_targets()
    test_backtest_contract_separates_scope_roi_and_probability_quality()
    print("keirin-ai regression checks: PASS")
