# 保留確認・誤申告訂正（合成レビュー専用・未公開候補）

Draft #266、基準main `d069ab9b6adcf9585954a5bae7be7df0546e473c`。
`ml.held_history_review` は、保留を確認した記録と根拠を保存し、誤った状態申告を訂正した
合成ケースだけ、元の確率表を使って再評価する。元の保留履歴を削除・上書きしない。

## 2つの判断

| decision | 必要な根拠 | レポート内の扱い |
| --- | --- | --- |
| confirm_nonstandard | 元の同着/欠車/中止と一致する合成結果。欠車車番も一致 | confirmed_excluded。確認完了、評価対象外を維持 |
| correct_declaration | 状態の誤申告であり、通常結果であることを示す合成結果と訂正理由 | 全保留の確認・競合検査に合格したレースだけreleased_for_synthetic_review |

実際の同着・欠車・中止を単一勝者へ変換する機能ではない。誤申告の訂正は明示操作であり、
通常結果を後から追加しただけでは解除しない。現在は生成した合成入力だけが対象。
実データの利用可否・実レース結果の真正性・ユーザーの公開/配備承認とは別の契約である。

## 必須入力

各確認記録は、既存の有効な `phase32-held-history-v1` または `ml-held-history-v1` 1件、
根拠 `synthetic-result-evidence-v1`、判断の3入力から作る。全処理で明示的なsynthetic指定が必須。
元schemaの完全検査に加え、日付/会場/番号・予定発走・7/9車の車番構成を厳密照合する。
選手本人IDはML snapshotにないため照合しない。会場の別名解決や推測は行わない。

根拠のキーは以下だけを受け付ける。

```json
{
  "schema_version": "synthetic-result-evidence-v1",
  "evidence_scope": "synthetic_test_only",
  "fixture_id": "generated-result-case",
  "race_identity": {"date": "2026-10-17", "venue": "SYNTHETIC", "race_number": 7},
  "scheduled_start": "2026-10-17T11:00:00+09:00",
  "car_numbers": [1, 2, 3, 4, 5, 6, 7],
  "result": {
    "result_status": "normal", "result_timestamp": "2026-10-17T02:20:00Z",
    "outcome_combo": "1-2-3", "settlement_odds": 40
  }
}
```

上記は生成fixture用の例。実データや別レースへ流用しない。
非標準確認ではresultを元のstatusとresult_timestampだけにし、withdrawnのみ元と同じwithdrawn_car_numbersを加える。
勝者・oddsを同時に渡すことや、余分なキー、boolの車番/odds、未知statusは拒否する。
根拠の結果確認時刻は元の保留確認時刻以降。normal/dead_heatは予定発走以降。

判断は `decision`、timezone付き `reviewed_at`、`reviewer_id`、空でない `reason` の4キー。
reviewed_atは根拠の結果確認以降。reviewer_idは `synthetic-`、fixture_idは `generated-` で始まる識別子。
識別子・理由・根拠は申告値であり、本人認証・第三者の確認・許諾を証明しない。

## 記録と競合規則

`held-history-review-v1` は元履歴・根拠・判断をすべてコピーし、元履歴と根拠のSHA-256を保持する。
validate_reviewは全体を再生成して厳密比較する。変更したフラグ・余分なキーも拒否する。
確認記録単独ではhold_released/evaluation_eligible=false。解除要求は一括検査に渡す。
digestは署名ではなく、入力全体を作り直せる者への改ざん防止を保証しない。

一括評価は `held_records` と `reviews` の2配列だけを受ける。通常履歴は受け付けない。
日付/会場/番号で両エンジンの保留を同じレースへまとめ、次の順で判定する。

1. 不正な元履歴/確認記録、入力に存在しない履歴を参照する確認記録は要求全体を拒否。
2. 同じレースの予定発走/車番構成の食い違い、1履歴への異なる確認記録、確認漏れはそのレースを未解決にする。
3. 訂正と非標準確認の混在、異なる訂正結果はそのレースを未解決にする。後日時刻による自動上書きなし。
4. 全件が非標準確認ならconfirmed_excluded。勝者・確率指標を作らない。
5. 全件が同一通常結果への訂正なら、エンジンごとに最新の保存予測を選ぶ。
   同じ保存時刻に異なるsnapshotがあれば、レース全体を未解決にする。
6. 合格レースだけ、その元確率表で固定予測の順位/log-loss/Brier等を計算する。
   Phase32とMLの指標は別集計。両者を混ぜた平均や金銭指標を作らない。

完全重複の履歴/確認記録は件数を増やさず、入力順でも選択を変えない。
訂正結果の時刻は同一時点のtimezone表記差を許し、oddsの40と40.0は同値とする。
新しい未確認の保留が同じ入力に加わった場合は、以前の訂正があっても再び評価対象外になる。
別レースの指標は影響を受けない。評価対象が0件なら指標nullで、0%として集計しない。

## オフラインCLI・保存

```sh
python -m ml.held_history_review create-review held.json evidence.json decision.json \
  --synthetic --output review.json
python -m ml.held_history_review evaluate batch.json \
  --synthetic --output review-report.json
```

出力は上書き不可。検証失敗では出力なし。評価対象0件では監査レポートを保存しexit 2を返す。
レポートは元履歴と確認記録を全件保持する。解除の効力はこの入力一式に対する合成レビュー内だけ。
履歴ファイルを省略した別入力や、未提供の別エンジン保留を横断検知する永続状態はない。
元履歴・根拠・確認記録を一緒に保存し、再開時には同じ入力一式で照合する。

通常履歴や学習データへのexportは設けない。既存のpartition_holds/evaluate_historiesは元保留を引き続き除外する。
学習/DB/外部取得/本番/金銭EV/昇格はOFF。snapshot・モデル・予測時odds・captureは不変。
Web/Edge UI、実owner認証下の訂正、実データ向け審査/権限/永続記録、通常収集経路への解除反映は未接続。

## 検証と引き継ぎ

新規11試験成功：7/9車×3状態×両エンジン、確認/訂正/未解決、元予測保持、欠落・追加保留、
重複/順序、訂正結果/判断/schedule/car/最新snapshot競合、別レース指標不変、証拠/時刻/フラグ改変、
CLI保存/再読込/上書き拒否、未解決レポート、既存学習/履歴ガードの維持を検証した。
新規試験は既存ML CIに追加。新head CI結果はPR本文に記録する。
前head78488e8は7系統CI成功、回帰39197013687も47/47成功。理由のない再実行なし。

公開/Function配備未承認。API predict20/history12/backtest11/history-pipeline7を維持。
KEIRIN.JP HOLD、実取得・実学習・予想DB書込・本番予想OFF。
将来の配備には別途明示承認、現行20/12/11/7原本保存・段階backend受入・失敗時復元が必要。
#265の承認と旧版ZIPは今回へ流用しない。
