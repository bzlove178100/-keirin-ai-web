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


def test_safety_contracts_remain_off():
    data_source = (ROOT / "supabase/functions/predict-engine-dev/data_source_contract.ts").read_text(encoding="utf-8")
    persistence = (ROOT / "supabase/functions/predict-engine-dev/persistence_contract.ts").read_text(encoding="utf-8")
    assert "DATA_SOURCE_MODE='caller_supplied_only'" in data_source
    assert "PRODUCTION_DATA_SOURCE_CONNECTED=false" in data_source
    assert "DB_WRITE_ENABLED=false" in persistence
    assert "PERSISTENCE_MODE='disabled_until_validation'" in persistence
