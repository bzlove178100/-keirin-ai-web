# Phase32 / ML 保留イベント連携（合成入力専用・未公開候補）

追加：合成レビュー内の保留確認・誤申告訂正は `KEIRIN_HELD_HISTORY_REVIEW_20261019.md` を参照。
この転送機能自体は保留解除を行わない。Web/Edgeや通常収集経路への解除反映は未接続。

Draft #266、基準main `d069ab9b6adcf9585954a5bae7be7df0546e473c`。
`ml.held_history_transfer` は、保存済みの保留イベントを別エンジンの保存済みsnapshotへ適用する。
予測の相互変換・再推論ではない。Phase32の予測をMLと改称せず、モデル成果物や予測を捏造しない。
両側の独立したsnapshotが必要で、元の予測・モデルartifact・capture時刻・未確認oddsを保持する。

## 入出力と照合

| 入力の保留履歴 | 必須の別snapshot | 出力のtarget_history |
| --- | --- | --- |
| phase32-held-history-v1 | ml-prediction-snapshot-v1 | ml-held-history-v1 |
| ml-held-history-v1 | prediction-snapshot-v1（Phase32） | phase32-held-history-v1 |

1. 明示的な `synthetic=True` / CLI `--synthetic` が必須。合成入力だけに使用する。
2. 入力保留と対象snapshotを既存の各schemaの検証器・生成器で再検査する。
   通常履歴、未知schema、同一エンジン間、ML artifact不在、digest不一致、安全フラグ改変は拒否。
3. 日付・会場・レース番号を構造化した値で厳密照合する。race_id文字列を分解して推測しない。
   会場の空白除去・別名/大文字小文字の自動置換はなし。日付は実在するISO日付、race_numberは1〜12。
4. 予定発走は同一時点で、JST日付がrace.dateに一致すること。timezone表記の違いだけは許す。
   7/9車の車番構成も一致すること。ML出力に選手本人のIDはないため、本人同一性の照合ではない。
5. イベントは同着・欠車・中止のみ。result_timestampと欠車車番はそのまま保持する。
   結果確認は両snapshotのcapture以降、同着は両方の予定発走以降。欠車/中止の発走前判明は許す。
6. race_idは対象schemaの既存規則で設定する。対象の予測・モデルartifact・capture時刻を維持した保留履歴を作る。

## 連携記録

出力は `held-history-transfer-v1`。source_historyとtarget_historyを両方埋め込み、
両者のSHA-256、構造化レース識別、UTC予定発走、車番構成を記録する。
`validate_transfer` はsourceとtarget snapshotから全体を再生成し、余分なキーも含めて厳密比較する。
`export_target` はこの検査に成功した場合だけ既存schemaの保留履歴をコピーして返す。

連携記録の評価/教師学習適格性・学習実行・DB書込・取得・本番・金銭EV・昇格・hold_releasedはfalse固定。
勝者・結果ラベルは作らない。通常確定への変換、override、保留解除はない。
SHA-256は整合性検査であり署名ではない。両方を作り直せる者に対する改ざん防止、
情報源の真正性、時計の独立検証、利用許諾の証明にはならない。
synthetic指定も申告であり、任意の実データを合成データに変える機能ではない。

## オフラインCLI

以下の入力ファイルは別途生成した合成fixtureに限る。実レースの私有データを使わない。

```sh
python -m ml.held_history_transfer transfer source-held.json target-snapshot.json \
  --synthetic --output transfer-receipt.json
python -m ml.held_history_transfer export-target transfer-receipt.json \
  --synthetic --output target-held.json
```

どちらも既存出力を上書きしない。検証不合格なら出力を作らない。
連携記録を監査用に残し、target-heldを対象エンジンの通常履歴と一緒に既存の評価処理へ渡す。
同じレースの通常履歴は入力順・重複に関係なく除外される。別レースの指標は変えない。
全件保留は評価なし。連携記録そのものを評価器やEdge APIへ渡さない。
履歴を意図的に省略した別入力まで監視する横断状態・DBはない。

## 検証・限界・次工程

ローカル8試験成功：7/9車×3状態×双方向、元予測とモデルの保持、往復時のイベント一致、
同一レース除外と別レース指標不変、identity/schedule/car構成不一致、時差表記、両captureとの因果順序、
source/target/receiptの改変、正常結果へのすり替え防止、合成指定必須、CLI保存/再読込/上書き拒否。
異なる確率表を持つ合成snapshotを用い、対象予測をコピー元へ置き換えないことを検査する。
新しい試験を既存ML workflowへ追加。新headのCI結果はPR本文を正とする。
前head6777d6aは7 CI成功・回帰47/47で完了済み。理由なく再実行しない。

これはPythonのオフライン連携まで。Web/EdgeのML schema直接受入・連携UI、保留解除、
配備済みbackendの実owner受入は未実装/未実施。既存Web/Edge契約を緩めない。
保留解除は次の独立工程で、元記録を残す訂正/審査証拠、競合時の停止条件を定義してから実装する。
実際の同着・欠車・中止を単一勝者の通常学習ラベルへ自動変換しない。

公開・Function配備は未承認。API predict20/history12/backtest11/history-pipeline7は未変更。
KEIRIN.JP HOLD、実取得・実学習・予想DB書込・本番予想OFFを維持する。
将来の配備には別途明示承認、現行20/12/11/7原本保存、段階backend受入、失敗時復元が必要。
#265承認や旧版19/11/10/6 ZIPを流用しない。
