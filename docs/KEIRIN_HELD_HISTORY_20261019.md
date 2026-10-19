# Phase32 オフライン保留履歴（未公開候補）

基準main `d069ab9b6adcf9585954a5bae7be7df0546e473c`。
Draft #266のガード `7a4fa23bdb2e32d79a40b899d917160c553ee8c2` に追加。
その旧headの7 CIすべて成功、回帰39128022537も47/47成功。成功済み試験の再実行なし。
新しいコード変更に関係する試験だけローカルで実行。新head CIはPR本文に記録する。

## 契約

`phase32-held-history-v1`は通常のbacktest-record-v2とは別schema。
保存済みsnapshotをコピーし、race_id・prediction_timestamp・settlementを保持する。
`settlement`は `result_status` と timezone付き `result_timestamp` のみ。
statusは `dead_heat` / `withdrawn` / `cancelled`。
withdrawnのみ `withdrawn_car_numbers` が必須で、空・重複・型違い・名簿外は拒否。
時刻はcapture以降。同着は予定発走以降も必須。欠車・中止は発走前の判明を許す。
勝者・払戻・学習ラベルは生成せず、評価/学習適格性とDB/外部取得/本番/金銭EVをfalse固定。
保存snapshotの内部整合性を検査するが、情報源の真正性・利用許諾・改ざん耐性の証明ではない。

有効な保留を先に収集し、同じrace_idの通常履歴を新旧・読込順に関係なく全除外する。
重複保留は保留レース数を増やさない。不正な保留はinvalid_held_recordとして除外し、
正常な別記録を抑止する根拠にしない。未知の正常履歴注記も学習適格とみなさない。
通常結果での上書き解除・overrideはなし。保留と通常履歴は一緒に渡す必要がある。
私有JSONを意図的に省略した別入力まで横断する状態・DBは持たない。

## 接続範囲

- `prospective-tools.html`：3状態の選択、保留JSON保存、通常履歴との再読込、保留件数表示、統合保存。
  入力変更時に前の保存対象を無効化。外部通信なし、端末ファイルのみ。
- browser coreとPython `ml.held_history.build_held_history` は同じJSON契約。
- collection status / evaluation_protocol / dataset build_rows は同じレースの通常履歴を除外。
  明示非標準状態を持つ通常レコードも学習対象外。合成試験でクロス言語照合。
- owner indexの履歴取込は保留を保持する。APIバックテストは未対応なので混在時は実行しない。
  検査scriptが不在なら通常履歴だけを取込まず停止し、旧データセット/バックテスト入力を消去。
- 既存の統合JSON形式で保留も保持。保存は明示的なJSONダウンロードで、DB保存ではない。

Edge側は通常結果注記ガードを維持し、有効な保留の生成・同一レース除外集計を未公開コードへ接続済み。
ML model_historyの保留優先規則に合わせたが、MLモデルsnapshot/schemaとの相互変換は未実装。
直接APIに非標準注記付き通常履歴を渡す経路の拒否ガードは下記の追加修正で接続した。
Python通常settlement CLIに保留オプションは追加していない（Python関数とブラウザ入口あり）。

## 検証と次工程

- 新規Python5試験：7/9車×3状態のJS/Python JSON一致、順序・重複、学習/評価/収集除外、
  発走前欠車/中止、時刻不正、欠車名簿不正、偽の適格フラグ/ID/勝者、不正レコード耐性。
- 既存dataset、collection5、settlement12、browser core/private bundle/collection UI試験成功。
- 実Web script＋合成owner/実handlerの7/9車結合で保留保持・API不呼出し・script不在時停止を確認。
- UI生成器の再適用はalready applied、diff check成功。
- Chromeがローカルにないため、390/1280幅の保存・再読込・統合保存の実ブラウザ試験を既存ML CIへ追加。
  新head CI成功まで画面受入完了と扱わない。配備済みAPIの実owner受入ではない。

