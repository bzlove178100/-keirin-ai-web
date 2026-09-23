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


def test_history_builder_safety_and_scope_contract():
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
    ]
    for text in required:
        assert text in source, f"missing history safety marker: {text}"


def test_history_pipeline_safety_and_temporal_contract():
    source = (ROOT / "supabase/functions/history-pipeline-dev/index.ts").read_text(encoding="utf-8")
    required = [
        "db_write_enabled:false",
        "external_fetch_enabled:false",
        "production_prediction_enabled:false",
        "evaluation_scopes:['prospective','replay_or_legacy']",
        "unknown result time is allowed only for replay_or_legacy",
        "snapshot.captured_at must be earlier than settlement.result_timestamp for prospective evaluation",
        "snapshot is not eligible for prospective evaluation",
        "No database writes or external result fetches occur",
    ]
    for text in required:
        assert text in source, f"missing pipeline safety marker: {text}"


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
    test_web_history_and_backtest_contract_present()
    test_prediction_safety_contracts_remain_off()
    test_history_builder_safety_and_scope_contract()
    test_history_pipeline_safety_and_temporal_contract()
    test_backtest_contract_separates_scope_roi_and_probability_quality()
    print("keirin-ai regression checks: PASS")
