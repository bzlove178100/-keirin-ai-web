# Phase32 結果申告ガード（未公開候補）

2026-10-18。基準main `d069ab9b6adcf9585954a5bae7be7df0546e473c`。
#265は公開済み。今回の変更はその承認範囲外で、マージ・配備未承認。

## 問題と対象

Phase32のbrowser buildHistory、history-pipeline、history-builderは、
結果に `result_status` や `dead_heat` を渡しても捨てて通常履歴を作れていた。
既存ML model_historyの保留契約を参考に、まず通常履歴の入口を閉じる。

- 省略された旧形式は互換維持。省略を正常確認済みと扱わない。
- `result_status: normal` は受理し、生成履歴のmetadataへ保持する。
- 同着・欠車・中止、不明/nullの状態、未対応のキーを拒否する。
- Edgeでは422、saved=false、db_write_enabled=false、子Function呼出しなし。
- ブラウザcoreでは履歴を返さず例外とする。
- 結果状態をtraining_inputへ入れない。認証、owner、OFF条件は不変。

この候補は保留記録を生成しない。既存履歴への直接取込、backtest/datasetの
結果状態検査、Python Phase32 settlement、結果選択UI、ML保留履歴との連携は
未接続。通常履歴入口のガードを、全経路の保留処理完成とは扱わない。
保留から通常結果への無条件な上書きや同着の単一着順化は実装しない。

## 検証

変更前の新規結合試験で明示normalが失われることを再現。
変更後 `node tests/test_history_pipeline_local.cjs` が7/9車で成功。
既存browser core試験も同harness内で成功。通常宣言保持、非標準宣言拒否、
子Function非呼出し、保存OFFを実handlerと合成owner/子通信で検査した。
配備済みAPI・実ownerの受入ではない。実データ利用・再学習は0。
新headのリモートCIはPR本文で記録する。#265の合格済み試験は再実行しない。

## 次工程・復元

保留を独立schemaで表し、同一レースに保留があれば通常履歴も評価から除くML契約を
Phase32へ設計・実装する。通常予測・学習ラベルを捏造せず、不正な保留も検査する。
UI、offline/Edge、履歴取込、学習/評価、重複解決を揃えてから全経路接続と判定する。
新規公開の前には個別承認と変更対象backendの受入が必要。
現行API predict20/history12/backtest11/history-pipeline7は未変更。
将来の配備時はこれらの現行原本を復元用に保存する。#265の旧版19/11/10/6を
本候補の復元版として流用しない。
GitHub上でmainとopen PR #250/#257を照合し、コード重複はない。
非公開Workや未push作業の内容は確認できていない。