次は新head CIと未解決QMP失敗を確認し、owner画面の保留API操作と全経路の受入を進める。
現在APIはpredict20/history12/backtest11/history-pipeline7。今回未配備。
公開・配備には別途明示承認と変更対象backendの受入が必要。#265承認の拡張なし。
将来の配備前には現在の原本を保存し、段階受入失敗時はその版へ復元する。
#265の旧版19/11/10/6を今回の復元対象として流用しない。
KEIRIN.JP HOLD、実取得・実学習・DB書込・本番予想OFF。
GitHubの他open PR #250/#257に対象コード重複なし。非公開Work/未push作業は未確認。

## 2026-10-19 直接履歴入力の拒否ガード（前段階。下記の有効保留受入を追加）

backtest-engine-devがroot/metadataのresult_statusを捨てて通常指標を返す問題を、
合成の同着申告で再現（修正前200、期待422）。修正後は混在要求全体を422で拒否し、
部分的な指標を返さない。保存OFF、子Function呼出しなし。認証とowner照会は既存のまま。

- rootとmetadataのstatusは省略またはnormalのみ互換受入。省略は正常結果の証明ではない。
- dead_heat / withdrawn_car_numbers / trifecta_outcomes / settlementは存在だけで拒否。
  false、空配列、nullも黙って捨てない。
- phase32-held-history-v1とml-held-history-v1は通常ラベルを付加しても拒否。
  Pythonの直接適格判定とbrowserの収集判定にも同じ保留schemaガードを追加。
- 不正なmetadata型もAPIで拒否。通常レコードへの明示normal追加で全指標が一致。
- APIは保留を受入・除外集計する段階には達していない。保留を含む評価はオフライン経路を使用する。

変更対象の合成試験のみ実行：7/9車のroot/metadata×status/補助項目/保留schema、
通常記録との前後順混在、保留JSON、metadata異常を実handlerで確認。
Python5試験にschema偽装とJS収集照合を追加して成功。実Web script＋実handlerも7/9車成功。
前head e5f561のChrome（ML CI39176166356）は保存・再読込・統合成功。
この追加修正のCI結果はPR本文でheadを区別して記録する。新規配備・実owner backend受入なし。

## 2026-10-19 Edge保留生成・除外集計（現在の未公開候補）

history-pipeline-devは既存の認証/owner照会後、3状態のsettlementを受ける。
prospective-onlyの不変snapshotを再検査し、browser/Pythonと同一の保留JSONをhistory_recordとして返す。
勝者・払戻・training_inputを作らず、通常builder/backtest子Functionも呼ばない。
backtest_resultはnull、prospective_eligible/supervised_training_eligibleと各安全フラグはfalse。
呼出し側のrace_id上書き、replay scope、通常結果との混合settlementは拒否する。

backtest-engine-devは有効なphase32-held-history-v1を受け入れ、同じrace_idの通常履歴を
新旧・入力順に関係なく全除外する。重複保留はheld_unique_racesを増やさない。
input_records、held_race_ids、excludedを返し、残った通常レースだけ既存指標を計算する。
通常レースが0件ならevaluation_performed=false、通常の3指標群はnullとする。
不正保留が混ざるAPI要求は全体422で拒否し、部分指標を返さない（オフラインの除外集計とは異なる）。
ml-held-history-v1の直接投入・非標準注記付き通常履歴は引き続き拒否。schema相互変換は未実装。
両APIのGETはheld_history_schemaとheld_result_supportedを通知する。
owner画面はまだ保留APIを無効にしており、この候補の配備や実owner受入は未実施。

共通snapshot検査のエンジン識別子優先順の差により、矛盾した識別子をPythonだけ受け入れる例を
追加試験で発見。保留入口で存在する両識別子を検査し、3経路とも拒否するよう修正。
Python6試験で7/9車×3状態のJSON一致、発走前欠車/中止、15種類のsnapshot異常、
時刻/名簿/注記不正、改変保留、除外規則を確認。実handlerでは保留生成、通常子Function不呼出し、
全件保留の指標null、別レースの全指標不変、混在順、未認証拒否を確認した。
Web結合7/9車とweb/safety回帰も成功。Deno module graph CIにhistory-pipelineを追加。
QMP失敗の調査記録は`docs/CI_QMP_FIRST_FRAME_20261019.md`。全必須CI成功や恒久修正とは扱わない。
