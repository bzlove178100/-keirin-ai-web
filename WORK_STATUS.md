# Work status

## FINAL 5 synthetic experiment history UI — 2026-10-21

再開照合：main d069ab9b6adcf9585954a5bae7be7df0546e473c、#267 2f0e2ad98bdf1a6e8c9010cce596cd3be8a99684。
直前headは全7CI/回帰39557798031の47件/ML39557798046のWorkbench92＋ranker/両台帳30＋既存実Chrome成功。
runtime39557798016/job119081578588の2026-10-21T07:02:08.4016812Zログで同一40桁head verified=true。
#266 ae2658f7acadb597bf67217c165afe722a651587、main、#250/#257は不変。非公開/未push Workは未確認。
PR冒頭/末尾・#266配備条件・AGENTS/SOURCE/要件/WORK/第二段階AI/保留契約を照合。旧成功CIの再実行なし。

次の許可済み合成開発として、既存実験台帳の閲覧画面を追加。
--final-five-experiment-ledgerでrepo外の既存checkpointを明示指定する。省略は記録有無不明として表示。
起動時に元台帳の計画/モデル/reportを検証して固定、GETごとに元バイト列を確認する。
変更/欠落/unsafe fileは表示停止、元に戻してもprocess再起動まで再採用しない。台帳ロック/書込/学習なし。
状態/条件/再試行元/失敗/中断/ローカル時刻/先行登録とのレース重複/6層の同点数比較を表示。
raw履歴/native model/per-race結果/私有例外詳細はAPIに渡さない。未指定/0件/未知ID/失敗を区別する。
比較モデルと保存済み選定から同じモデルIDの全完了記録へ接続。hash一致は来歴や独立評価の証明ではない。
選定台帳schema/資格やtraining_attempts_tracked=falseは変えず、参照だけを追加。
実JSで型/安全フラグ/状態/参照/比較合計を検証。失敗と遅い旧応答で以前の詳細やリンクを残さない。

ローカル新規Python/API6＋影響する既存実験台帳12/比較6/選定6＝計30試験成功。JS構文/diff check成功。
新規実Chrome2（390/1280px）は一覧/再試行元/モデル一致複数/比較・選定リンク/重複/XSS文字表示、
不正・遅い旧応答、未知ID/保存物変更、SIGKILL再起動、未完runningを学習せず表示、未指定区別、
元ファイル不変・GETのみ・外部通信なしを確認する。ML CIに追加し、実Chromeの確定はこれから。
このWorkのローカルChrome実行環境は利用できず、既存CIの実Chromeを使用。依存導入の反復はしない。
新headのCI確定結果は#267本文だけへ保存し、記録だけのcommit/手動再実行/取消しなし。
契約：docs/KEIRIN_FINAL_FIVE_RANKER_20261021.md「合成実験の閲覧とモデルIDからの照合」。

残件：実験登録/実行/abandon/モデル切替の画面操作、第一段階を含む独立評価/実用特徴、
商品目的変数/受入、DREAM、会員/課金/許諾済み実データ受入。旧fit/別台帳/人間の閲覧/外部保留は未追跡。
合成成功を実精度/利益/商品完成と扱わない。API20/12/11/7は記録値、KEIRIN.JP HOLD、
実取得/実学習/予想DB書込/本番予想OFF。#266/#267マージ・公開・Function配備は未承認。
#266の現行原本保存/段階backend受入/復元・旧承認/旧ZIP不流用を維持する。

## FINAL 5 preregistered synthetic experiment ledger — 2026-10-21

再開照合：main d069ab9b6adcf9585954a5bae7be7df0546e473c、#267 b9a1568184eae043567f96e47165e139c2878b82。
直前headは全7CI/回帰39551502665の47件/ML39551502728のWorkbench92＋ranker/台帳18＋実Chrome成功。
runtime39551502736/job119061512647の2026-10-21T06:00:09.2804714Zログで同一head verified=true。
#266 ae2658f7acadb597bf67217c165afe722a651587、#250/#257、mainは不変。非公開/未push Workは未確認。
PR冒頭/末尾とAGENTS/SOURCE/要件/WORK/第二段階AI・保留確認契約を照合。成功済みCIは再実行しない。

次の許可済み合成開発としてml.final_five_experiment_ledgerを追加。
学習前の入力/固定条件/学習・検証manifest登録→running保存→1回の学習→結果保存。
同IDの応答再試行は再学習なし。failed/interrupted/blockedも保持し、同条件再試行は最新元ID＋別ID＋理由が必要。
未解決runningは結果不明として明示abandonを要求。自動再試行/再開/昇格は追加しない。
inspectは全先行登録（未実行/失敗も含む）の検証再使用/学習と検証の移動をrace IDで表示する。
元入力一式・モデル/reportを保存、復元時は元manifestと再推論reportを照合し再学習しない。
5入力一式/各200履歴・8 MiB/20実験/全体32 MiB、超過は削除せず拒否。既存SessionStoreの別ファイルで保存。
exportは既存{model,report}形式で比較画面と互換。旧fit/別台帳/画面選定との追跡は未接続。

ローカル新規11試験＋追加の保留/競合/除外1試験＝12成功。影響する既存ranker9試験も成功。
実LightGBMの事前保存/別process再読込/CLI互換、学習例外・KeyboardInterrupt、
実SIGKILLの学習中/terminal置換前後3境界、fsync失敗前後、結果不明時の再実行拒否、
明示再試行/入力順序・cutoff変更時の重複、再hash破損/上限/ロック/外部変更/元入力不変を確認。
rankerの共通計画・学習・再評価を分離したが、学習方式/parameters/点数/基準は変更しない。
既存ML CIのtest_final_five*.pyで自動実行。画面変更/新規Chrome/CI条件変更なし。
新headのCIはこれから確定し、結果を#267本文だけへ保存する。記録だけのcommit/手動再実行/取消しなし。
契約：docs/KEIRIN_FINAL_FIVE_RANKER_20261021.md「学習前の実験登録・中断と再試行の記録」。

残件：実験台帳の画面操作/選定との追跡接続、第一段階を含む独立評価/実用特徴、商品目的変数/受入基準、
DREAM、会員/課金/許諾済み実データ受入。旧fit/別保存先/人間の事前閲覧や外部保留は横断検知しない。
ローカル時計/digestは来歴・独立性・実精度・利益の証明ではない。evaluation_eligible/product_acceptance=false。
API20/12/11/7は記録値、KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF。
#266/#267マージ・公開・Function配備は未承認。#266現行原本保存/段階受入/復元条件と旧承認/ZIP不流用を維持。


## Selection UI Chrome wait correction — 2026-10-21

#267 0301a60fc7f080d7a649ae8888a8b7e14d05da58のML39550765017/job119059187705がfailure。
保存ログ2026-10-21T05:43:17.6192292Z：新規Chrome試験70行のpage.waitForLoadState('networkidle')が30秒timeout。
遅い対象応答の受信後に、先行する意図的な応答喪失も含むページ全体の通信停止を待っていた。
その前の応答喪失→同ID再送/reload/選び直し/不正照会はassertion通過、後続の保留/再起動ケースは未確認。
Python Workbench92（新規6含む）とranker＋台帳18、既存Chromeは成功。旧成功分を失敗とは扱わない。
修正は新規試験だけ：対象response.finished＋描画サイクルで処理を待ち、旧応答で詳細が復活しないassertionを維持。
製品コード/待機期限/CI条件は変更しない。JS構文/diff check成功。修正後の実Chrome/全CIはPR本文で確定する。
失敗runの無条件再実行/取消しなし。0301a60の回帰/runtimeは取り消さず結果を保存する。
API20/12/11/7記録値、HOLD/OFF、マージ/公開/Function配備未承認・#266原本/段階受入/復元条件を維持。

## FINAL 5 selection saving from synthetic comparison UI — 2026-10-21

直前#267 07ef97b8ec961b5d66539cc6431a0723f8a65a34の選定台帳CLIは全7CI/回帰39549344298の47件成功。
runtime39549344364/job119054714213の2026-10-21T05:35:11.1072160Zログで同一head verified=true。
ML39549344154/job119054713388で新規台帳9＋ranker9＝18、Workbench86、既存Chrome成功。
確定結果は#267本文/#266末尾へ保存。記録だけのcommit・旧成功CIの手動再実行/取消しなし。
main d069ab9b6adcf9585954a5bae7be7df0546e473c、#266 ae2658f7acadb597bf67217c165afe722a651587は不変。

次の許可済み合成開発として、--final-five-selection-dirの明示時だけ比較画面から台帳へ保存できるようにした。
理由と保存要求IDを持ち、保存直前にmodel/snapshot/同セッション保留/元保存物を再検査。
閲覧/再確認だけでは追記なし、予測/通常結果/保留/確認一式は不変。台帳の既存検証/復元/上限を再利用。
ブラウザは送信前に要求を保持し、応答喪失は未確認として同IDで照会/再送。成功後の明示選び直しは新ID。
再読込で保持IDを照会。不正な控え/返却値/遅い旧照会を拒否。モデルなし/保留後でも過去記録の確認だけは可能。
別origin/端末では控えを共有しない。ID手入力またはCLI inspect/showで確認。自動学習/昇格/保留解除なし。
新規Python/API6＋影響する既存challenger6がローカル成功、実API→実JS検証関数と不正な内側安全主張の拒否も成功。
JS構文/diff check成功。新Chrome2（390/1280幅・7/9×3/4/5保存、応答喪失/再送/reload/SIGKILL再起動、
選び直し、不正/旧照会、送信前保留、控え破損、モデルなし過去照会）をML CIへ追加。
新headの全CI/実Chrome確定結果は#267本文を優先し、記録だけでcommit/CIを再起動しない。
契約：docs/KEIRIN_FINAL_FIVE_RANKER_20261021.md「合成比較画面から選定を保存・確認」。

残件：学習前の実験登録/失敗/再試行/検証集合の再使用記録、商品評価軸/受入、第一段階を含む独立評価、DREAM、会員/課金/実データ受入。
後からの合成選定記録であり、実精度/利益/前向き実績/商品受入ではない。別保存先の保留検知なし。
API20/12/11/7記録値、KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF。
#266/#267マージ・公開・Function配備未承認。将来の現行原本保存・段階受入・復元は#266本文を厳守。

## FINAL 5 persistent synthetic selection ledger — 2026-10-21

再開時照合：main d069ab9b6adcf9585954a5bae7be7df0546e473c、#267 cb632bed30666eec361df61019b85c7f1a8db3c7。
直前は全7CI/回帰39546345773の47件/ML39546345784のPython86・ranker9・実Chrome2成功。
runtime39546345822/job119045279911で同一head verified=true。#267本文の確定結果を再利用。
#266 ae2658f7acadb597bf67217c165afe722a651587、#250/#257とmainは不変。非公開/未push作業は未確認。

残件のモデル管理/選定保存として、合成専用ml.final_five_selection_ledger CLIを追加。
モデル本体・元snapshot・同点数の基準/AI選定・理由・順序・保存時刻をrepo外へ保存。
復元時にモデル/入力/選定を再計算照合し、不一致は拒否。実行/復元で学習なし、元ファイル不変。
同一request-idの同内容再試行は重複なし、別内容は拒否。新IDでの選び直しは以前の記録を保持。
inspect/showで選び直しと1件の選定を確認できる。最大5モデル/20snapshot/100選定/32 MiB、超過時は削除せず停止。
既存SessionStoreのlock/atomic replace/fsyncを別ファイルで再利用。保存不確実時は全操作を再起動まで停止。
新規9試験がローカル成功：7/9×3/4/5、別process再読込、重複/モデル変更、破損/上限、
fsync障害、実SIGKILL前後2境界、lock/外部変更/入力link/FIFO/サイズ、CLIと原本不変。
ML CIへ新規9試験を追加。既存Web/UI/API変更なし、新規Chromeなし。新headのCI確定結果は#267本文へ保存する。
記録だけのcommit・旧成功CIの手動再実行/取消しなし。
契約/CLI/保存と復元：docs/KEIRIN_FINAL_FIVE_RANKER_20261021.md「モデルと選定の永続台帳」。

本記録は後からの合成選定でevaluation_eligible=false。発走前実績/実精度/利益/商品受入ではない。
保留入力を持たないstandalone台帳で横断hold検知/解除なし。学習再試行の追跡も未実装と明記。
次の残件：画面からの保存、学習前の実験登録/失敗/再試行/検証集合の再使用記録、商品評価軸と受入、
第一段階を含む独立評価、DREAM、会員/課金/実データ受入。商品仕様/価格を推測で決定しない。
KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF、API20/12/11/7は記録値。
#266/#267マージ・公開・Function配備未承認。将来の現行原本保存/段階backend受入/復元は#266本文を維持。

## FINAL 5 saved-model comparison display — 2026-10-21

再開照合：main d069ab9b6adcf9585954a5bae7be7df0546e473c、#267 c3395104cab7debc6c6b77f2096a1327024c1f5b。
全7CI成功、回帰39544435728は47/47、runtime39544435731/job119039280176で同一head verified=true。
成功確定を#267本文/#266末尾へ保存し、記録だけのcommit/手動再実行/取消しなし。
#266 ae2658f7acadb597bf67217c165afe722a651587、#250/#257不変。非公開/未push作業は未確認。

残件の画面接続として、保存済み第二段階モデルを明示指定した場合だけ起動時に検証/固定する。
既存snapshotから基準と試作を同点数で比較。モデル未指定/学習済みrace/cutoff前/同セッションML保留はAI候補なし。
元値と不足、未校正比較スコア、モデルhash/cutoffを表示し、本文/manifest/結果/reportは返さない。
再確認時/失敗時に旧候補を消去、遅い応答破棄。予測/履歴/判断の書込や画面からの再学習なし。
モデルファイル変更は稼働中へ自動反映せず、再起動時に再検証。不正モデルでは起動拒否、暗黙fallbackなし。
新規Python/API6＋既存基準6がローカル成功。初回のfixture時刻不整合を修正し製品の検査は維持。
JS構文/diff check成功。新Chrome2（390/1280幅、各7/9車×3/4/5点）と変更headの全CIは#267本文で確定する。
前Workのscratch/ログイン/モデル/依存ライブラリを仮定せずGitHub保存物から再取得した。
契約/起動例：docs/KEIRIN_FINAL_FIVE_RANKER_20261021.md「保存済みモデルの画面接続」。

残件：商品受入基準/実用特徴/第一段階を含む独立評価、実験選択の記録、モデル管理/選定保存、DREAM、会員/課金/実データ受入。
KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF、API20/12/11/7は記録値。
マージ/公開/Function配備未承認。現行原本保存/段階backend受入/復元は#266本文を維持。

## FINAL 5 learned challenger — 2026-10-21

再開照合：main d069ab9b6adcf9585954a5bae7be7df0546e473c、#267 20e4ba0cfaf6058e0901350943309df17e2712ac。
前head全7CI/回帰39541374349の47件、ML39541374298のPython80/新規Chrome2、runtime39541374348 verified=trueを再利用。
#266 ae2658f7acadb597bf67217c165afe722a651587、#250/#257は変更なし。非公開/未push Workは未確認。

次の合成専用開発として第二段階AIのオフライン試作を追加。既存最大15候補の勝者分類をLightGBMで学習し最大5点へ選ぶ。
目的変数/特徴/固定parameterは技術検証の選択で、確定商品仕様とは扱わない。既存の基準/画面/第一段階を置換しない。
明示cutoffで予測と結果の両方が前のレースだけ学習。検証ラベルを学習/調整/早期停止へ渡さない。
保留/競合/不正/重複は既存判定、候補外の負例も保持。各レースweight合計1。
モデル保存→別プロセス再読込→推論、基準と同一snapshot/候補/点数で7/9車×3/4/5点の比較を実装。
対象0件は率null。学習不足/正負不足/検証なしは学習前に停止。学習済みレースとcutoff前の推論も拒否する。
評価は第二段階の後向き時系列分離。第一段階学習入力の独立性/実用性/実精度/商品受入は未確認。

新規Python9項目を実行。初回8成功/1失敗は試験が7/9車の入力順と出力順をzipしていたことが原因。
レースID照合へ修正し当該試験と過去入力拒否の強化試験が成功。追加レビューでnormal省略/明示の同値履歴hashを正規化し、順序試験を追加。
変更headの新規9試験/全CI確定結果は#267本文へ保存する。既存成功試験の手動反復なし。画面変更なし、新規Chrome追加なし。
契約とCLI：docs/KEIRIN_FINAL_FIVE_RANKER_20261021.md。生成モデル本体はGitHubへcommitしない。
残件：商品受入基準/実用特徴/第一段階を含む独立評価、実験選択の記録、画面/モデル管理接続、DREAM、会員/課金/実データ受入。
KEIRIN.JP HOLD・実取得/実学習/予想DB書込/本番予想OFF、API20/12/11/7記録値を維持。
#266/#267マージ/公開/Function配備未承認。現行原本保存/段階backend受入/復元は#266本文を厳守。

## FINAL 5 frozen-result diagnostic — 2026-10-21

再開main d069ab9b6adcf9585954a5bae7be7df0546e473c、#267 2d40e4424fa1efdce74db8287f9e4341e9aa1e24。
全7系統success、回帰39538234404は47/47、runtime39538234369/job119019757956 verified=true。
ML39538234468/job119019757914はPython73/新規Chrome4成功。#266 ae2658f、#250/#257も前記headと一致。

次の許可済み合成開発として、固定FINAL 5基準の結果診断を#267同ブランチへ追加。
既存の履歴選択を共用し、保留/競合/不正記録を除外、通常結果が一致する最新予測を1件採用する。
元最大15候補内の正解が最大5点へ残った/絞込みで落ちた/元候補外だった、の3区分を集計。
7/9車×3/4/5点を分け、0件の率はnull。結果/払戻oddsを選定に使わず、元予測/履歴/判断は不変。
後から固定ルールを適用する診断であり、前向き実績や別モデルとの同点数比較ではない。
第二段階AI/実データ精度/収益/商品受入の完成とは扱わない。保留訂正の通常履歴への反映も未接続。

読取専用API/画面/取得時点の集計JSONを追加。保存停止中は最後の確認済みメモリと明示する。
再確認で旧結果消去、遅い応答破棄、エラー消去/回復。既存の保存/復元規則を変更しない。
ローカル新規Python7＋共用化が影響する既存model_history8＝15成功、JS構文/diff check成功。
新Chrome2ケース（390/1280幅・各7/9車混在）をML CIへ追加。新head全CIは#267本文で確定。
成功済み旧headの手動再実行なし。CI確定記録だけのcommitは作らない。
契約docs/KEIRIN_FINAL_FIVE_REVIEW_20261021.md。次の残件は同文書と#267本文を参照。
API20/12/11/7記録値、KEIRIN.JP HOLD・実取得/実学習/予想DB書込/本番予想OFF。
マージ/公開/配備未承認。#266の現行原本保存・段階backend受入・復元条件を維持する。

## FINAL 5 probability-only comparison baseline — 2026-10-21

再開main d069ab9b6adcf9585954a5bae7be7df0546e473c、Draft #267 36351fb0546cbe1115b86ef10474a6057bb2b582。
#267の全7系統success、回帰39457346234の47/47、ML39457346364のPython67/Chrome4を再利用。
#266 ae2658f7acadb597bf67217c165afe722a651587、#250/#257は変更なし。未完CIなしから着手。

FINAL 5の選定範囲について過去会話検索で2026-10-03 07:39:50Zの本人案を確認。
5カテゴリ各最大3点の中からおすすめ5点を選ぶ方針。各カテゴリ1点の枠にはしない。
第二段階AIの評価軸/重み/受入条件は確定しておらず、今回はその比較対象となる確率順の基準を追加する。
未校正確率降順、同値は車番tuple昇順。既存最大15候補だけから最大5点、候補不足は補完なし。
元の確率/オッズ/カテゴリ/順位を保持し、全210/504表から新たな買い目を追加しない。
これは第二段階AIや実用推薦の完成ではない。オッズ価値/展開/確信度/分散効果を評価したとは表示しない。

#267同ブランチで読取専用API/ローカル画面と現在予測からのリンクを追加。
元予測の全検証を維持。不正なら409、対象なし/任意queryは404、同一origin違反403。
画面は5点未満/選定元/未確認oddsを明示。再確認時に旧候補消去、遅い応答破棄、不正応答/503も消去。
ローカル新規Python6、JS構文/diff check成功。新Chrome4（390/1280×7/9車）をML CIへ追加。
新headの全CI/Chromeは#267本文で確定。既存成功headを手動再実行せず、結果記録だけのcommitも作らない。
詳細docs/KEIRIN_FINAL_FIVE_BASELINE_20261021.md。料金/会員権、第二段階AI/DREAM、実データ評価/本番受入は残る。
API20/12/11/7記録値。KEIRIN.JP HOLD・実取得/実学習/予想DB書込/本番予想OFF。
マージ/公開/配備未承認。#266の現行原本保存・段階backend受入・復元条件を維持し、#265承認/旧ZIPは流用しない。

## Synthetic category disclosure candidate — 2026-10-21

再開main d069ab9b6adcf9585954a5bae7be7df0546e473c、Draft #266 ae2658f7acadb597bf67217c165afe722a651587。
#266は全7系統success、回帰39438773118は47/47、runtime39438773171/job118682760535 verified=true。
ML39438773194/job118682753442のPython61/原本取得Chrome2/既存画面成功を再利用。他open PR #250/#257は変更なし。

完成条件に残る商品表示を進める。過去会話検索で5カテゴリ＋FINAL 5＋DREAM TICKETの採用方針を確認。
個別プランの割当/価格/期間/失効は原文で明示採用を確認できず、推測で実装しない。
指定カテゴリだけを返す読取専用処理と合成確認画面を別ブランチcodex/synthetic-product-disclosureへ追加。
この候補は#266検証済みheadに依存し、mainへのPR差分には未マージの#266も含む。どちらも公開/マージ未承認。
新規差分はae2658fから比較する。#266のコード/head/成功CIは変更しない。

指定なし/対象外/開始前/期限切れは候補0。未知カテゴリ/認証主張/不正指定は拒否。表示対象だけ既存snapshot検証を通す。
ブラウザへ全候補を送らず、指定カテゴリだけ返す。画面切替で旧候補を消し、遅い旧応答を破棄、失敗時も消去する。
誰でも全ケースを選べる合成画面であり、本人認証/実会員権/課金の実装ではない。FINAL 5/DREAM TICKET出力なし。
既存owner/認証設定・Function・配備・予測/履歴/確認一式は変更しない。予測の再生成/再学習なし。

ローカル新規Python6、JS構文/diff check成功。Chrome4ケース（390/1280×7/9車）をML CIへ追加。
新headの全CI/実Chromeは候補PRで確定する。結果だけでcommit/CI再起動なし。
詳細docs/KEIRIN_CATEGORY_DISCLOSURE_20261021.md。商品開示/利用権供給/実会員接続・FINAL5/DREAM・課金/実データ評価は残る。
API20/12/11/7記録値、KEIRIN.JP HOLD・実取得/実学習/予想DB書込/本番予想OFF。
#266の将来の現行原本保存・段階backend受入・復元条件を維持。#265承認/旧ZIPを流用しない。

## Read-only migration-original inspection and download — 2026-10-20

前head a7ccad6adfc4c5f29fa7b6c5e7916a27a04b26b1は全7系統success、回帰39420958802は47/47。
runtime39420959298/job118621474201 verified=true、ML39420958797/job118621471632はPython54と実Chrome成功。
main d069ab9b6adcf9585954a5bae7be7df0546e473c、他open PR #250/#257は変更なし。成功済み試験を手動反復しない。

自動保存した移行前原本を画面から照合し、原本バイト列のまま取得する入口を追加。
件数/サイズ/hashと、欠落/不正/別原本/現行外部変更/一時モードを区別。固定名だけを読取専用で検証する。
v1は完全バイト一致、v2はlegacy/旧snapshot/原本に含まれる履歴との整合を確認。
取得時も再照合し、画面確認時のraw SHA-256と違えば409で取得停止。原本・現行記録・確認一式の書込なし。
署名/来歴証明ではなく、有効な古い保存物の差戻しや同内容の再整形検出は別保証。端末保存完了は未確認。
旧版再開は現行v2と確認一式を保全して別保存先で行う。自動復元/削除/修復・過去原本の推測生成なし。

新規Python7試験がローカル成功。原本完全取得/保存不変、追加履歴、破損/リンク/FIFO/上限/別原本、
外部変更/古い取得リンク409/同一origin/固定path/一時モードを確認。JS構文/diff check成功。
新Chrome2ケース（390/1280）を既存ML CIへ追加。新head全CIと実Chrome結果はPR本文で確定する。
契約docs/KEIRIN_HELD_HISTORY_REVIEW_20261019.md「移行前原本の確認と取得」。結果記録のみでcommit/CI再起動しない。
通常開発は工程ごとの確認待ちを挟まず進める。公開/マージ/Function配備未承認、API20/12/11/7記録値を維持。
KEIRIN.JP HOLD・実取得/実学習/予想DB書込/本番予想OFF。将来の現行原本保存・段階backend受入・復元条件を維持。

## Preserve original v1 bytes before session migration — 2026-10-20

前head d9eff3e33435af2b65a465c3c063d72506b33dc4は全7系統success、回帰39417795189は47/47、runtime39417795250 verified=true。
ML39417795204/job118610955051でworkbench Python47試験と実Chrome操作/保存復旧成功。main/他open PR #250/#257は変更なし。

v1からv2への移行前原本が手動バックアップに依存していたため、保存先指定時の移行直前に原本を自動保存する。
synthetic-session-v1-before-migration.jsonへ元ファイルのバイト列をそのまま保存し、fsync/排他公開/dir fsync/一致確認後に移行。
既存原本は上書きしない。同一原本は再同期して利用し、異なる原本/リンク/非通常ファイル/上限/保存失敗は503と書込停止。
旧ファイル/メモリは保持。v2保存に失敗しても移行前原本を保持する。新規v2/旧記録操作/一時モードでは新設しない。
既にv2移行済みで原本がない場合は推測生成しない。旧版復帰は別保存先で原本を使用し、現行v2/別確認一式を巻き戻さない。
link→一時名unlink間の強制終了は2リンクが残るため、旧v1復元後も次の移行を拒否。原本を保全し明示修復するまで再開しない。

新規7＋影響する既存14＝21試験がローカル成功。完全バイト一致/別保存先復元/既存非上書き/同名競合、I/O障害、
実SIGKILL3境界、HTTP503/メモリ保持、リンク/FIFO/上限を検証。JS構文/diff check成功。新head CIは既存設定の自動実行で判定する。
契約docs/KEIRIN_HELD_HISTORY_REVIEW_20261019.md「保存形式の移行前原本を自動保存」。確定head/CIはPR本文が最新。
PR本文は上限に近いため最新節を更新し、以前の確定CIと重要契約を保持する。結果記録だけでcommit/CIを再起動しない。
通常開発は工程ごとの確認待ちを挟まず検証・保存まで進める。公開/マージ/配備は引き続き未承認。
API20/12/11/7・KEIRIN.JP HOLD・実取得/実学習/予想DB書込/本番予想OFF、将来の原本保存/段階backend受入/復元条件を維持。

## Synthetic session expiration and v1 compatibility — 2026-10-20

前head d192cbd7bd8af48022ca5fd2bd8e880b32760381は全7系統success、回帰39413810530は47/47、runtime39413810736 verified=true。
main d069ab9b6adcf9585954a5bae7be7df0546e473c、他open PR #250/#257は変更なし。旧取消し/VM失敗を再実行しない。

期限更新後のseries*10+車数で17R/19Rになる制約を修正。新規v2セッションは7R/9Rを維持し、期限切れ後は
現在+1時間と既存最遅予定+1日の遅い方へ進め、JST日付/レース識別の重複を防ぐ。同じ開催内の再予測は同じ識別。
v1は従来規則で読み込み、読込/選択/旧結果記録では形式維持。新予測時だけ一回のcheckpointでv2へ移行。
旧series/予定/予測hashを保持し再照合。原予測・時刻・履歴を変更しない。旧17R/19R保留は移行後も全体拒否。
v2を旧プログラムで読むことはできない。旧版へ戻る必要があれば新予測前のv1バックアップが必要。
保存失敗前後のメモリ保持/503/再起動再検証、20件/32MiB上限、別確認一式と判断の保存契約は維持。

ローカル新規6+影響する既存14=20試験成功（実合成モデル期限更新1含む）。反復期限更新/JST年越し/7・9車、
保留追加/保存復元/v1互換/旧番号拒否/移行時fsync失敗/不正入力を検証。CIは既存設定による新候補の自動実行で判定。
契約docs/KEIRIN_HELD_HISTORY_REVIEW_20261019.md「期限更新後の合成レース識別」。確定head/CI結果はPR本文を優先する。
次は新headのMLと全依存CIを確認し、失敗時は当該ログで診断する。成功済み試験の手動反復はしない。
公開/マージ/配備未承認、API20/12/11/7・KEIRIN.JP HOLD・実取得/実学習/予想DB書込/本番予想OFF。
将来の現行原本保存・段階backend受入・失敗時復元条件を維持。合成結果を実データ/本番受入へ拡張しない。

## Packet VM Python startup compatibility — 2026-10-20

根拠貼付け候補a3dabd0のML39413293532/job118596105067はsuccess。390/1280×7/9車の拡張Chrome4ケース成功。
回帰39413293240/job118596105543はkernel7.0の512M packet VMでPython encodings不在→PID1終了。
前候補45abeb0の同試験はkernel6.17で成功。UI変更との直接関連なし、正確な欠落原因は未確定。
packet VMを固定1024Mにし、payloadサイズとcodec存在/hashを記録する。initramfs展開失敗の即時拒否も追加。
ローカルVM10/packet15試験成功。全期限・画像上限・隔離・認証/expiry/S3検査は維持。実VMは新候補CIで判定。
詳細docs/CI_VM_INITRAMFS_20261020.md。最新head/CI確定結果はPR本文を正とする。旧失敗の無条件再試行なし。
公開/マージ/配備未承認、API20/12/11/7・HOLD/OFF・将来の現行原本保存/段階受入/復元条件を維持。

## Synthetic review evidence text input — 2026-10-20

前head45abeb0352f3efbd1dafa5d4f037549806c9d8f1は全7系統CI成功、回帰39410059644は47/47、runtime39410059690 verified=true。
main/他open PR #250/#257は変更なし。旧取消しとVM起動失敗は前候補の確定記録を再利用し、再試行しない。

合成確認の根拠JSONを画面へ貼り付け、明示読込できる候補を追加。ファイル受渡しをさらに減らす。
UTF-8 3 KiB上限/JSON構文を画面で確認し、元文字列を既存判断APIへ送る。完全な根拠照合はサーバーで維持。
編集/対象変更時に前の根拠を解除し、再読込前の判断を停止。ファイル選択と貼付けは同時に有効にしない。
根拠/判断の自動生成なし。未送信入力は保存せず、成功判断だけ既存保存・復元経路を使う。
ローカルJS構文/diff check成功。既存Chrome4ケースを貼付け・拒否・保存復旧まで拡張。新head CI結果はPR本文を正とする。
契約はdocs/KEIRIN_HELD_HISTORY_REVIEW_20261019.md「根拠JSONの貼り付け」。
公開/マージ/Function配備未承認、API20/12/11/7・HOLD/OFFを維持。将来は別途承認・現行原本保存・段階受入・復元が必要。

## Synthetic VM startup compatibility diagnosis — 2026-10-20

合成保留直接追加候補81b7164のML39408953490は成功。新規Python6/Chrome4、workbench計41試験成功。
一方、回帰39408953553の既存VMでkernel7.0上のinitramfs書込失敗→systemd実行不可を確認。
kernel6.17の同種成功ログと照合。前候補のtimeoutやQMP問題とは別。詳細はdocs/CI_VM_INITRAMFS_20261020.md。
容量不足を仮説として、systemd合成VMだけ512M→1024M、archive/ゲスト容量診断を追加。
安全条件、期限、画像上限、packet-only VM、本番/ホスト設定は変更なし。
ローカル既存19試験＋C static/Werrorコンパイル/host実行拒否を確認。実VMは新head CIで検証する。
新head/最終結果はPR本文を正とする。kernel7環境での改善と全CI成功が確認できるまでは未解決。
公開/配備未承認、API20/12/11/7、KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF。

## Synthetic session to held-review direct transfer — 2026-10-20

基準main d069ab9b6adcf9585954a5bae7be7df0546e473c、前head bd654a9e79a0e5ce1345c9ae081339e5f1353f58。
引き継いだ未成功CIは解消。取消し7件のannotationsは全てjob timeout、全stepと試験ログは成功済みだった。
取消し回帰6件/API1件だけ再実行して成功後、依存未成功で停止したruntime1件を再実行して成功。
回帰39279107744 attempt2は47/47、history39279107755/runtime39279107742 attempt2 success。
成功済み41件は初回の実行時刻を保持して再利用。検査/timeout変更なし。終了処理遅延の根本原因は未確定。
main/他open PR #250/#257に差分なし。非公開Work/未push作業は未確認。

同じ合成予測セッションのML保留を、確認画面からファイル操作なしで明示追加する候補を実装。
元保留一覧と確認一式の両revisionを同一lock内で照合。不一致409、全体検証、追加のみ、保存失敗503。
通常履歴は追加せず、予測/モデル不変、根拠/判断の自動生成なし。新規保留の自動同期はしない。
既存読込/保存を再利用。旧17R/19R等は全体拒否し番号を補正しない。合成入力限定。
ローカル新規6＋影響する既存7試験成功。新Chrome4ケースをCI追加、構文/diff check成功。
新head CIはPR本文の最新記録を正とする。前headの成功を新候補の証拠へ代用しない。
詳細：docs/KEIRIN_HELD_HISTORY_REVIEW_20261019.md「同じ合成セッションから直接追加」。
次は本候補のCI/Chrome結果確認。実owner/実データ審査・公開Web/Edgeの訂正・通常収集への解除は未接続。
公開/配備未承認、API20/12/11/7、KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF。
将来の配備は別途承認、現行原本保存・段階backend受入・復元が必要。#265承認/旧版ZIPは流用しない。

## Synthetic held-review automatic save/recovery — 2026-10-20

main d069ab9b6adcf9585954a5bae7be7df0546e473c、Draft #266前head03b1ad279738f9310c506467600e93d51479b392から継続。
前候補は7系統success、回帰39226822818=47/47、runtime39226822743 success。ML39226822632も新規7試験/Chrome12ケース成功。
最新remote・他open PR #250=0659657 / #257=99aeacaに変化なし。成功済みCIの手動再実行なし。

--state-dir指定時に、保留確認一式をheld-review/held-review.jsonへ自動保存する候補を追加。
既存予測セッションとは独立。検証済みSessionStoreの固定ファイル/協調ロック/atomic replace/fsyncを共有。
保存完了後にメモリへ反映して成功応答。失敗や外部書換えは503とwrite_blockedで停止し、再起動時に検証する。
破損時に空で上書きせず、孤立partialを昇格しない。予測/モデル不変、実学習・通常履歴化なし。
画面で一時保存/自動保存/復元/保存失敗を表示。未送信フォームは保存対象外。
復元試験で監査配列順序の差を検出し、保存一式とレポートの順序を揃えて修正。

ローカル：新規保存/復旧9＋既存確認API7＋共有保存処理7の計23試験成功。既存の実モデル学習試験はCIへ委ねる。
実SIGKILL・置換前後・同期失敗・途中/完了復元・二重起動・破損/外部変更・503を検証。
新Chrome4ケース（390/1280×7/9車）を既存ML CIへ追加。新head/CIはPR本文の最新記録が正。
契約：docs/KEIRIN_HELD_HISTORY_REVIEW_20261019.md。電源断・任意ホスト耐久性・署名/グローバル台帳の保証はない。
次は新候補CI確認。その後の許可済み合成開発は、予測から保留確認までのファイル受渡し削減を検討。

公開/配備未承認、API20/12/11/7、KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF。
実owner/実データ審査・権限・公開Web/Edge・通常収集への解除反映は未接続。非公開Work/未push作業は未確認。
将来の配備には別途承認、現行原本保存・段階backend受入・復元が必要。#265承認/旧版ZIPは流用しない。

## Synthetic held-review UI and bundle — 2026-10-19

修正head19df940のML39225660699/job117971190799はsuccess。新規Chrome12ケースとPython/API7試験成功。
最終レビューで409競合応答の状態読取にも既存lockを適用し、同時更新中の不整合表示を防ぐ。
この最終差分の候補head/CIはPR本文を正とする。前候補の成功を新headの証拠に代用しない。

初回head956559aのML39224926950/job117968775119は新Chrome保留選択で停止。
Python JSONをJavaScriptで再構成するとPhase32のfloat表記が変わりdigestが不一致になることを再現。
製品UI/APIと試験fixtureで元JSON文字列を保持するよう修正。digest検査は緩和せず、転送試験を1件追加。
修正後headのCIはPR本文で確認。既存成功CIの手動再実行や未完CIの取消しはしない。

main d069ab9b6adcf9585954a5bae7be7df0546e473c、Draft #266前head f3eb9877c3d6798e69016a89debd027086a4b543から継続。
前候補の7系統CI成功、回帰39205905562は47/47。新規11試験もML39205905481で成功済み。
以前のCI待ちは解消。成功済み試験の手動再実行なし。新コードに対するCI結果はPR本文の最新記録が正。

ローカル合成workbenchへ /held-review を追加。両エンジンの保留を読み、根拠JSONと判断を入力する。
確認一式をダウンロード/再読込でき、CLIレポートも再計算して再利用する。元履歴は変更しない。
読込は追加のみ。部分一式で未確認保留/競合判断を消さず、改変・孤立確認・上限超過は全体拒否。
revision不一致では別タブの古い操作を409で停止。合成予測画面の保存とは別のメモリ保持であることを明示。
Python/API新規7試験を実施。390/1280幅のChrome保存/復元/入力試験を既存ML CIへ追加。
ローカルにChromeなし。新候補の画面成功・全CIはPR本文の最終結果で確認する。
契約・上限・1〜12R制約・保存の限界：docs/KEIRIN_HELD_HISTORY_REVIEW_20261019.md。

次は新head CI結果確認。その後、許可済み合成範囲で確認記録の自動保存/中断復旧と操作負担削減を検討。
公開Web/Edgeの訂正、実owner/実データ審査・権限・永続台帳、通常収集への解除反映は未接続。
他open PR #250=0659657 / #257=99aeacaは変更なし。非公開Work/未push作業は未確認。
公開/配備未承認、API20/12/11/7、KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF維持。
将来の配備は別途承認、現行原本保存・段階backend受入・復元が必要。#265承認/旧版ZIPは流用しない。

## Synthetic held-event review — 2026-10-19

main d069ab9b6adcf9585954a5bae7be7df0546e473c、Draft #266の前head78488e85c14b3431de3e5c5df623ba6b87b20321から継続。
前候補は7系統CI成功。回帰39197013687は47/47、runtime39197013668、PostgreSQL39197013600もsuccess。
ML39197013605/API39197013613/collection39197013761/AWS39197013752成功。integrated39197013675はskipped。
前記録の未完CIは解消済み。合格済み試験の手動再実行なし。過去QMP失敗の根本原因は未確定。

ml.held_history_reviewを追加。保留確認と誤申告訂正の根拠/判断/元履歴を別記録として保存する。
入力内の同じレース・両エンジンの保留をすべて確認し、訂正結果も一致した場合だけ合成レビュー内で再評価。
確認漏れ、新規保留、訂正競合、予定発走/車番構成/最新snapshot競合は対象レースを未解決にする。
非標準確認は評価対象外のまま確定。元予測/モデル不変、通常履歴/学習データexportなし。
新規11試験成功。既存ML workflowへ新試験追加。契約：docs/KEIRIN_HELD_HISTORY_REVIEW_20261019.md。
新head/CI結果はPR本文の最新記録が正。次は新候補CIと、合成レビューの操作画面・保存/再読込連携。
Web/Edge・実owner・通常収集経路への解除反映と、実データ審査/権限/永続記録は未接続。
GitHub他open PR #250=0659657 / #257=99aeacaは変更なし。非公開Work/未push作業は未確認。
公開/配備未承認、API20/12/11/7、KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF維持。
将来の配備は別途承認、現行原本保存・段階backend受入・失敗時復元が必要。#265承認/旧版ZIPを流用しない。

## Phase32 / ML held-event transfer — 2026-10-19 12:54 JST

main `d069ab9b6adcf9585954a5bae7be7df0546e473c`、Draft #266の前head `6777d6ad1e092ec9a69167cd92e04d5910081723`から継続。
前headは7系統CI成功、回帰39184944241は47/47。runtime39184944242は初回の依存待ち期限切れ後、
同一headの依存成功を確認して失敗1ジョブだけ再実行しattempt2成功。詳細はPR本文12:44 JST記録。
以前の「新head CI待ち」「Chrome未確認」はこの成功確認より古い。過去QMP失敗の根本原因は未確定。

今回、ml.held_history_transferに合成入力専用の双方向保留イベント連携を追加。
別々の保存済みPhase32/ML snapshotを検査し、日付/会場/番号・予定発走・車番構成一致を要求する。
元予測/モデル/時刻を保持し、source/target両履歴とdigestを連携記録へ保存。予測の変換・モデル捏造なし。
CLIは連携記録の作成と検証後のtarget出力。既存ファイル上書き・通常結果化・保留解除はなし。
新規8試験成功。7/9車×3状態×双方向、評価除外、別レース指標不変、改変/時刻/識別不一致、CLIを検証。
変更対象の試験だけ実行し、既存ML CIへ新試験を追加。新head/CI結果はPR本文の最新記録を正とする。
契約と限界：docs/KEIRIN_HELD_HISTORY_TRANSFER_20261019.md。本人の選手IDや情報源真正性は検証していない。
次は新head CI確認、保留解除の監査・競合・訂正契約。Web/EdgeのML連携と実owner backend受入は残件。

他open PR #250=0659657 / #257=99aeacaは変更なし。非公開Work/未push作業は未確認。
公開・Function配備は未承認。API predict20/history12/backtest11/history-pipeline7は変更なし。
KEIRIN.JP HOLD、実取得・実学習・予想DB書込・本番予想OFF。
将来の公開/配備は別途承認、現行20/12/11/7原本保存・段階受入・失敗時復元が必要。#265承認/旧版ZIPは流用しない。

## Phase32 owner held API UI — 2026-10-19

Chrome診断：修正head aa146adのML39184712111/job117844583964は生成器・package検証を通過。
新Chrome試験が対応更新待ちで停止。模擬predict-status応答に必須service名がなく、
checkStatusがinvalid_statusで後続GET前に終了する契約不一致を確認した。
試験の模擬応答へservice=predict-statusを追加。製品処理・待機上限・安全条件は変更しない。

追加診断：head875b677のML CI39184498691/job117843944540は、レビュー生成器の
owner_web_integration_anchor_changedで停止（Chrome未開始）。clearSession先頭の
ownerModelPreview.reset()を元の位置へ戻し、保留状態の無効化をその直後に維持した。
生成器/owner controller/失敗時receiptの3試験はローカル成功。完全package試験は
ローカルのLightGBM不在で未完了のため、新head CIで確認する。検査の緩和・同一head再実行なし。

基準main `d069ab9b6adcf9585954a5bae7be7df0546e473c`は変更なし。Draft #266を継続。
前head `482857c2ffde32506deb345a0798dad460fb9964`は7系統CI成功、回帰39181274460も47/47成功。
ML39181274341 / API39181274307 / collection39181274296 / AWS39181274448 /
PostgreSQL39181274574 / runtime39181274508成功。integrated39181274348はskippedで成功数に含めない。
過去のQMP初回RESUME失敗は今回再発しなかったが、原因確定・恒久修正とは扱わない。

今回、owner画面へ同着・欠車・中止の保留生成、保存、混在バックテストを接続した未公開候補。
GETのowner・安全状態・正確な保留schema対応を確認できるAPIだけ保留操作を有効にする。
未対応API・不正保留・改変応答は停止。生成応答を送信snapshot/settlementと照合し、
集計応答の入力数・保留ID・除外数をローカルの保留規則と照合する。
全件保留は「評価対象なし」で通常指標を表示しない。入力変更・ログアウト後の古い応答を無効化。
実Web script＋実handlerの7/9車合成試験、通常capture試験、web/safety回帰は成功。
390/1280幅のChrome owner保存/再読込/除外試験を追加。新headのCI結果はPR本文を正とする。
この記録時点で新Chrome試験の成功・配備済みbackendの実owner受入とは扱わない。

他open PR #250/#257は記録済みheadと一致。非公開Work/未push作業は未確認。
公開・Function配備は未承認。API predict20/history12/backtest11/history-pipeline7は未変更。
KEIRIN.JP HOLD、実取得・実学習・予想DB書込・本番予想OFF。
MLモデル履歴の相互変換・保留解除・配備済みbackend受入は未完。詳細はdocs/KEIRIN_HELD_HISTORY_20261019.md。
将来の配備には別途承認、現行20/12/11/7原本保存、段階受入・失敗時復元が必要。
#265承認や旧版19/11/10/6の保存ZIPを今回へ流用しない。

## Phase32 held API — 2026-10-19

#266 head `daa9f9efb3eb59e2ced8338aeb4eaa4af9f79981`から継続。main `d069ab9b6adcf9585954a5bae7be7df0546e473c`は変更なし。
前headの5 CI成功。回帰39177306812は46/47成功、QMP初回RESUME受信で1件失敗。
runtime39177306779は20分の回帰待ちで停止。詳細は`docs/CI_QMP_FIRST_FRAME_20261019.md`。
共通VM検査の厳格拒否を維持し、同一head再実行なし。根本原因・恒久修正は未確定。
今回、history-pipelineの保留JSON生成、backtestの保留・同一race_id除外を未公開候補へ接続。
全件保留時は通常指標null、学習/保存/本番OFF。不正な保留は要求全体422。通常結果注記ガードは維持。
Python/browser/Edgeで同一JSONを確認し、エンジン識別子矛盾の拒否も統一。
Python6試験、7/9車の実handler結合、既存Web結合、web/safety回帰が成功。新head CIはPR本文が正。
詳細・限界は`docs/KEIRIN_HELD_HISTORY_20261019.md`。owner画面の保留API操作はまだ無効。
MLモデル履歴変換・保留解除・配備済み実owner受入は未実施。
公開/配備は未承認。API predict20/history12/backtest11/history-pipeline7、HOLD/OFFを維持。

## Phase32 direct history guard — 2026-10-19

#266 head `e5f561201fb3189ec1c4bd5c6d0257cebea6455d`から継続。mainは`d069ab9b6adcf9585954a5bae7be7df0546e473c`。
前headのChrome保存・再読込・統合は成功。5 CI成功、runtime39176166395は回帰待ち、回帰39176166392はqueued（08:35 JST照合）。再実行なし。
今回、非標準結果を注記した履歴が直接backtest APIで通常集計される問題を合成試験で再現し修正。
root/metadataの非標準・未知status、結果補助項目、既知の2種類の保留schemaを拒否。混在要求は全体422、部分指標なし。
状態省略の旧形式と明示normalは互換維持し、全指標一致を確認。保留schemaに通常ラベルを付けた入力はPython/browserも除外。
7/9車の直接API＋pipeline、実Web script＋実handler、Python5試験（JS照合含む）が成功。新head CIはPR本文を正とする。
契約と残件は`docs/KEIRIN_HELD_HISTORY_20261019.md`。次は新head CIとEdge保留生成/集計の接続。
今回は拒否ガードまでで、Edge保留生成・集計・MLモデル履歴変換・解除処理は未実装。
公開/配備は未承認。API predict20/history12/backtest11/history-pipeline7は未変更。
KEIRIN.JP HOLD、実取得・実学習・DB書込・本番予想OFF。#265の承認を拡張しない。

## Phase32 offline held history — 2026-10-19

main `d069ab9b6adcf9585954a5bae7be7df0546e473c`と#266旧head `7a4fa23bdb2e32d79a40b899d917160c553ee8c2`を照合。
#266旧headは7 workflows成功、回帰39128022537は47/47成功。再実行なし。
#266へ保留JSON、オフラインUI保存・再読込、Python/ブラウザ評価除外を追加する未公開候補。
詳細・検証・限界は `docs/KEIRIN_HELD_HISTORY_20261019.md`。新headのCIはPR本文を正とする。
公開・Function配備は未承認。API predict20/history12/backtest11/history-pipeline7は未変更。
KEIRIN.JP HOLD、実取得・実学習・DB書込・本番予想OFF。次は新headの未完CIのみ確認。
Edge保留応答・MLモデル履歴の相互変換・解除処理は未実装。全経路完成と扱わない。

## Phase32 result declaration guard — 2026-10-18

基準main `d069ab9b6adcf9585954a5bae7be7df0546e473c`（#265公開済み）。
#265の公開後回帰39125663260は47/47成功、Pages39125662974も成功。
APIはpredict20/history12/backtest11/history-pipeline7。公開済み試験は再実行しない。
今回の未公開候補はPhase32の結果申告を通常履歴へ黙って落とさないガード。
詳細・限界・次工程は `docs/KEIRIN_RESULT_DECLARATIONS_20261018.md`。
新候補のマージ・配備は未承認。KEIRIN.JP HOLD、実取得・実学習・DB書込・本番予想OFF。
ML保留記録との相互変換・集計・UI接続は未完で、このガードを全経路接続完了とは扱わない。

## Data duplicate-type correction / prepared Claude pilot — 2026-10-14

Baseline main `703e2ed24a8d0c0df307b90776f2272478b96013` is unchanged since the
owner-approved PR #253 merge. Its six CI workflows passed (47/47 regression jobs,
21/21 bridge synthetic tests); existing automatic Pages update also passed.
Older candidate/Draft/PENDING notes below are historical and superseded.

P0 data: reproduced an order-dependent intake defect using synthetic records.
Python equality treated boolean/numeric or integer/float changes in duplicate
content as identical; a valid first record's review could then retain that race
in a historical partition. Candidate correction compares finite JSON content,
preserving scalar types and nested structure. Conflicts quarantine the whole race
in either order across train/validation/test; unrelated reviewed races remain.
Reordered object keys and genuine duplicates retain their existing behavior.
Local verification: 161 historical tests, 26 shared-agent preparation tests and
existing web/safety regression pass. Five targeted tests were added; two new audit
tests failed on the old implementation before the correction. Remote candidate
CI results and exact commit will be recorded in its PR; no merge authorized yet.

No new matching source-permission mail was found in the bounded 2026-10-14
query. This does not prove absence in every channel. KEIRIN.JP HOLD persists.
Recovery branch remains `62f197d`; GitHub cannot resolve reported local `9fbb95d`.
Recover the original Claude session/patch; do not reimplement it from a summary.

Jarvis parallel: owner-created Issue #255 prepares one synthetic payout-test-only
pilot. No trigger, credential registration, permission/flag change or model run
occurred. #254 retains the remaining separate approvals and runtime acceptance.
PR #250 remains open. No source outreach/acquisition, real training, prediction DB
write, production AI/Jarvis run, new billing or reporting schedule was enabled.

## PR #253 bridge review revision — 2026-10-14 (historical pre-merge review)

Resumption matched main `62f197db216a1f4b58226cbd644ae9f11c676686`, PR #253
head `61e9a7d76d0edffeecfd280266bedfa056314ee8`, open PR #250 and Issues
#249/#254 to the handoff. No intervening commits/comments or overlapping PRs.
Three CI runs on the old #253 head succeeded: 38402783406, 38402783448,
38402783673. These do not prove bridge runtime success. PR #250 touches only
AGENTS.md; this candidate leaves it unchanged. Neither PR is merged here.

Official Action review found the custom-prompt agent mode did not provision the
requested branch, while Bash was forbidden; its post-push scope check was too
late. The pinned Action also mishandles empty CLI values/settings-source flags.
The revision separates tool-denied/read-token proposal generation from a fresh
trusted publisher with no Claude credential. Exact owner-trigger issue content,
base SHA, file scope/blobs, overlapping PRs and existing task branches are checked
before publishing. Only existing regular Python files (1–4, 24 KB/file, 60 KB total)
can be proposed; generated code is never run by the credentialed publisher.
New synthetic contract tests cover refusals, drift, partial failures and draft
creation; a dedicated no-model CI workflow is added. Local 21/21 and basic web/
safety regression pass. Final new-head CI is PENDING until observed on GitHub.
See docs/CLAUDE_TASK_BRIDGE.md for official source pins and activation gates.

P0 data: no new acquisition/storage/training/commercial permission is established.
The recovery branch claude/keirin-ai-web-survey-i4e236 still equals main 62f197d;
reported local 9fbb95d is not available here. Do not duplicate its 7/9-rider work.
Recover that original Claude session, then verify the actual diff/tests. Preserve
all existing source evidence and inquiry threads; no provider outreach was sent.

Jarvis parallel work in this candidate is the bounded development handoff only;
existing agent-runtime, cloud/custody and other applications are unchanged.
Next: verify the revised exact head and all applicable CI, then request approval
for disabled-only #253 merge. Separately authorize OAuth registration, any GitHub
permission change, enable flag and one synthetic pilot. Current GitHub docs say
GITHUB_TOKEN-created PR CI requires manual approval; review the code first.
Bridge execution/authentication/automatic PR creation remain NOT RUN.
KEIRIN.JP HOLD; production prediction, DB writes, source acquisition, real training,
hosted execution, schedules, reporting, credentials, new charges and deployment
remain OFF/unapproved. Existing historical evidence below is retained unchanged.

## PR #251 verified baseline / historical source-variant quarantine candidate — 2026-10-13

Resumption rechecked GitHub main 806496bea8617414d37bb39bda308619782533d7,
tree b67916b45b453870b6f5b09e34563f76d4f9c432, PR #251's Final independent
main receipt and current workflow statuses. All five independent push workflows
succeeded: regression 38379293047 (47/47), runtime 38379293609, PostgreSQL
38379293542, UI 38379293172 and AWS 38379293050; Pages 38379293329 also succeeded.
PR #251's revised head 92f0a71bce2db6b052948fb1dc803861599ddd56 passed all five
PR workflows; regression 38377640220 passed 47/47. The final receipt supersedes
its candidate PENDING text below. Main live-save job 115235405534 verified two
fresh boots, unchanged original deadlines and complete live observations of
1.991607595 s / 1.867473865 s, followed by expiry, restoration, normal save/reboot
and generation-2 poweroff. Main runtime job 115235407178 verified exact push SHA.
The initial three-entrypoint VM failure remains a failure; live restart/halt have
local negative-entrypoint tests, not successful dedicated live VM qualification.
The historical PR #246 QMP greeting cause remains unknown; diagnose recurrence.

Issue #249 prioritizes data permission/coverage while agent work continues.
Concurrent docs-only PR #250 remains open at head
0659657f3778c98e63735cf526b88e8df02de2f0; AGENTS.md is not changed here.
No source-use permission is newly established. Provider terms, costs, coverage,
point-in-time evidence and a private operational path remain unresolved.

Code inspection and synthetic reproduction found a concrete review boundary gap:
historical_audit intentionally ignores sources when counting content duplicates,
and historical_training.prepare uses the first record's exact-hash review. At the
verified baseline, equal race data with a different sources value entered the
training partition on that first review alone (reproduced for both 7 and 9 riders).
No real record or training execution was used for this reproduction.

The candidate retains one-race counting, but adds source_variant_races and a
source_variants_require_review reason whenever duplicate provenance differs.
Canonical JSON comparison includes nested receipt/hash metadata and scalar types;
source-object key ordering alone does not create a difference. The training planner
propagates this reason and excludes the whole affected race from every partition,
regardless of duplicate order. Exact-source duplicates still deduplicate normally,
and unrelated reviewed races remain available. Inputs/reviews are not rewritten,
no provenance is silently merged or removed, and no review is generated.
The existing agent preparation path already refuses duplicate IDs before task
creation; new regression coverage preserves that stricter path and no artifacts.

Local synthetic verification: 156 historical tests and 26 agent preparation tests
passed (182 total, 7 new); diff check passed. Includes both input orders, 7/9 riders,
all three partitions, changed/missing/nested sources, exact duplicates, unaffected
races, no model/output creation when all candidates are excluded, and agent refusal
before task/state creation. PR and independent main CI are PENDING. Expect six
workflows because the ML change also triggers the synthetic LightGBM smoke; the
regression matrix stays at 47 jobs. Verify every workflow and all regression jobs,
inspect ML/agent/runtime receipts, merge only the tested head, then verify main.
If main advances, validate the combined head. Do not rerun an unchanged failure.

Next data work: obtain/record separate source-specific evidence for automated
retrieval, storage, training and commercial use plus 7/9-rider/time/field coverage;
a reviewed multi-source merge must retain all provenance and bind its evidence
to the combined record. This PR implements conservative quarantine only, not
that merge, authenticity checking, new licensing, data acquisition or training.
Continue agent recovery work separately; first expired-receipt-write failure is
still unqualified. Arbitrary torn writes, host power loss and live hosting remain
unqualified. KEIRIN.JP HOLD; production predictions, DB writes, external acquisition,
real training (0), credentials/cloud changes and live activation remain OFF.
No outgoing inquiries/messages or provider/race-data retrieval was performed.

## PR #248 verified baseline / live-save refusal candidate — 2026-10-13

### PR #251 initial VM failure / narrowed live-save observation

Initial head 7e84fc4ba21a3879af4eec0051786f9dd1876286, regression
38376408615, live-refusal job 115225786005 failed at 2026-10-13T09:33:08Z
with LIVE_INBOUND_QUALIFICATION_REQUIRED. Boot 4a5d832e-83e6-41b6-b148-bf6a770059c5:
lease start monotonic 112.515434283, before record 115.629697974 (3.114263691 s).
The three inline refusals completed before the original 120515446979 ns deadline,
with unchanged disk hashes and no saved/shutdown markers. The four live probes
still succeeded; expiry later blocked all four and authenticated SSH survived.
However, identity/guard readbacks between the probe-time check and record emission
pushed the complete observation beyond the existing strict 3-second window. This
is a failed experiment, not full VM qualification; no unchanged retry is allowed.

Changed condition: narrow this VM case to the actual save entrypoint only, reducing
work inside the live critical interval. The save/restart/halt negative entrypoint
unit tests remain. Do NOT claim real live restart/halt VM qualification from the
failed candidate. The original 3-second observation, 8-second permission, service
and host-observer limits are unchanged. Require the new complete before record
and all VM cycles/CI to pass; investigate any recurrence rather than relax bounds.

Resumption checked GitHub main 8f502d86e82fb71595475b30978a254db82c846d and
PR #248's Final independent main receipt (in the PR body, not a comment).
Its tested tree is 2b1fbc3d79ad0d26f52ad83a132176b6b5d30524. All five PR
workflows passed; regression 38368617320 passed 46/46. All five independent
main workflows passed: regression 38370154853 (46/46), runtime 38370157007,
PostgreSQL 38370154821, UI 38370154863 and AWS 38370154828; Pages 38370154342
also passed. This resumption independently read all 46 regression jobs and
runtime job 115204854690's exact push-SHA/successful-sibling evidence. The
final receipt supersedes historical PR #248 candidate PENDING text below.
Its actual S3 + ENOSPC/EROFS results are complete within that synthetic scope.
The PR #246 QMP cause remains unknown; inspect bounded first_line on recurrence.

Concurrent open PR #250 only changes AGENTS.md, recording issue #249's
Keirin-data-first / parallel-general-agent priority. Do not duplicate or overwrite
that work. Data permission/HOLD remains the P0 blocker; this candidate continues
the explicitly handed-off isolated agent validation track without source access.
Recheck main and this parallel PR before merging; validate the combined head if
main moves. No outgoing inquiries, messages or race-data acquisition performed.

Code inspection refined the proposed earlier-live-lease storage-fault scope:
there is NO supported durable write during a live inbound lease. save() first
requires the completed same-boot expired recovery and full restored profile via
restart.intact(). Only then does it read the loaded policy, fsync receipt.json,
write policy.json and publish saved. restart/halt publish their shutdown request
only after that save. Do not bypass this admission to manufacture early ENOSPC.

The revised fixed awake live-refusal case calls the actual save entrypoint
while the original 8-second permission is live. Missing completed-recovery
records now produce a specific refusal instead of an incidental FileNotFoundError.
Require the expected save refusal before the original deadline, exact unchanged
policy/receipt/temp-path hashes, no saved/shutdown marker, unchanged packet policy
and guards, and all four established/fresh qualification probes still succeeding
within the original 3-second live observation window. No deadline is extended.
Then require the ordinary expiry, authenticated SSH controls, full unmasked
restoration, successful durable save, normal reboot, fresh keys/boot and a second
full cycle ending in normal poweroff. One new isolated VM job; no external NIC,
host mounts, real keys, cloud mutation, permission replay or active-lease storage.

Local: 63 related tests passed, including 24 inbound-persistence tests (3 new).
Diff check passed. New VM evidence and independent main CI are PENDING;
regression expands from 46 to 47 jobs. Inspect actual new-mode receipts and all
five workflows, merge only the verified head, then verify independent main.
This does not qualify real filesystem failure during active authorization,
arbitrary torn writes, host power loss, or production deployment. Future live
metadata persistence requires its own design and failure/permission boundary.
KEIRIN.JP HOLD; production predictions, DB writes, external acquisition,
real training (0) and live activation remain OFF. Historical failures retained.

## PR #247 verified baseline / suspend then storage-failure candidate — 2026-10-13

Resumption rechecked current main 57e1bdd50214a72973cf6da07a06c8e29d2e72b1,
no open PRs and a clean local tree. PR #247 head b16ddb0d7bcf238a75a3d40b05368ade376e239c
and main share tree 88dc7d00ef9e7f5dd026d80b0ac58a4af2fbfe72. Its final PR receipt
supersedes the historical pending text below. All five PR workflows passed;
regression 38365085660 passed 44/44. All five independent main workflows passed:
regression 38366434687 (44/44), runtime 38366434313, PostgreSQL 38366434464,
UI 38366434461 and AWS 38366434459; Pages 38366435052 also passed. Runtime
job 115192557247 explicitly verified the exact main SHA and successful siblings.
The original PR #246 QMP refusal and the initial PR #247 coordinator timeout
remain historical failures, not reclassified successes. QMP's original first
frame was not captured; its cause is unresolved. Inspect new bounded first_line
evidence if it recurs, and do not retry unchanged or skip a greeting.

The next candidate adds two fixed isolated cases: enospc-suspend and erofs-suspend.
Each first completes actual QMP-observed S3 and wakeup, original 8-second BOOTTIME
expiry, authenticated SSH controls, and full unmasked inbound restoration. The
reboot handler then encounters actual ENOSPC or EROFS on the sole synthetic
64 MiB ext4 policy volume after expired-receipt fsync. It must retain the exact
closed profile and partial pair, publish neither save-success nor shutdown intent,
and leave the guest running with no new RESET/SHUTDOWN event. The supervisor
SIGKILLs only its QEMU and starts a fresh awake recovery guest on the unchanged
image, requiring the same bytes to be refused before any auth/lease execution.
This is failure during the post-S3 save preceding a requested normal reboot;
it does not claim a successful normal reboot following a failed save.

Awake and suspend evidence must match their actual mode and distinct expiry
outcome; negative recovery remains awake. Unit tests prove restart/halt cannot
publish a request or call systemctl after either save error. Existing immutable
lease, per-stage bounds, profile checks, isolated volume/NIC/host guards and
finite 20-minute overall CI observer are retained. No repair, permission replay,
real credentials, cloud mutation, external acquisition or live host operation.

Local: 82 targeted tests passed, including 21 inbound persistence tests (4 new),
plus modified shutdown-intent rejection coverage. Diff check passed. New PR VM
and independent main results are PENDING. Regression expands from 44 to 46 jobs;
inspect both new S3/fault jobs and all existing results before merging exact head.
If a failure occurs, retain head/run/job and investigate before changing/retrying.

Remaining unqualified scopes include storage faults earlier in a live lease,
arbitrary torn writes/host power loss, and real hosted deployment. No production
readiness or overall completion percentage is inferred. KEIRIN.JP HOLD, real
training 0, production predictions/DB writes/acquisition/live activation OFF remain.

### PR #247 initial diagnostic head / sibling CI budget failure

Initial diagnostic head 1fdb7a8e566548571d323afaea78b5c4997f3547 passed the
previously failing legacy persistence job 115183656727 through all eight cases.
QMP greeting refusal did not recur there; its historical cause remains unknown.
PR runtime 38363694438 / job 115183656780 stopped at 07:46:20Z after 600 seconds
while regression 38363694272 was still running (43/44 successful at observation).
The same coordination limit also blocked PR #246 main runtime 38362990933 /
115181377008; main regression ultimately ended 43 success / 1 QMP failure.

Changed condition: increase only the sibling workflow observation budget from
10 to 20 minutes and its outer Actions job cap from 15 to 25 minutes, accommodating
runner queues and the expanded 44-job suite. Still require exact SHA/event/branch,
completed success for every required sibling; completed failure blocks immediately,
and missing/pending never become success at the new finite deadline. No automatic
workflow retry, VM stage deadline, 8-second lease or guest behavior change. A test
now proves real sibling success after 660 seconds is accepted, failure at that
same point is refused, and pending/missing expires at 1200 seconds. Latest changed
head must pass all PR workflows before merge and independent main checks afterward.

## PR #246 main QMP observation failure / diagnostic candidate — 2026-10-13

PR #246 merged as 6b252fdccf520ff28938163608a422b9687a3734, tree
68235d414772d2713eb3317714449fb1b617332b, after exact head
304c374e302a8391251fbbda691e576acd96301e passed all five PR workflows:
regression 38361863327 (44/44), runtime 38361863334, PostgreSQL 38361863356,
UI 38361863517 and AWS 38361863438. PR jobs 115177702975 (all seven invalid
states), 115177702922 (actual ENOSPC), 115177703076 (actual EROFS),
115177702720 (normal) and 115177703092 (crash) all passed with inspected logs.
The fault jobs verified unchanged same-disk partial pairs refused on fresh boots.

Independent main regression 38362990916 failed at job 115181378548,
custody-persistence, on 2026-10-13T07:32:54Z: QMP_GREETING_REQUIRED in QMP.__init__,
before query-block, startup, storage reads or qualification. The failing case was
the legacy valid seed, kernel 6.17.0-1022-azure, QEMU 8.2.2, systemd 255.4.
Other main jobs are still running at this candidate's creation. Main invalid-state
job 115181378425 already passed. Do not report main as all green or silently rerun
the unchanged failed workflow. The original failure remains historical evidence.

The old observer parsed and discarded the first JSON frame before checking for
QMP, so the failure receipt does not reveal that frame. It establishes that the
membership check failed, not why. Event ordering is only a hypothesis; malformed
peer output is not ruled out. No root cause or permanent fix is claimed.

This diagnostic candidate preserves a bounded, JSON-escaped first frame when
handshake admission fails. Invalid JSON and non-object frames are also explicitly
rejected. It still rejects a leading event/return before any capability command;
it does not skip input, reconnect, retry, extend deadlines, or change guest policy.
New tests prove rejection without negotiation, bounded evidence, and correct
handling of fragmented greeting plus a buffered capability reply. 68 targeted
local tests passed, including 9 QMP/VM supervisor tests (3 new).

Changed-condition validation: execute the new diagnostic head through normal PR
CI and independent main CI only after all PR checks pass. If greeting failure
recurs, stop and inspect its first_line evidence; do not retry unchanged. If it
does not recur, report revalidation success separately from the still-unresolved
original first-frame cause. New PR/main results are PENDING.

The prior next-feature work is deferred while this observation issue is checked.
All real acquisition/training, production prediction, DB writes, live activation,
real credentials and cloud mutations remain OFF; KEIRIN.JP HOLD remains active.

## PR #245 verified baseline / inbound storage-failure candidate — 2026-10-13

Resumption rechecked main 4bf4941ecb707db430fb2d8414df0a4771f055f7 and no open
PRs. PR #245 head 8e08b0afbea62b03cba5e00126ac74ed1eb98ad7 and main share tree
f22c04aacb3a57e80cd01a2a1cecdecd68162fcb. Its final PR receipt supersedes the
historical pending text below. All five PR and independent main workflows passed;
regression 38338968173 and 38339912216 each passed 41/41. Main runtime
38339912227, PostgreSQL 38339912266, UI 38339912228, AWS 38339912220 and Pages
38339911792 also passed. Main normal job 115108343535 verified normal reboot,
exact generation-1 checkpoint bytes and PRIOR_BOOT_LEASE_REFUSED; crash job
115108343500 verified actual owned-process SIGKILL, exact same-disk partial
checkpoint bytes and ORPHAN_RECEIPT_REFUSED without auth/lease startup.

The new candidate extends that wider inbound profile with seven independent
invalid ext4 seeds: missing/corrupt policy, stale permission fields, orphan or
mismatched receipt, interrupted temporary file, and corrupt receipt. Each must
fail for its intended reason before link/auth/lease execution, preserve all four
checkpoint path hashes, keep the ruleset empty and unmount cleanly. The shared
seed builder now binds generation-1 negative fixtures to the requested profile,
so a cross-profile rejection cannot masquerade as the intended receipt failure.

Two further cases first complete the actual awake startup/SSH/8-second-expiry/
unmasked-restoration cycle, then use the sole synthetic 64 MiB ext4 volume to
produce real ENOSPC or EROFS on the policy write after the expired receipt fsync.
They require exact kernel errno and filesystem evidence, unchanged closed profile,
no saved marker, and no temporary files. The supervisor then SIGKILLs only its own
QEMU. A fresh boot of the same unmodified image must reject the exact partial pair
and never start auth or lease services. No repair, permission replay, host mounts,
external NICs, deadline relaxation or unchanged CI rerun is introduced.

Local targeted regression: 59 tests passed, including 17 inbound-persistence tests
(7 new). New PR VM evidence and independent main CI are PENDING. The expanded
regression matrix has 44 jobs; inspect all five inbound persistence modes and
all existing jobs before merging the tested head. Preserve exact failed head/run/
job if any failure occurs, investigate its cause before changing/retrying.

These are bounded synthetic guest tests, not arbitrary torn-write/power-loss or
production recovery qualification. Wider-profile filesystem error composition is
not verified until the new VM jobs pass. Next separate scope remains combined
suspend/reboot behavior under storage faults and broader host deployment review.
Real training 0; production predictions, DB writes, external acquisition, live
host application/activation and real credentials remain OFF. KEIRIN.JP HOLD
remains active. Historical failure receipts below are retained.

## PR #244 verified baseline / inbound durable-recovery candidate — 2026-10-13

Continuation rechecked current main 0ce5032c2f64990678885de54841a7a80f14aa27,
merged PR #244 and no open PRs. PR head 2db898a5dea6c1b794aa15b6ad86773d494525c3
and main share tree 0cb8130c2b6f24d660ee52250b864b32436644d0. The final PR #244
receipt supersedes its historical pending text below. All five PR and independent
main workflows passed; regression 38328188658 and 38329055133 each passed 39/39.
Main runtime 38329054976, PostgreSQL 38329055107, UI 38329055112, AWS 38329055026,
and Pages 38329054692 also passed. Original PR #243 failures remain preserved.

Next candidate binds the wider inbound maintenance profile to a strict closed-only
configuration on one synthetic 64 MiB ext4 disk. The prior tcp443-only profile
remains the default and cross-profile loads are refused. The actual systemd
store dependency precedes the gate and both first link-ups. No receipt restores
permission, and no credential is persisted. Normal mode runs both complete
startup/SSH/real-S3-expiry/unmasked-restoration cycles, a normal reboot and final
poweroff, with exact checkpoint hashes, prior-boot lease refusal, fresh public
key material and actual store unmount evidence.

The crash case completes the awake cycle, fsyncs only the expired receipt, then
pauses without publishing a saved marker or requesting shutdown. The supervisor
SIGKILLs only its owned QEMU process. A second fresh process opens the same
unmodified image, requires exact policy/receipt hashes and ORPHAN_RECEIPT_REFUSED,
then verifies both links remain down, an empty ruleset, no auth/check/lease/recover
service execution, and volume/process cleanup. This is a process crash after an
acknowledged fsync; it is not host power-loss, arbitrary torn-write, broader
filesystem-fault coverage or production recovery qualification. No repair,
reseed, forced reboot fallback, deadline relaxation or unchanged CI retry.

Local: 10 new inbound-persistence tests passed; 66 targeted tests passed overall.
Actual new PR VM evidence and independent main CI are PENDING. Inspect both new
normal/crash jobs plus all existing regression jobs before merging a tested head.
If anything fails, preserve the exact head/run/job and investigate that evidence.

Real training 0; production predictions, DB writes, external acquisition, live
host application/activation and real credential use remain OFF. KEIRIN.JP HOLD
remains active. This is common-agent recovery qualification, not a completion
percentage or production-readiness claim. After this candidate, wider-profile
invalid/missing durable configuration and real filesystem error composition
remain separate unverified scopes; the legacy narrower-profile evidence cannot
be silently promoted to those claims.

## PR #243 main observation failure / stage-observation correction — 2026-10-13

PR #243 merged as b1c9a6fffca12e0f00153e5b8df63dd782226782 (tree
90d42d290d5daa0bcfaa1ab2fe7049ae08f9b807). Its corrected PR head
3e9ec7132aa2def784d6a9e619ffe0a1f62a6014 passed all five workflows, including
regression 38326427654 (39/39), both normal-restart cases and corrected peer-link
cleanup. The earlier cleanup failure below remains part of the evidence history.

Independent main regression 38327203303 failed awake restart job 115068529971.
Boot 6b1c6985-3c3b-4eea-ad0d-02ff2adaa2b1 completed the full startup/authentication/
expiry/unmasked recovery cycle and actual ordered systemd shutdown. Both links
went down while the peer was alive; the restored profile stayed unchanged with
expired guards absent; the peer and SSH stopped. QMP confirmed guest-origin RESET.
The next matrix record did not arrive within the aggregate 100-second deadline;
the only retained serial diagnostic was the kernel restart message. This does
NOT prove either a policy failure or a hung reboot. On the successful corrected
PR suspend case, RESET-to-matrix already took about 99.5 seconds (second guest
monotonic matrix time 97.166s). The old observer combined firmware/kernel, setup,
gate, link and the exhaustive matrix into one budget, hiding startup progress.

The correction adds opt-in setup-entered/setup-completed/gate-completed/link-
completed records to the restart guest. The host requires this exact sequence,
a fresh same boot ID and finite ordered monotonic clocks, with a separate fixed
100-second observation budget at each stage and at the existing matrix record.
This increases the aggregate startup observation allowance; it does not change
any guest service's 90-second limit, RPC's 30-second limit, immutable 8-second
lease, <3-second live proof, <7-second resumed probe or authentication criteria.
Missing/stalled stages still fail; there is no reset, retry, fallback or deadline
extension based on noisy progress. The fixed workflow job bound also remains.

Local inbound suite: 25 tests passed, including deterministic >100s aggregate
progress, wrong stage, stale/mixed boot, reversed/nonfinite clock, activation and
stalled-channel rejection. This is a changed-condition diagnostic/correction,
not an unchanged rerun; actual new PR/main VM evidence remains pending. If it
fails, use the last completed stage to investigate, without marking main green.
Durable wider-profile configuration and crash recovery remain unverified. All
production/training/acquisition controls and the KEIRIN.JP HOLD remain in force.

## PR #243 cleanup race correction — 2026-10-13

Initial head 45d8fec85b58d8b2404c6254ebe82bd8c0c7e48e / regression 38325699996 /
existing inbound-lease job 115063731642 failed while cleaning its completed awake
cycle. Startup matrix, authentication, expiry, restoration and recovery records
had passed. The report's interface-name check saw host0, but the following
`ip link del host0` failed with Cannot find device. The peer namespace is stopped
immediately before this cleanup and its destruction asynchronously removes veth
pairs: the existing check/delete sequence cannot assume the link still exists.
This does not establish why the race appeared on this runner rather than earlier
runs; no policy or expiry failure was observed in this trace.

Cleanup now accepts a failed deletion ONLY when a fresh namespace query proves
the owned link absent. A still-present link or a successful command that leaves
it present remains a failure, and the final empty-rule/lo-only/no-peer checks
remain. No blind deletion retry is added. The new normal-shutdown observer also
uses a single full link-state snapshot instead of querying a name and then a
potentially disappearing link separately. A local regression simulates the
between-check-and-delete disappearance, persistent failure, false removal success,
already-absent links and refusal of unowned names. Local total: 53 targeted tests
(inbound 24, systemd 14, packet 15). Actual corrected CI is pending. Original
failure retained; timing limits and packet/authentication criteria are unchanged.

The original new restart jobs did complete successfully before correction:
awake 115063731879 (boots 175a1eea-8d0b-49d7-8446-25c00862352f ->
891271e1-5ee8-4b6c-ac3d-7f0aad7d0e9e) and suspend 115063731951 (boots
3f1fe44c-e578-457e-8259-ae382c7210b4 -> c00cc4b4-b953-477b-a359-da67e4ac7aa2).
Both showed both-links-down while the peer was alive, unchanged unmasked profile,
actual reverse service stops, normal reboot then poweroff, fresh key digests and
full cycle revalidation. These successes do not override the failed existing
cleanup job or qualify the changed correction head without fresh CI.

## PR #242 verified baseline and inbound normal-restart candidate — 2026-10-13

Current main rechecked: ba5fd544d66964422d1cdc29fd02dd31437537e3; PR #242 merged,
no open PRs at continuation. PR head 76e65c1d76a239aa9a7e5bcd94ccb5a8460b3055
and main share tree 7def3964a5bfe8983e5f2e22fb6eeb5ae580dc31. PR #242's final
receipt supersedes the older candidate UNVERIFIED text below. All five PR and
independent main workflows passed, regression 37/37 each, plus main Pages.
PR regression 38322256249 / inbound lease job 115052818578; main regression
38323129977 / inbound lease job 115055563782. Main awake and real-S3 boots both
proved expired existing/fresh qualification denial, authenticated SSH continuity,
exact maintenance restoration, and all 28 input paths / 16 loopback controls
after expired guards were removed. Main S3 boot 2937eb7b-f5d8-41b2-81af-936e1079a98e
completed its first resumed packet probes 2.810746412 monotonic seconds after
lease start, within the unchanged 7-second bound. No failed candidate runs or
unchanged retries were needed for PR #242.

Next candidate composes the verified inbound cycle with normal guest-manager
shutdown/reboot and another complete fresh-boot cycle. Two separate CI matrix
jobs cover awake and actual S3 expiry. Each job uses one diskless QEMU process,
normal reboot.target followed by poweroff.target, actual guest-origin QMP events,
and a zero exit after poweroff. No forced reboot or QMP reset is used. The
8-second immutable deadline, <3-second live window, <7-second first-resume window,
90-second services and existing observation bounds remain unchanged.

Before shutdown, the restored wide profile must match exactly with the expired
guards already absent. The link service closes BOTH host0/host1 while the peer
still exists, repeats closed qualification probes, and retains the full inet
profile. Actual inactive timestamps must show the reverse service order before
the shutdown checker permits final.target. Peer and SSH processes must be gone.
After normal reboot, fresh empty startup state, a distinct boot ID and newly
generated public host/client key digests are required. The complete original
startup matrix, SSH positive/negative authentication, expiry and unmasked
recovery matrix run again. Key digests ignore comments; no private keys leave
the guest. Different digests are not a claim of an old-key revocation test.

Local: 52 targeted tests pass (inbound 23, systemd 14, packet 15). New refusal
cases cover stale/unexpired recovery, partial link shutdown, changed or masked
profiles, incomplete/reordered service stops and reused boot/key evidence.
Actual normal reboot/poweroff composition, exact PR CI and independent main CI
remain pending for this candidate. Next: inspect actual guest evidence, fix any
observed failure without blind retries, merge only a verified head, then inspect
main CI. Durable on-disk recovery and crash recovery of this wider profile remain
separate unverified compositions; this diskless reboot test does not establish them.

Real training 0; DB writes, production prediction, external acquisition, live
activation and real credentials remain OFF. KEIRIN.JP HOLD remains active. This
is synthetic common-agent recovery work, not a product completion percentage.

## Inbound expiry/recovery composition candidate — 2026-10-13

Continuation baseline rechecked: main 9511be129821ef96ebc91c8dff4cc9320a2a1a90,
PR #241 merged, no open PRs. PR #241 head 1171d3ad687acf91c769d225d9f971fec5fea679
and main have tree 712e654b0ecfbcd7afb5310f4c5c780d66735471. The final receipts in
PR #241 supersede the historical pending checkpoints below: all five PR workflows
and all five independent main workflows passed, regression 36/36 on each, plus
main Pages. PR regression 38287640635 / inbound job 114939720627; main regression
38288630733 / inbound job 114942976249. All five boot cases completed, including
full input matrix and authenticated management. Earlier failures remain recorded.

This candidate adds a separate opt-in diskless QEMU job, after the existing
sealed-input startup/matrix/auth stage. The two fresh guest cases are awake
expiry and real S3 expiry. Each retains the original 8-second immutable deadline,
<3-second live window and <7-second first post-resume packet window. The first
post-resume network actions are old/fresh IPv4/IPv6 qualification probes, before
policy reads, SSH checks or recovery. Actual existing/fresh SSH then verifies
management continuity. Only synthetic documentation addresses and ephemeral
keys are used; the VM has no external NIC or disk.

The qualification replacement requires unchanged startup identity, a live nft
lease snapshot and unchanged attached immutable boottime program. A late recovery
replaces only the owned wide profile with maintenance; original guard identities
must survive unchanged. After exact maintenance readback, a separate recovery
service removes the expired experiment guards and reruns all 28 input paths and
16 loopback controls, plus closed outbound qualification, so outer guards cannot
mask an incorrect restored profile. Same-boot identity, actual systemd dependencies,
service timestamps and owned cleanup are required. The new loader build permits
only the fixed lo/host0/host1 topology with additional command-line opt-ins; old
loader builds and CI cases retain their previous interface gate.

Local verification: 47 targeted tests pass (inbound 18, systemd 14, packet 15);
new C loader builds with -Wall/-Wextra/-Werror and refuses host invocation.
Actual combined guest execution and exact PR/main CI are still UNVERIFIED.
Next: publish this candidate, inspect actual CI packets/S3/auth/recovery evidence,
resolve any demonstrated failure, then merge only the verified exact head and
check independent main CI. Combined restart/durable recovery remains later work.

Real training 0; DB writes, production predictions, external automatic acquisition,
live activation and real credentials remain OFF. KEIRIN.JP HOLD remains in force.
No completion percentage or whole-agent readiness claim follows from this test.

## PR #241 phase observation budget correction — 2026-10-13

Head 5d99b09fb5a82cb86f6e2089fec82f3885b0a41a / regression 38287038436 /
job 114937778223 passed the full control again. On the closed boot its unbound
route readback measured IPv4 source 192.0.2.2 and IPv6 source 2001:db8:1::9.
That establishes the multi-address selection hazard; it does not retroactively
provide the missing original SSH exception. The source-bound attempt reached
SSH setup, then the supervisor's single 100-second whole-boot observation
budget expired without an SSH outcome. Successful authentication is still
unverified on that head.

The exhaustive matrix now publishes a distinct required same-boot completion
record before SSH. The supervisor bounds startup/matrix and auth/report as
separate 100-second phases, instead of incorrectly budgeting both as one.
This explicitly increases the supervisor's possible total observation window;
packet timeouts, SSH/RPC limits, 90-second per-service bounds and all preexisting
lease/S3 timing requirements are unchanged. Final evidence must contain the
exact same complete matrix, same boot and ordered timestamps, plus real SSH
results; a phase marker alone cannot pass. Local targeted total: 44 tests pass.
Corrected complete five-case guest run and exact PR/main CI remain pending.

## PR #241 SSH control failure and source binding — 2026-10-13

Head 87a4379615692fd9d67708f5a334daa67a6a1669 / regression 38286291962 /
job 114935359179 included nft_ct and its dependencies and passed the full
28-path unfiltered control, all 16 loopback checks and cleanup. The closed
case then failed during check with ConnectionRefusedError from its control
channel. Cleanup could mask the initial SSH error, and the supervisor did not
preserve preceding diagnostics on this failure path. Therefore the original
SSH failure cause is not yet proven.

The peer deliberately has approved .2/.3 and unapproved .9 addresses for both
IP families. SSH had no explicit source binding, unlike every matrix flow.
The corrected inbound fixture pins fresh/existing and negative-auth SSH clients
to .2/::2 using OpenSSH -b; other SSH fixtures retain their unchanged default.
Unbound route-source readback is now included in evidence to test the source
selection hypothesis. Peer failures return an explicit error while preserving
the control channel for cleanup; primary exceptions and bounded preceding
diagnostics survive shutdown errors. No firewall allowance or authentication
criterion is widened. Local targeted total: 43 tests pass. Corrected five-guest
VM and exact PR/main CI remain required; both original failures are retained.

## PR #241 missing conntrack module correction — 2026-10-13

Initial head ea09e7a13b84d01b29d18e112ac8eda688b5a31b failed regression
38285673690 / inbound boot job 114933338833 before the unfiltered control
could start. nft rejected the ct direction expressions with ENOENT. The guest
module manifest contained veth/nf_tables but no nft_ct; the old packet image
had not needed conntrack expressions. Linux net/netfilter/nft_ct.c registers
the ct expression, including NFT_CT_DIRECTION. This is a fixture dependency
omission, not a measured policy denial. Source inspected:
https://raw.githubusercontent.com/torvalds/linux/master/net/netfilter/nft_ct.c

The inbound image now explicitly includes nft_ct and modprobe-discovered
matched-kernel dependencies, and loads it before compiling the reference.
Original images retain the previous module set. Unexpected guest-stage failures
now stop the supervisor promptly; only deliberate negative-case gate errors
continue to final service-state evidence. No rule, packet requirement, deadline
or acceptance window was relaxed. Local total: 42 targeted tests pass (inbound
boot 8, boot 5, inbound 5, lease 5, restart 4, packet 15). Corrected VM execution
and exact PR/main CI remain pending; the original failed run is retained.

PR #241 is open. Publication approval has been received; the older blocked
handoff below is historical. No live activation or data-use permission changes.

## GitHub publication authorization — 2026-10-13

The user replied “続けて” at 2026-10-13 02:37 JST to the explicit request
to publish this change, create the PR, inspect CI and merge only after success.
This authorizes resuming that bounded publication flow. The earlier rejection
below is historical; actual VM/CI verification remains required.

Local branch `codex/boot-inbound-composition` contains the six-file inbound
startup/authentication increment below. All 25 targeted tests and diff checks
passed. The automatic approval reviewer rejected the GitHub push because the
continuation instruction did not explicitly authorize disclosure of this new
payload and work-history changes to the destination. No alternate write route
or push retry was attempted. The GitHub connector subsequently confirmed the
repository is public, owned by bzlove178100, and has push permission; the new
remote branch returned 404. No PR, new CI result or main update exists for this
increment. GitHub publication still needs the user's explicit approval under
that review decision. After approval, push this existing branch, create its PR,
inspect all CI results, fix any actual failures, and merge only after success.
Do not count the five-guest experiment as executed from local unit-test results.

## Sealed inbound startup with authenticated management — 2026-10-13

PR #240 is merged at c2bc2df0f336fb8a70fcef223e39e7fffe0adc8c. Its exact
PR and independent main passed all five project workflows and 35 regression
jobs; main Pages also passed. Main regression 38264361449 and inbound job
114862648919 are final predecessor receipts. This supersedes the candidate
pending checkpoints below without erasing either earlier fixture failure.

This increment composes the fixed PR #240 maintenance profile with actual
systemd startup and ephemeral authenticated OpenSSH in diskless QEMU guests.
Both internal links stay down until the compiled complete policy matches the
independent peer-namespace reference and its exact identity is sealed. The
link service checks the same boot, policy and still-down links before first
activation. Missing, invalid and widened policies must prevent both link and
check service entry. The original boot/lease/storage jobs remain unchanged.

A separate explicitly unfiltered control boot requires all 28 IPv4/IPv6 TCP
and UDP paths to reach active wildcard listeners. The closed boot repeats all
28 fresh paths, including wrong source, destination, interface and source port
53, with before/after input counters distinguishing drops from lost replies.
All 16 loopback listener controls must work. The echo listeners are stopped
before real SSH starts; approved fresh and existing SSH, wrong client key and
wrong server identity checks run under the unchanged sealed maintenance policy.
Owned services, SSH children, links, tables and VM images must be cleaned.
No external NIC, disk, live key or host service/network change is introduced.

Local: 25 tests passed (inbound boot 6, boot 5, inbound 5, lease 5, restart 4),
and whitespace validation passed. Actual five-guest execution and exact PR/main
CI are pending. Final PR receipts will supersede this candidate checkpoint.
This verifies sealed startup plus authentication only if the VM test passes;
it does not qualify the wider policy with lease/S3/recovery or durable reboot,
all protocols/fragments, live application binding or production deployment.
Next: compose the verified wider startup profile with immutable qualification
expiry and recovery, retaining the existing timing and packet acceptance gates.
Phase 3 incomplete; KEIRIN.JP hold, real training zero, DB write OFF and live
activation OFF remain unchanged.

## PR #240 fresh phase fixtures after blocked TCP reuse — 2026-10-12

Head 7593c7bc288d90a67f1c03a75a7f27ff9ffdec91 / regression 38262328563 /
job 114855718251 passed all unfiltered positive controls, legacy gap
reproduction and the entire maintenance matrix. The UDP endpoint fix therefore
restored the required real multi-address control. The next qualification check
stopped at old ip_wrong_source: expected/observed denial matched, but early,
late and tracked counters were unchanged (13/4/10 before and after), so no
actual new packet was available as evidence. Previously blocked TCP writes
can wait behind outstanding data/retransmission; socket failure alone is not
accepted as a firewall observation.

Each of maintenance, qualification and restored now runs in a fresh outer CI
namespace, repeating every positive control and legacy-gap reproduction with
fresh sockets/conntrack state. Qualification still performs the exact owned
maintenance-to-qualification transition; restored still performs both owned
transitions and checks exact maintenance readback. Each phase independently
requires actual fresh and preexisting original-direction traffic plus early/
late counters, allowed management and live listeners. No counter or denial
requirement was removed, no timeout was raised, and no runtime policy changed.
Local 13 tests pass. All three phase receipts and exact PR/main CI are pending.


## PR #240 initial positive-control failure — 2026-10-12

Head 9036fa164b971c61db85afa4bba319773582c272 failed regression 38261852097 /
inbound job 114854082274 at ip6_udp22 before any candidate filter was installed.
Existing transition/recovery jobs passed. The wildcard UDP echo helper used
sendto without received packet information on a host with two IPv6 addresses;
reply-source selection was not bound to the original local destination. The
log did not record that address, so this is the hypothesis to verify, not a
claim that the rejected policy caused the failure. The corrected UDP helper
uses recvmsg destination/interface information and sendmsg to preserve the
reply endpoint for both IP families. Local real loopback UDP checks pass;
actual multi-address namespace controls remain required. Failure diagnostics
now include per-flow result and before/after counters. No policy or negative
acceptance criterion changed. Local total is now 13 tests, including 5 inbound.
Corrected exact-head CI remains pending; retain the initial failure evidence.


## Exact inbound path and connection direction — 2026-10-12

PR #239 merged at a954a6ee062fc0c937422ac072221127e810850a. The corrected
PR and independent main each passed five project workflows and 34 regression
jobs; main Pages deployment also succeeded. Main regression 38256307958,
I/O job 114835180821, crash 114835180860 and normal persistence 114835181213
are final receipts. Both ENOSPC/EROFS cases and all eight normal storage cases
passed. The observed 327 free blocks exactly matched 327 reserved clusters,
with zero available blocks, confirming the corrected ext4 accounting. These
receipts supersede the old pending checkpoints below; the initial failure stays
part of the history.

This increment tightens the existing pure synthetic network rehearsal profile.
Every non-loopback allowance now fixes host0, both endpoint addresses and the
connection direction: management ingress is original / response is reply;
DNS/time/qualification egress is original / ingress is reply. Source-only and
state-only allowances did not encode those boundaries. No live host is changed.

The new CI-only experiment uses two empty private network namespaces and two
internal veth paths, with fixed documentation addresses/static neighbours.
Wildcard TCP22/80/443/8080 and UDP22/53/443/8080 echo listeners are deliberately
active positive controls. Twenty-eight IPv4/IPv6 cases cover approved management,
wrong source/destination/interface, other transports and preexisting inbound
TCP/UDP flows using source port 53. A reconstructed legacy control exactly
matches the prior main renderer; it must reproduce the destination/interface
and DNS-reply-direction gaps before the corrected rules can pass. Independent
counters before/after the policy distinguish input drops from lost replies;
old flows must still be observed as established in the original direction.
Maintenance, qualification and restricted restoration all retain the boundary,
working approved management and live loopback listeners. Owned processes, links
and tables must disappear; the runner host network namespace remains unchanged.

Local validation: 12 tests pass (inbound 4, transition 4, watchdog 4), legacy
control matches the old renderer exactly, and diff whitespace check passes.
Actual kernel reproduction/acceptance and exact PR/main CI remain pending.
Final receipts in this increment's PR supersede this candidate checkpoint.
This is transport-level isolated evidence: actual SSH authentication is covered
separately, and this does not establish live cloud policy, application bind
configuration, full boot/lease/recovery composition, all IP protocols/fragments,
or physical storage power-loss durability. Phase 3 remains incomplete. Next is
composition of the wider boundary with sealed startup and the authenticated
management path; no production binding or credentials are activated.
KEIRIN.JP hold, real training zero, DB write OFF and live activation OFF persist.



## PR #239 initial CI failure and correction — 2026-10-12

Regression 38254192708 / job 114827886531 failed before the actual policy
write: the test incorrectly required statvfs free blocks to equal zero after
single-block fallocate ENOSPC. ext4 retains an internal reserved-cluster pool,
including for uid 0 (kernel ext4_has_free_clusters; admin-guide/ext4 sysfs).
The corrected fixture records free/available blocks and reserved clusters;
it requires no more free blocks than that observed pool and bounded allocation.
A cluster is at least one block, so this comparison is conservative. It also
records the allocator ENOSPC separately. The independent real atomic policy
ENOSPC, unchanged durable bytes, no saved marker, and fresh-boot orphan refusal
remain mandatory. No mount/reservation configuration or product acceptance
was changed. The initial log did not include counts, so reservation accounting
is the source-supported hypothesis to check with the corrected VM evidence.
Sources: https://www.kernel.org/doc/html/latest/admin-guide/ext4.html
and https://github.com/torvalds/linux/blob/master/fs/ext4/balloc.c .
Corrected exact-head PR/main VM results remain pending; no unchanged rerun.

## Actual bounded filesystem write failures — 2026-10-12

PR #238 is merged at 13b14c70c040fe106d9d4fc02e0b5e1439782782.
Its exact PR and independent main passed five workflows and 33 regression
jobs. Main regression 38249212919, crash job 114810836644 and normal storage
job 114810836520 verify SIGKILL/same-disk refusal and all eight existing cases.
These final receipts supersede the historical pending checkpoint below.

This increment adds real filesystem faults only inside the fixed 64 MiB
synthetic guest volume. After a durable receipt, an explicit mode either
allocates bounded blocks until ENOSPC or remounts that guest filesystem ro.
The ordinary second atomic policy write must raise actual ENOSPC/EROFS.
The original OSError is re-raised; no saved marker or normal shutdown can be
published. Evidence requires exact unchanged policy/receipt bytes, blocked
IPv4/IPv6 TCP443, observed mount mode, bounded capacity and no leftover temp.
A supervisor kills only its owned QEMU and reopens the same disk in a fresh
guest: orphan refusal, no link/auth/lease execution and cleanup are required.
No host disk mount, live credentials, source capture or production activation.
The existing default writable mount check remains strict; readonly acceptance
is explicit only for the fault observer. All previous storage jobs remain.

Local validation: 36 tests pass (I/O 6, crash 5, persistence 11, restart 4,
boot 5, lease 5). Real VM ENOSPC/EROFS and exact PR/main CI are pending.
Final receipts in this increment's PR supersede this candidate checkpoint.
This is not physical media EIO, sudden host power loss, arbitrary torn-write
coverage or automatic repair. Phase 3 remains incomplete. Next work after
qualification is the remaining broader protocol/inbound and production-binding
scope; physical-device failures and repair remain separate unqualified areas.
KEIRIN.JP hold, real training zero and live activation OFF remain unchanged.

## Actual VM interruption between durable writes — 2026-10-12

PR #237 is merged at c77bea236b89439484eeef710ec2f25703fc1f78.
Its exact PR and independent main CI passed five workflows and 32 regression
jobs each, including all eight persistence cases and cleanup. Main regression
38247234674 and persistence job 114804079555 are the verified predecessor.
These receipts supersede PR #237's historical pending checkpoint below.

The next increment adds an explicit isolated-guest crash barrier after the
receipt has been written, fsynced and read back, before policy replacement or
saved-marker publication. The guest first completes authenticated SSH and the
unchanged awake lease expiry checks; IPv4/IPv6 TCP443 must remain denied at the
barrier. The supervisor SIGKILLs only its own QEMU process, requires the actual
signal exit, then starts a fresh guest using that same private 64 MiB disk.
No reseeding, repair, host mount or normal guest shutdown occurs between boots.
The new boot must refuse the orphan receipt, read identical policy/receipt
hashes, keep its link down and never execute observe/auth/lease services.
Owned processes, image and disk must be removed and host boot/netns unchanged.

Local validation: 30 tests passed (crash 5, persistence 11, restart 4, boot 5,
lease 5). Actual VM experiment and exact PR/main CI are pending. A bounded
barrier timeout refuses continuation. Existing normal persistence/S3 and
seeded-negative tests remain required and unchanged in their acceptance rules.

This qualifies only the controlled crash point if the VM experiment succeeds.
It does not prove physical power-loss durability, arbitrary torn writes, real
storage I/O failures, automatic repair or production readiness. Next unverified
storage work is actual filesystem write failure; wider protocol/inbound and
production binding also remain. Phase 3 incomplete. KEIRIN.JP hold, real
training zero and no live activation remain unchanged.

## Interrupted checkpoint refusal — 2026-10-12

PR #236 is merged at cb49614cc051109430dc03a0b456e9b30d875fe3.
Its exact PR and independent main CI passed five workflows/32 regression jobs
(main regression 38227805065, persistence job 114739520695). This supersedes
the historical pending checkpoint below; PR #235's original main failure
remains part of the evidence.

This candidate rejects orphan receipts, mismatched policy/receipt boots,
malformed or duplicate receipt keys, and leftover policy/receipt temporary
files before installing a startup gate. Dangling symlinks are not treated as
missing state. It never repairs ambiguous checkpoints or grants permission
from saved receipts. Every storage validation/read failure emits a refusal.

Local tests: 46 passed. A real child process exits after file fsync and before
rename, leaving a refused temporary file. Injected ENOSPC/EROFS/EIO failures
cover opening, file sync, replacement, directory sync and readback; no success
receipt is returned. A failed second write cannot publish the saved marker.
These are controlled process interruption and simulated I/O errors, not
physical power-loss, real block-device fault or production crash qualification.

The existing isolated persistence VM job adds four seeded recovery states:
orphan receipt, mismatched pair, interrupted temporary file and corrupt receipt.
Exact PR/main CI is pending; final receipts belong in the PR body and private
progress record. Phase 3 remains incomplete. Abrupt VM/disk failure, actual
filesystem I/O failure, broader protocols and production binding remain open.
KEIRIN.JP hold, real training zero and no live activation remain unchanged.

## Atomic guest readiness publication after main failure — 2026-10-12

PR #235 merged at 1e53a38e0d7354038bceaf52764f08bed9ad306d after
five PR workflows/32 regression jobs passed, including all four persistence
cases. Its independent main persistence job 114732244394 failed: positive
two-boot storage/S3/shutdown passed, but the following guest hit JSONDecodeError
reading a transient readiness marker before host0 existed. Main qualification
is incomplete; this supersedes any implication that PR success verified main.

The setup peer published its final path before JSON writing finished, while
the parent waited only for existence. A controlled empty-write window reproduces
this exposure in the old writer. This fix writes a sibling then atomically
replaces the final path; readers cannot see partial JSON. A failed replacement
retains the previous complete marker. These are transient /run publication
tests, not durable-disk power-loss claims. Unexpected startup errors now stop
the persistence supervisor immediately with diagnostics.

Local tests: 40 passed, including two readiness-publication regressions.
Exact follow-up PR and independent main CI pending; final receipts belong
in the PR body and private progress record. No timing/acceptance relaxation,
unchanged rerun or production activation. Source hold and real training zero
remain. Durable storage fault injection and broader production qualification
are still pending; Phase 3 incomplete.

## Guest-owned durable closed configuration — 2026-10-12

PR #234 is merged at ef5d0535f4ee61b4258d94b88f360c8223fa637e.
Its PR and independent main CI passed five workflows/31 regression jobs.
Each normal reboot/poweroff job produced 48 boot/lease/shutdown records.
Final receipts in PR #234 supersede the historical pending checkpoint below.

This candidate adds one explicit 64 MiB private regular-file ext4 disk to the
otherwise isolated synthetic guest. No host disk is mounted or formatted.
A mounted, strictly validated closed configuration must precede the startup
gate and link. The guest writes/fsyncs a new policy generation plus an expired
lease receipt before normal reboot. A different boot must read the exact
persisted hashes while refusing the prior-boot receipt as authorization.
Fresh pinned-key SSH and a newly created immutable lease remain required;
actual S3/expiry checks keep the original eight/three/seven-second bounds.
Missing configuration, malformed JSON and an injected stale lease field must
fail the gate and prevent link/observe/auth/lease entry. Shutdown must unmount
the volume; all synthetic VM/disk files must be removed afterward.

Local tests: 38 passed. Actual persistent-disk experiment and exact-head/main
CI results pending; final receipts belong in the PR body and private report.
Atomic writes are implemented, but abrupt power loss, partial multi-file
writes, storage errors and production configuration migration remain unqualified.
Broader protocol/inbound coverage and real host/credential/runtime binding
remain pending. Phase 3 incomplete; KEIRIN.JP acquisition hold and real training
zero unchanged. No live application or external data acquisition is enabled.

## Composed normal systemd reboot and poweroff — 2026-10-12

PR #233 is merged at 35e2dc73e504459c8071ba760ff4ee62726a5981.
Its PR and independent main CI passed five workflows/30 regression jobs,
with eight boot and 18 lease/authentication records per run. Final receipts
in PR #233 supersede the historical pending checkpoint below.

This candidate retains the same closed startup, pinned-key SSH, immutable
eight-second lease and awake/actual-S3 expiry checks. It adds the installed
systemd normal reboot/poweroff target transaction (no force CLI), ordered
owned-service shutdown, packet denial and unchanged guards through link-down,
then retained inet policy and absent SSH/peer processes after services stop.
Device removal may remove TC/netdev attachments; unchanged full guards are
checked while the link exists, not falsely claimed after device destruction.
A real guest-origin reset must lead to a different boot ID and repeat the full
closed-before-link/authentication/expiry cycle. Normal guest poweroff must
exit QEMU successfully. Both awake and S3 modes are exercised. Installed
shutdown unit hashes join image/binary provenance.

Local tests: 33 passed. Actual new guest transactions and exact-head/main CI
are pending; final receipts belong in this PR body and private progress record.
Writable configuration persistence, wider protocols/inbound paths and live
production bindings remain unqualified. Phase 3 remains incomplete.
KEIRIN.JP acquisition remains on hold; real training and new race acquisition
remain zero. No host power/network/service change or live activation.

## systemd startup composed with authenticated immutable lease — 2026-10-12

PR #232 is merged at cd8429d5b4f29a0536aa2f0c29f69f7952420224.
Its PR and independent main CI passed five workflows/29 regression jobs.
Actual systemd boot/reboot, missing/invalid policy and cleanup yielded eight
boot records per run. The previous pending checkpoint is historical; PR #232
contains the final receipts.

This candidate joins real systemd setup -> closed policy -> link -> observed
closed startup -> SSH authentication -> immutable lease in each isolated guest.
Initial SSH includes pinned host keys and wrong-client/wrong-host-key refusal.
The original eight-second absolute boottime deadline, three-second live window
and seven-second first-resume window remain unchanged. Awake expiry and actual
S3 must deny old/new IPv4/IPv6 TCP/443 while established/fresh SSH succeeds.
Missing/invalid startup policy must prevent observe/auth/lease units executing.
All owned guest services, SSH processes, rules, interfaces and VM files must
clean up. No real host, external NIC, credential or application activation.

Local tests: 29 passed; both original/systemd boottime loader variants compiled
and refused ordinary-host execution. Actual composed guest/CI results pending;
final receipts belong in the PR body. This composition does not yet establish
combined reboot/shutdown recovery or writable production configuration
persistence. Broader protocol/inbound coverage and production binding remain.
Phase 3 incomplete; KEIRIN.JP acquisition hold and real training zero unchanged.

## Actual systemd closed boot and guest reboot — 2026-10-12

PR #231 is merged at d90198582f3e167c4b1e332436ac9f6dbd4a62f2.
Its PR and independent main CI passed five workflows/28 regression jobs, with
70 packet records each, including authenticated SSH across awake/S3 expiry.
The previous pending checkpoint text is historical; PR #231 has final receipts.

This candidate boots actual systemd as PID1 inside diskless isolated QEMU.
Fixed units require setup -> sealed closed policy -> internal link activation.
A separate observer requires real manager dependencies/start/exit timestamps,
policy identity and IPv4/IPv6 packet results. Missing/invalid policy must fail
the gate and prevent the link service from executing. The closed case asks
guest systemd for a forced reboot, requires a guest-origin QMP reset and a new
boot ID, then repeats policy-before-link measurement from the same immutable
image. This tests image-backed configuration, not writable production disk
persistence or the full normal shutdown unit transaction. No host service is
installed; no host reboot, external NIC, host mount or live activation exists.

Actual guest/CI results are pending; final receipts belong in the PR body.
SSH/lease/S3 remains independently qualified by PR #231, not yet composed into
this systemd boot harness. Broader protocol coverage and production host/service
binding remain. Phase 3 is incomplete. KEIRIN.JP hold and training zero remain.

## Authenticated management in the integrated guest — 2026-10-12

PR #230 is merged at 5eb1fafad5bd7ed973e88562498424c800e65f20.
Its PR and independent main CI passed five workflows/28 regression jobs;
each run retained 50 packet records, including both integrated awake/S3 cases.
The previous integration-pending paragraph below is historical.

This candidate adds two fresh isolated guests with real OpenSSH management.
Keys are generated inside each guest; clients pin the ephemeral host key, and
wrong client keys and wrong host keys must be rejected on IPv4 and IPv6.
The only permitted remote command echoes bounded synthetic tokens. Existing
SSH sessions and fresh authenticated connections must succeed after awake
expiry and actual S3 while the original TCP/443 qualification probes deny.
SSH setup precedes the lease; SSH after-checks follow the first packet result.
The original 3-second live and 7-second first-resume windows are unchanged.
All previous controls remain mandatory. OpenSSH packages are downloaded and
extracted, never installed or started on the CI host; provenance is recorded.

Local packet/startup/VM tests: 23 passed. Actual SSH guest results and CI are
pending at this checkpoint; final receipts belong in the PR body. This is
synthetic guest authentication, not production management qualification.
Phase 3 still needs actual OS service ordering/reboot persistence, broader
inbound/protocol coverage and production binding. No live host, credentials,
scheduler, data acquisition or learning activation. KEIRIN.JP hold and zero
real training remain unchanged.

## Closed startup to immutable lease integration — 2026-10-12

PR #229 is merged at 9c1d8a2a34db568748cd8616d06463c851c042d9.
Its final PR and independent main CI passed five workflows/28 regression jobs;
all four startup cases were measured. The prior pending text below is historical.

This candidate joins the previously separate fixed guest experiments: install
and seal the closed TCP/443 policy while host0 is DOWN, enable the internal link,
measure initial denial and management echo, refuse release with missing guard
proof and measure continued denial, then install/read back the original nft
lease and immutable TC boottime program before removing only the startup gate.
Require old/new IPv4/IPv6 qualification connections during the original lease,
then denial after awake expiry or actual S3; management connections must survive.
No guard reinstall, deadline extension or post-resume policy repair is added.
Original open/nft-only/boottime controls and four startup cases remain mandatory.

Local packet/startup/VM tests: 21 passed. Actual integrated guest results and CI
are pending at this checkpoint; final receipts belong in the PR body. Changed
rules, TC identity and exhausted-deadline rejection are local unit cases; the
actual guest negative control is missing proof before guard installation. This
is not hostile privileged-writer attestation. Keep the existing 3-second live
and 7-second first-resume windows unchanged.

Next after scoped integration: authenticated management, actual OS service boot
ordering/reboot persistence, broader inbound/protocol coverage and production
binding. TCP/22 is still echo, not SSH. Phase 3 remains incomplete. No live host,
credential, scheduler, source capture or learning activation. KEIRIN.JP hold and
training zero remain unchanged.

## Closed startup candidate — 2026-10-10

PR #228 is merged at 97014583a70460673040576cac73e507ae7dabee;
its final PR and independent main-push five workflows/28 regression jobs passed.
It qualified the immutable boottime gate only in fixed isolated awake/S3 guests.
The nft-only suspend gap remains measured; this is not live host qualification.

The next candidate adds four fresh diskless/no-external-NIC guests: an open
negative control, missing policy, rejected installation, and closed startup.
A fixed non-expiring inet TCP/443 drop policy is installed and semantically
read back while host0 remains administratively DOWN. Only successful readback
allows the first link-up. Missing policy and a real invalid nft transaction
must retain DOWN and an empty ruleset. Closed startup requires the first new
IPv4/IPv6 TCP/443 probes denied and both TCP/22 echo controls reachable, with
unchanged rule identity and complete guest/host-side cleanup. No runtime policy
is installed on the CI host. Local policy/evidence/packet/VM tests: 19 passed.
First CI job 114233949136 passed open/missing/invalid guests; the closed guest
stopped before link-up because the verifier assumed interleaved object ordering.
Normalize table/chain grouping while preserving exact per-chain rule order;
add grouped-layout acceptance and reordered-rule rejection tests. No packet
condition is relaxed. Closed guest evidence and final-head CI remain pending;
record final measurements and independent main verification in the PR body.

Scope is this fixed synthetic local TCP path. TCP/22 is an echo listener, not
SSH authentication. No claim of a production allowlist, inbound initiated
traffic qualification, OS service boot ordering, reboot persistence, closed-to-
leased admission, or integration with the TC deadline. These remain separate
next steps before a live proposal. Phase 3 remains incomplete. KEIRIN.JP hold,
training 0, and all activation restrictions remain unchanged.

## Phase 3 resumed: immutable boottime packet deadline — 2026-10-09

Starting main 33967acdefd9ae04530c67151fb79c43d0263af0 has all five independent
push workflows successful (regression 37879521348). No open PR was present.
The existing nft-only suspend gap remains a measured blocker. Add a guest-only
kernel TC deadline based on suspend-inclusive boottime, immutable after loading,
with the loader exited before all packet observations. Preserve the original
diagnostic and require new awake/S3 packet denial, management continuity and
unchanged filter identity. First candidate CI loaded/attached the program but
stopped on a readback schema mismatch: ID/tag are nested under options.prog.
Correct the parser against the observed JSON; local 28 packet/VM/lease tests
pass. Candidate packet evidence is still pending the changed CI. See
SECRET_CUSTODY_SUSPEND_VM_REVIEW.md.
No live host, credential, scheduler or data-source activation occurs. Phase 3
also still requires closed startup and authenticated management qualification.
KEIRIN.JP hold remains active. note's support reply/public API update is recorded
in NOTE_INTEGRATION.md; no new outreach, subscription, save or publication.

## Source acquisition hold — 2026-10-09

Newly reviewed private provider correspondence changes the collection plan.
KEIRIN.JP acquisition is now on hold, including bounded scripts and the JSON
fallback. SOURCE_ACQUISITION_STATUS.md supersedes earlier fetch-next-race
steps. Do not bypass the hold with another transport or endpoint. Original
private evidence is retained, with no training/source-use approval. The earlier
awaiting-reply status is historical, not current.

Before the reply was read, a single header/result pair for the fourth race
was captured and still showed payouts without all finishes. No acquisition
was made after the decision to hold. No new complete result or unique race
was added. Previously reviewed race records remain excluded from learning.

PR #226 is merged at 44f4288cd96e3667cd20e31e661361a27d86a137. Its PR CI
all six and regression28 passed; main-push CI was still running at resume.
Do not treat this document checkpoint as final CI proof; private receipts
carry later status. Common-agent/synthetic development can continue. Seek
documented licensed data provision; other source inquiries remain separate.

## Disqualified crossing intake — 2026-10-09

PR #225 is merged at 62008f14da9a39552548421b027bf1379253dcc7; all six
main-push CI workflows succeeded. The private noon result checkpoint found
three complete result captures: two joined, one blocked by unclassified
disqualification. No fresh source request was needed to diagnose it.

The importer now recognizes exact disqualification with explicit valid crossing
order as a starter, separately from an awarded finish and retirement. Missing
evidence and contradictory rank/withdrawal/retirement remain blocked. The
original crossing value and raw blocks are retained; no rank is fabricated.

Validation: 150 historical tests plus 25 shared preparation tests pass. Saved
12 historical results/four-pair bridge and 12 pre-race cards replay unchanged.
The three noon result pairs now join against their immutable pre-race cards;
technical review covers 27 riders, while preparation excludes all three for
unconfirmed source use and missing source-use evidence. Training stays zero.
Prior observations/quarantine receipts remain unchanged; new derived records
have new hashes and reviews. Private evidence contains exact source receipts.

This checkpoint precedes PR CI/merge. Production, DB writes, continuous external
collection, learning and hosted execution remain OFF. Follow later results
against saved pre cards; await provider replies. Unknown DQ variants, broader
coverage, evaluation periods, note access and suspend-expiry gap remain open.

## Official JSON result capture bridge — 2026-10-09

PR #224 is merged at 293f1aced5b5c68821f5c62fcb986adac1365969; all five
main-push workflows succeeded. No open PRs were present on resume.

Fresh result/card HTML requests returned HTTP 500/EC0500E, while the public
schedule and page JavaScript remained readable. The schedule selection token
was unchanged. Inspection of the page's own controllers established its GET
JSJ001 header / JSJ012 result route. Both returned HTTP 200. The HTML failure's
server-side cause is unknown; no claim of repair, login or access bypass.

Added offline paired-JSON intake with independent byte/receipt checks, closed
request types/endpoint/query, equal selection tokens, header/scope matching,
chronology and publication checks. Normalization and pre-race joining reuse
existing HTML roster/status/tie/payout and review boundaries. Raw JSON blocks,
original capture hashes and scoped receipts are retained; no HTML is fabricated.
The composite source hash is explicitly labeled. See HISTORICAL_OFFICIAL_DETAIL.md.

Validation: 11 JSON tests, 133 existing historical tests and 25 agent preparation
tests pass. Saved 12-race HTML observations and the four-pair bridge are unchanged.
The first live 1R JSON capture was unpublished; the next contained payouts but
no finish rows and was correctly rejected as result_not_published. Private
receipts retain those changing states. Later capture outcomes belong in the
private follow-up receipt, not an assumed result at this commit checkpoint.

PR/CI/merge remain pending at this source checkpoint. Production, DB writes,
automatic collection, learning and hosted execution remain OFF. No approval or
training follows merely from obtaining official JSON. Source replies, continuous
coverage, note access and BLOCKED_SUSPEND_EXPIRY_GAP remain unresolved.

## Shared preparation stage accounting — 2026-10-09

PR #223 is merged at d7b03860c59fc0b97d8929b61a146241d5707624; all six
independent main-push workflows succeeded. No open PRs were present on resume.

Preparation receipts previously showed only records that reached preparation,
so upstream exclusions were invisible. The shared adapter now derives stage
entry counts from hash-checked arrays and reports converted, quarantined,
detail-quarantined and orphan entries separately from partitioned/excluded
preparation records. Missing optional arrays remain unknown; malformed arrays
block. Producer summary counters are not authoritative, overlapping stages are
not summed into a unique-race total, and private identifiers/reasons stay out of
receipt/activity data. Blocked runs do not claim completed accounting.

Persisted preparation bytes and task fingerprints are unchanged. A completed
resume returns counts without repeating the action or rewriting the report.
25 preparation tests and 133 historical tests pass. Saved four-pair evidence
produced three converted / one upstream quarantine / three preparation-excluded
/ zero partitioned records; a second invocation executed no action and preserved
the output bytes and modification time. The diagnostic used empty reviews and
existing diagnostic split dates; no evaluation period or approval was adopted.

PR/CI/merge are pending at this source checkpoint; consult the PR and private
receipt for final status. No new races or real training. Source replies, later
results, continuous coverage, note access and BLOCKED_SUSPEND_EXPIRY_GAP remain
unresolved. Production, DB writes, collection, learning and hosted execution OFF.

## Result-state consistency — 2026-10-09

PR #222 is merged at dca016068932d00bc6edd9c25c9f3d9d6e45bfcd; all six
independent main-push workflows succeeded. No open PRs were present on resume.

The detail importer accepted a finish rank together with an explicit retirement,
and accepted withdrawal and retirement on the same row. Such contradictions
could supply a confirmed starter count; ranked retirement could reach the
unapproved single-label review bridge. Blank status objects also concealed an
unclassified missing rank. Six synthetic tests reproduced 12 failing subcases.

The importer now flags those contradictions, leaves the confirmed starter count
unknown, and retains original fields. The bridge quarantines contradictory
captures via its existing issue gate. Ranked blank placeholders and separate
unranked withdrawals/retirements stay valid; unknown statuses are not interpreted.

Validation: 133 historical tests and 19 agent preparation tests pass. The saved
12-result replay, four-pair bridge and separate venue reconciliation are unchanged.
No new races, source approvals or real training resulted. PR/CI/merge are pending
at this source checkpoint; consult the PR and private receipt for final status.
Source replies, later results, continuous coverage, multilabel learning, note
access and BLOCKED_SUSPEND_EXPIRY_GAP remain separate unresolved work. Production,
DB writes, automatic collection, learning and hosted execution remain OFF.

## Tied finish/payout consistency — 2026-10-09

PR #220 is merged at ec63bc6ba7a88af53752eba82890786bf109a070; all five
independent main-push workflows succeeded. The pending checkpoint below is
superseded. There were no open PRs when this increment began.

Review found that the detail importer bypassed finish/payout reconciliation
whenever any repeated rank existed. Consistent prefixes across the two payout
tables alone could admit missing tied combinations, incorrect third-place cars,
or a wrong winner when a tie existed only below third place. Synthetic cases
reproduced nine failing assertions before the fix.

The importer now checks both ordered payout sets against bounded prefixes of
all observed competition-rank groups. Missing/extra/wrong combinations and
nonstandard rank gaps are flagged while retaining raw evidence. No payout amount
or training label is invented. See HISTORICAL_OFFICIAL_DETAIL.md for limits.

Local validation: 127 historical tests and 19 shared preparation tests passed.
The saved 12-race detailed-result replay, four-pair bridge and separate venue
reconciliation remain identical to the saved outputs; original bytes were not
changed. The bridge still has three unapproved records and one tied quarantine.
This is improved validation of existing observations, not new races or training.

This commit checkpoint precedes its PR/CI/merge; the PR and private receipt hold
final status. Source-use replies, continuous coverage, multilabel learning,
note editor access and BLOCKED_SUSPEND_EXPIRY_GAP remain unresolved. Production,
DB writes, hosted execution, automatic collection and learning remain OFF.

## Repeated interruption recovery follow-up — 2026-10-09

Verified base: PR #219 merged at 5aa4de7001108ef8c4f360328771a0908434f9e0.
All five PR and independent main workflows passed, including 28 regression jobs
on each side. This supersedes the pending CI checkpoint below.

Replayed the separately saved follow-up against current main. Its expanded tests
reproduced the second-interruption failure and acceptance of malformed attempt
counts before the fix (19 tests: four failures and two errors, including subcases).
The follow-up accepts only the launcher's exact saved reconciliation in pending
or running state, checks original report bytes again, and completes without a
new action or reconciliation. It rejects malformed attempt counts before the
legacy decoder can coerce them. Ordinary shared-runner decoding is unchanged.

After applying the saved implementation, all 19 preparation tests and eight
shared-core tests passed. Cases cover repeated interruption, output corruption,
missing/unrelated reconciliation, duplicate records, invalid counts and action
non-replay. This is scoped local recovery verification, not host qualification
or live training. Private reports and evidence remain outside this repository.

The earlier push-authorization blocker was resolved by the user's instruction;
GitHub connector delivery is used because terminal git push has no credentials.
CI/merge for this follow-up is pending at this commit checkpoint; consult its PR
and private receipt for the final result. Source-use replies, note editor access
and BLOCKED_SUSPEND_EXPIRY_GAP remain separate unresolved work. Production, DB
writes, hosted execution, autonomous collection and learning remain OFF.

## Verified local preparation recovery — 2026-10-09

Verified base: main 13940dcd7f689be501e78697d821997d95daea21 (PR #218).
A saved preparation report could survive interruption before its artifact/state
commit, leaving explicit reconciliation to a manual caller. The new opt-in
`--reconcile-verified-output` checks the exact task fingerprint, original input
hashes, chronology boundaries, sole interrupted step and recomputed report bytes
under the task lock, then restores the artifact record without rerunning the
preparation action. Default resume still blocks ambiguous interruption. Missing,
changed, symlink or unrelated failure evidence remains blocked. See
HISTORICAL_AGENT_PREPARATION.md for scope and caller storage assumptions.

Local tests: 15 preparation tests (five added recovery cases with rejection
subcases) and eight shared-core tests passed. A separate private diagnostic run
using the existing three technically reviewed records was intentionally stopped
after report creation. Ordinary resume blocked; CLI explicit recovery and its
repeat both completed with zero action replays and unchanged output bytes/mtime.
Original inputs and original completed run were preserved. All three remain
excluded for source-use evidence; real training is still zero. No new races.

A scoped mailbox search now succeeded and returned the note acknowledgement only;
no substantive reply was found in that query. This does not prove absence across
all mail. Three inquiries have been sent, including the official data-use contact;
no source-use permission is established. Private correspondence stays outside git.

This change does not resolve note editor loading or BLOCKED_SUSPEND_EXPIRY_GAP.
The latter still needs a suspend-inclusive kernel deadline or closed boundary;
ordinary userspace recovery cannot establish packet revocation during resume.
No unchanged host experiment was retried. Hosted execution, production prediction,
DB writes, automatic collection and learning remain OFF. Remote CI and merge are
pending at this commit checkpoint; consult this change's PR for their final state.
Next: qualify host suspend boundary separately, diagnose note using new support
evidence, join later results to immutable pre-race captures and resolve source-use.

## Nine-rider pre-race intake and scoped technical review — 2026-10-08

PR #217 is merged at 23bf9689bcbe7d053c813b057c73b35a011863e7.
Its six main workflows and 28 regression jobs passed. This supersedes the
pending checkpoint below; the private receipt preserves exact run identities.

A bounded next-day capture saved all 12 Yahiko races for 2026-10-09 before
start: 108 listed rider rows, all nine-rider fields. Each page passed the existing
strict capture/date/venue/race/roster checks. One pre-race roster contains an
additional-entry note, retained for later result reconciliation. Results are
not available in these pre-race captures. Unique observed races increase from
329 to 341; these are observations, not approved training examples or predictions.

The prior navigation mismatch is explained by the official page handlers:
the promotion's prmEnc is used by its result button, whereas its next-day
vote button uses venue/date. Do not treat that result token as a next-day card
link. The working read-only route is tomorrow's JSJ057 schedule followed by
its venue encPrm and returned per-race encParaR values. No login or vote action
was performed. Validate actual page identity after every navigation. This fixes
the operator's route selection; it does not claim a server-side repair.

Three existing pre/result records (20 active rows) received a scoped technical
review against exact saved bytes: capture chronology, identity, roster notes,
style and score mappings. The reviewed derivatives preserve the original hashes;
unknown S/H/B windows remain unmapped. Two additional entrants were already on
the saved pre-race roster; one withdrawal was known before start and confirmed
in the result. No source-use approval was created. Shared-agent preparation
now excludes these three only for unconfirmed training use / missing source-use
evidence, with zero learning runs. Completed resume executes no steps and checks
the saved report again. Continuous train/validation/test coverage is still absent;
removing record-level blockers alone would not establish adequate evaluation.

This increment changes handoff documentation only; application code and production,
DB, autonomous collection/learning and hosted gates remain unchanged/OFF. Private
captures, reviews, source references and replay scripts are saved separately.
CI/merge for this documentation checkpoint is pending here; consult its PR and
private receipt for final status. Next: preserve new pre-race originals, join later
results without changing features, resolve source-use scope, and extend continuous
coverage. note and BLOCKED_SUSPEND_EXPIRY_GAP remain unresolved; no unchanged retries.

## Completed venue results and pre/result review bridge — 2026-10-08

Verified base: PR #216 is merged at 344c5fb3ed6ff14a51b528cf8aa07f606ed1d047.
Its private receipt records all six main workflows and 28 regression jobs
successful; the remote main ref and merged PR were checked again this session.
This supersedes its pending checkpoint below.

New private captures at 22:00–22:02 JST fill 8–12R. All 12 detailed results
(84 listed rows, 82 confirmed starters, 80 ranked finishers) match the separate
venue payout list and the original paper identities. Earlier 1–7R payouts are
unchanged. 10R has two first-place finishers and two ordered outcomes; both are
retained. 12R confirms the withdrawal seen on the saved pre-race card. This adds
five detailed results to existing races, not five new unique observations;
cumulative unique observations remain 329.

`ml.historical_official_records` replays saved pre/result HTML and receipts,
checks cross-capture identity and every observed start, and emits hash-bound
historical review records accepted by the shared preparation runner. Only
observed style/score are mapped; unknown metric windows stay raw. A pre-known
withdrawal can be excluded from the candidate population without altering the
source; a later-only withdrawal, unknown classification or tied rank blocks the
single-label bridge. Private raw results, including all tied payouts, are retained.
See HISTORICAL_OFFICIAL_RECORDS.md.

Four saved pre-race cards produced three unapproved records (20 active rows),
with 10R quarantined for the separate multilabel contract. These are an alternate
representation of the same races; do not concatenate them with earlier paper
candidates as additional independent examples. Shared-agent preparation excludes
all three: source-use/definition/roster and final-record reviews are outstanding.
There are zero real training runs. Fixed, continuous evaluation data are still
needed. Historical tests: 120 passed, including 14 new bridge tests; shared-agent
preparation tests: 10 passed. This increment's remote CI/merge is pending at this
commit checkpoint; consult the PR and private implementation receipt.

The reply search failed with Gmail RATE_LIMIT_EXCEEDED/PERMISSION_DENIED. This
is not evidence of no reply. Do not repeat the unchanged request or send a new
inquiry. note editor access and BLOCKED_SUSPEND_EXPIRY_GAP remain unresolved and
were not retested here. Production, application DB writes, scheduled collection,
autonomous learning and hosted activation remain OFF. Next: resolve source-use
and feature definitions, review exact records, extend dated coverage and add a
proper multilabel contract while preserving the general-agent/note work.

## Official detailed intake and working access route — 2026-10-08

Verified base: PR #215 merge 87dfca07ff9a9562c297d4862b5cb8bf2f5e7719,
with all six PR workflows, all six main-push workflows and 28 regression jobs
in each successful. This supersedes its earlier pending checkpoint below.

The private venue-list capture at 18:31:58 JST joins 1–7R ordered results;
the preceding five values are unchanged. A later official top-page route
returned detailed pages with HTTP 200, using the same public race tokens that
had previously failed. The earlier EC0500E server-side cause remains unknown;
working access at this observation time is not a permanent service repair.

New offline `ml.historical_official_detail` retains entire header/card/result
blocks, pins capture bytes and identity, reconciles rider IDs, rejects late
pre-race captures, and preserves non-finishers and partial refunds. It supports
3–9 listed riders and separates listed riders, finishers and confirmed starters.
No unknown metric windows are silently mapped into training features.
See HISTORICAL_OFFICIAL_DETAIL.md.

Privately saved: seven detailed results (49 listed rows), plus four pre-race
cards for 9–12R (28 rows, all before listed starts). 1R includes a withdrawal
and partial refund; 2R includes a fall retirement; 12R's new pre-race card
includes a withdrawal. Earlier paper bytes remain unchanged. Later observations
must not be used to rewrite what was known at the earlier paper capture time.
These enrich existing races; cumulative unique observations remain 329.

Local historical tests: 106 passed including 15 new detail tests; shared-agent
historical preparation: 10 passed. This increment's remote CI/merge is pending
at this commit checkpoint; its PR and private implementation receipt carry
final status. Learning-eligible records and actual training runs remain zero.
Source-use/feature definitions, final-record reviews and continuous evaluation
coverage are unfinished. These captures are not paired prediction records.

note/provider reply search still found only note's prior acknowledgement in
its stated query scope. No new outgoing messages. The note editor issue and
BLOCKED_SUSPEND_EXPIRY_GAP are not fixed or revalidated by these data tests.
Production, application DB writes, automatic external collection and autonomous
learning remain OFF. No completion percentage or delivery date is inferred.

## Official source capture and offline result reconciliation — 2026-10-08

Verified base: PR #214 is merged at
08e3b82020e40f27d114aee37f7e53e8e814ce54. Its six independent main-push
workflows and all 28 regression jobs passed. This supersedes the pending
PR214 checkpoint below.

A separate private capture saved the current official program at 15:43:11 JST,
before the first listed start of 15:45: 12 races and 84 rider rows. Ten brief
rider-comment facts, one stated follow intention and bank dimensions were also
retained. These are pre-race source observations, not paired prediction records.
Cumulative unique observations are 329; no new races are counted by this join.

The official result list saved at 17:17:03 JST contains ordered payouts for
races 1–4 and blank cells for 5–12. The new offline importer pins source and
snapshot hashes, checks table shape/date/roster/chronology, excludes duplicate
mobile tables, preserves multiple outcomes, and quarantines ambiguous rows.
It produces separate result observations and unapproved historical review
candidates without changing the pre-race bytes. See HISTORICAL_OFFICIAL_RESULTS.md.

Applied privately: four joined summaries, eight pending at that capture time.
Existing preparation excludes all four candidates (0/0/0); full results/status,
style, source-use and final-record reviews remain incomplete. Local historical
checks: 91 passed, including 12 new tests. This increment's remote CI/merge
is pending at this checkpoint; consult its PR and private receipt for final state.

The linked KEIRIN.JP detail lookup returned HTTP 500. A separate GET reading
path returned the same status; the cause and repair are unverified. The source
list remains accessible. Do not infer full finish orders or retry unchanged
failed lookups. Next: confirm a working official detail path or subsequent
program results, reconcile result/status changes, and extend continuous input
coverage and reviewed training preparation. No background collector is running.

note's editor issue, provider inquiry and BLOCKED_SUSPEND_EXPIRY_GAP remain open.
No new messages or purchases; production, application DB writes, autonomous
learning and automatic collection remain OFF. Learning-eligible races and real
training runs remain zero. No completion percentage or delivery date inferred.

## Detailed historical intake alongside existing work — 2026-10-08

Verified base is PR #213 merge c36f9c5b5cf9f4f1938d31ce1b8543f7fd8fd151.
The user's new instruction explicitly asks for collection improvements alongside
existing work. This supersedes the earlier note-first pause for independent
collection development; it does not resolve the note failure or authorize
unbounded external collection, purchases, publication or messages.

`ml.historical_details` adds hash-pinned, lossless four-table CSV intake,
field-level coverage, duplicate/conflict handling and an explicit missing-data
backlog. It retains all 55 source column positions across the four schemas,
including unexpected columns, and connects eligible candidates to the existing
strict review converter. A separate hash-bound rate-feature bridge requires
confirmed definitions/window evidence; it never treats download time as a
historical cutoff. See HISTORICAL_DETAIL_COLLECTION.md for usage and limits.

Applied to the existing 11 files: 301 races, 6,451 unique rows, no conflicting
keys; 211 have all four tables, three of those have missing entrant cars. The
other 90 lack entrants. Converted review records remain 208. All 1,408 H cells
are blank; 90 race weather/wind values are absent in the 2026 sample. This is
more detailed organization/validation, not new external collection. Cumulative
unique observations 317; training-eligible 0; real-data training runs 0.

Local historical tests and existing shared-agent preparation tests pass.
This increment's remote PR/CI/merge is pending at this checkpoint; consult its
PR and private receipt for final status. No existing learner or production
feature contract is changed. Automatic collection, autonomous learning,
production predictions, application DB writes and hosted activation remain OFF.

note support has acknowledged an editor-loading inquiry; the root cause and
repair are unverified. Do not request repeated phone/login checks. The provider
use/time inquiry also remains awaiting a substantive reply. Keep both threads
and BLOCKED_SUSPEND_EXPIRY_GAP open. Next collection work is source/window
qualification and continuous-period acquisition, followed by reviewed features
and frozen evaluation partitions; do not report all details collected or a
completion percentage based on file/PR counts.

## Shared-agent historical preparation — 2026-10-08

PR #212 is merged at 734272e4a07c96c331cec1c3b31e995cb8e104c9,
tree 8cec984a3eb919cd52c7aa9374dddf6b06004d7a. Its six PR workflows
and six independent main-push workflows passed, with 28/28 regression jobs
on each. The previous private progress report is version 8.

The authenticated note home loaded this morning. Following its current new-post
link still left the editor on a loading indicator; no repeated login, new draft,
save or publication occurred. The cause remains unknown. Focused mailbox searches
for the provider/topic and note sender found no matching reply; do not generalize
this to all possible reply locations. Browser integration remains incomplete.

The new historical_preparation launcher connects existing reviewed-record
preparation to the shared AgentRunner and FileStateStore. It pins input hashes,
paths and explicit diagnostic boundaries, verifies persisted report bytes and
records a private activity ledger. Identical completed resumes do not repeat the
action; changed input, review, boundary, output or an interrupted attempt stops
for review. No train, fetch, DB, note write or scheduler action is exposed.
See HISTORICAL_AGENT_PREPARATION.md for usage and remaining work.

Applied to the same 208 converted records with empty reviews: the diagnostic
completed and excluded all 208, with train/validation/test 0/0/0. A second call
executed no steps and verified the same output hash. This is real-data execution
of preparation, not real-data training. Cumulative unique observations remain
317, training-eligible races 0, real training runs 0. The earlier 93 upstream
quarantines are unchanged. Private artifacts remain outside git.

Local verification: 10 new agent-preparation tests, 67 historical tests, 8 core
tests, 3 persistence-redaction tests and existing web/safety regression passed.
Current increment PR/merge/independent-main receipts must be read from its PR
and private progress record. No completion percentage or delivery date inferred.

Next: resolve note editor access using new evidence before binding a live host;
read any provider reply and attach supported use/time evidence to exact records;
review final hashes and establish continuous, fixed-period evaluation data.
BLOCKED_SUSPEND_EXPIRY_GAP remains unresolved. Production, DB writes, automatic
collection, autonomous learning and hosted runtime activation remain OFF.

## note draft adapter and historical review conversion — 2026-10-07

Current main before this increment is PR #211 merge
9ba315fa244df7352fa2a4b8e755d241cca4d8ed. All six independent main-push
workflows passed (UI 37602735819, ML 37602735943, AWS 37602735992,
PostgreSQL 37602735827, regression 37602735835 with 28/28 jobs,
runtime 37602735718). This supersedes earlier pending-PR211 receipts below.

A previously authorized provider inquiry has now been sent; the Work browser
showed completion. The reply is not yet verified. The private progress report
holds the exact message and screenshot. Earlier “unsent” statements are history.

The Work browser retained note authentication in a fresh tab. The article
editor remained on a loading indicator after one reload, so private draft
save/reopen is NOT verified. NOTE_INTEGRATION.md records this boundary.
The new NoteDraftAdapter handles existing private drafts through an injected
host backend: expected account/content, separate permissions, persisted readback,
and blocked ambiguous saves. It has no live browser backend by default and no
publication/message action. Synthetic tests are not standalone live integration.

ml.historical_records replays normalization from retained raw rows before mapping
entrant candidates to the historical training/review schema. Candidate lineage,
provider rider IDs, missing H/timestamps, DNS/DNF/DSQ, dead heat and refunds are
preserved. Final record hashes differ from upstream candidates; old reviews do
not transfer. The converter never creates use/time evidence or training approval.

Applied offline to the same 301 races: 208 converted review records (206 ordinary,
1 dead heat, 1 full refund), 93 upstream quarantines. Counts of 7/6/5 riders are
157/33/18. Existing training preparation with empty reviews excludes all 208;
train/validation/test remain 0/0/0. Diagnostic boundaries are not evaluation
partitions. Cumulative unique observations remain 317; real-data training 0.
Local tests: 67 historical tests and 8 note-adapter tests, including 17 new tests.
Current increment CI/merge receipts must be read from its PR/private progress.

Next: bind and verify a real authorized note browser backend only after editor
access works; review the provider reply; add supported source/time evidence to
converted records and review their final hashes; establish continuous coverage
and fixed chronological evaluation. General-agent BLOCKED_SUSPEND_EXPIRY_GAP
remains unresolved and was not retested. Production, DB writes, automatic
collection, autonomous learning and runtime activation remain OFF.

## Offline entrant import — 2026-10-07

This checkpoint supersedes the earlier pending-main receipt: PR #210 is merged
at 908952a046fd6c8d3b66e70ba1cf7c5d06f12847. All five applicable main-push
workflows passed: UI 37599957354, runtime 37599957359, PostgreSQL 37599957343,
AWS 37599957399, regression 37599957355 (28/28 jobs). ML was path-filtered.

`ml.historical_entrants` now imports private KeirinDB entrant CSVs into existing
payout candidates without network access. It joins exact race/car/provider ID,
cross-checks rider names and withdrawal status, retains raw rows and hashes,
and maps only Points, style, S, H and B. Blank numeric values remain missing.
It does not use current rider-master values or unreviewed aggregate-rate columns.
Missing cars are not reconstructed from results. Each changed record has a new
hash linked to its original payout candidate; old reviews cannot carry over.

Applied to the already acquired sample: 301 races, 1,408 entrant rows supplied;
208 races / 1,387 rider rows matched (2024: 96 / 659; 2025: 112 / 728).
Three races remain quarantined because withdrawn entrants have no car number;
90 races have no entrant file in the 2026 sample. All 1,387 matched H values
remain missing, while score/S/B are present. This is an input conversion result,
not a new collection count, independent source verification or training approval.
Observed matched rosters contain 5, 6 and 7 riders; synthetic coverage also
checks 3 and 9. No nine-rider real-data import is claimed in this sample.

Local historical tests: 58 passed, including 10 new entrant-import tests.
The private CLI report and evidence archive preserve reproducible inputs.
This implementation's PR/CI/merge is not complete at this document checkpoint;
read its PR and the private progress report for final receipts.

Primary provider research distinguishes a full-year KeirinDB CSV offer from
its three isolated-day free samples, a current-rider-only CSV, a third-party
Kdreams collection repository, and a vendor's betting APIs. None of these
checks established a newly qualified continuous training dataset. The private
source decision record retains URLs, missing evidence and an unsent inquiry.
No purchase or provider message was made. Next acquisition decision: confirm
historical card timing and the intended model-training use of an existing CSV
provider before paying or scaling intake; commercial use is a separate scope.

Unique historical observations remain 317; training-approved races 0;
real-data training runs 0. Feature/result-availability times are still unknown.
Conversion output still needs source/time evidence and a dedicated historical
review before training. General-agent BLOCKED_SUSPEND_EXPIRY_GAP was not
retested or resolved. Production, DB writes, automatic collection, autonomous
learning and runtime activation remain OFF. No overall percentage is asserted.

## Archived-card corroboration and source-use review — 2026-10-07

This checkpoint supersedes earlier current-status text. PR #209 is merged at
8e82619d40abcd331cef7b7e8ae9d478e66729f9, tree
ef78448fb990816fd77c4e7e371dac37f6dc2869. Five applicable PR workflows passed
(regression 28/28). Independent main-push checks also passed: AWS 37597251455,
PostgreSQL 37597251508, UI 37597251451, regression 37597251410 (28/28),
and runtime 37597251423. ML was not triggered by that documentation-only change.

Cumulative unique historical observations remain 317; this increment adds no
new races. Three archived race cards corroborate all 21 existing paper scores
and all 21 paper BK/archive B values. They also supply observed style and S
values for those 21 rows. Matching uses the same race/car plus name, age,
prefecture and term; it does not establish stable cross-race rider identities.
No stable IDs were resolved or current rider-master features imported.
Value agreement is not proof of independent upstream sources or of pre-race
publication. Feature/result-availability timestamps remain unset.

The private source-qualification report records source-specific scope:
KeirinDB explicitly describes AI-assisted analysis and prediction-logic use;
that statement is not treated as an explicit model-training, automated-fetch
or commercial-service license. Kdreams' site policy contains restrictions on
private use and unauthorized copying; its cards are not accepted as a training
source, and no further bulk collection is started. KEIRIN.JP's own policy does
not authorize another provider. Legal applicability has not been adjudicated.
No paid purchase, provider message or permission request was sent.

Existing training preparation was run on the three enriched candidates, with
no fabricated reviews: 0 train / 0 validation / 0 test; all remain excluded.
These diagnostic dates are not an adopted evaluation partition. Numeric H and
other optional fields may remain missing; stable IDs are needed specifically
for rider-history joins. Do not turn every enrichment into a universal gate.

Private artifacts: keirin_source_qualification_2026-10-07.json and
keirin_source_qualification_evidence_2026-10-07.zip. The bundle retains factual
extracts, original HTML hashes, the prior intake and an offline reconciliation
script; full archive HTML and editorial content are not bundled. The prior
paper-intake artifact remains an unchanged baseline. The progress JSON records
this new scope and final PR/CI receipts. Current documentation CI/merge is
pending here; read its PR or the private progress file for final receipts.

Next: prioritize a source that can substantiate learning-use scope and historical
input/result timing, rather than scaling a source that is not qualified. Keep
the separate general-agent work visible: BLOCKED_SUSPEND_EXPIRY_GAP was neither
retested nor resolved. No new product implementation in this increment.
Historical training-approved races 0; real-data training runs 0; accuracy and
return on stakes unmeasured. Production, DB writes, automatic collection,
autonomous learning and runtime activation remain OFF. No overall completion
percentage or deadline is established.

## Dated historical program intake — 2026-10-07

This checkpoint supersedes older current-status statements below. PR #208 is
merged at main 3d22089d2fe59b550709154cc1d3a1aac6a13b98,
tree 3e677359ffd5fd2d16453a8918301c2fe726fdfa. All six PR workflows passed;
independent main-push runs also passed: regression 37591972830 (28/28 jobs),
runtime 37591972844, PostgreSQL 37591972850, UI 37591972829,
ML 37591972919 and AWS 37591972825. Its earlier pending text is historical.

Private intake now contains 317 unique race observations: previous 314 plus
three bounded race-1 observations from the consecutive 2024-01-29/30/31 meeting.
Three dated official program PDFs (11 pages) were obtained. Only three races and
21 rider rows have been structured; untranscribed races in those PDFs are not
counted. Paper scores/BK, roster and scheduled starts were visually transcribed;
full finish orders and ordered payouts were checked against three result pages.
For two races, the next day's official program also agrees on the full order
and ordered payouts. This does not establish independent upstream data providers.
All originals, private records, SHA-256 hashes and reproduction script stay
outside this public repository.

The PDFs report creation on the preceding day, but that is not proof of public
availability before the race. HTTP modification dates postdate the meeting.
Historical feature and result-availability times remain unset. No stable rider-ID
join was inferred from names; no style/S/H was invented from results. BK is
retained literally, with its model-column mapping awaiting review. Scores/BK
were not independently checked against another archived card. Source automated,
training and commercial-use scope remains unconfirmed.

Existing offline intake and training-preparation code was run on the three new
records: all three remain excluded; train/validation/test counts are 0/0/0.
No new model implementation or real-data training occurred. Diagnostic split
dates are not an adopted evaluation period. Private detail artifact:
keirin_dated_program_intake_2026-10-07.json; raw evidence and reproduction script:
keirin_dated_program_evidence_2026-10-07.zip. The existing private progress JSON
records current counts and, after checks, the final documentation PR receipts.
This documentation increment has not passed CI or merged at this checkpoint;
its final receipts must be read from its PR or that private progress file.

Next: establish source use/time evidence and stable identities for a bounded
continuous period; approve feature mapping before expanding transcription or
training. Do not repeat unchanged failed source URLs or treat PDF metadata as
historical publication evidence. Preserve the separate general-agent goal:
BLOCKED_SUSPEND_EXPIRY_GAP remains unresolved and was not retested in this slice.
Approved historical training races: 0; real-data training runs: 0; accuracy and
return on stakes unmeasured. Production, DB writes, automatic collection,
autonomous learning and runtime activation remain OFF. Counts do not justify an
overall completion percentage or a delivery date.

## Historical payout normalization — 2026-10-07

This checkpoint supersedes older current-status statements below. PR #207 is
merged at main 4a3e18d0f75783d1ecd6d9342087a4a21b637f91,
tree 52b07e8a0bc364020ef4a244ba9dded81f3fb14d. All six PR workflows passed;
independent main-push runs also passed: regression 37588152057 (28/28 jobs),
runtime 37588151938, PostgreSQL 37588152013, UI 37588151987,
ML 37588151978 and AWS 37588152101. Earlier pending statements describe history.

Private intake now contains 314 unique race observations: earlier 13 plus 301 free
KeirinDB samples (2024-01-01: 98; 2025-01-01: 113; 2026-01-01: 90).
These are three individual dates, not complete years. Original downloads and the
source/quality checkpoint are saved privately; no real race data enters this repo.
Source automated/commercial-use scope and historical feature times are unresolved.
The 2026 sample has no entrant table; all 1,408 earlier entrant rows lack H, and the
2026-08-21 rider master has not been joined into earlier features.

Current branch codex/historical-payout-normalization adds ml.historical_payouts.
It preserves raw evidence, hashes and change reasons while accepting only known
ordered-payout date formats that agree with the complete supplied finish order.
Contradictions/unknown formats are quarantined; tied winning orders must be complete.
Refunds require explicit evidence and remain separate from ordinary winning labels.
DNS/DNF/DSQ remain distinct; a nonclassified fault abbreviation is recorded explicitly.
Output is an unapproved normalization candidate, not a training record.

Applied locally to 301 already-downloaded races: 301 internally consistent candidates;
604 payout-row transformations; trifecta outcomes 298 ordinary / 2 dead heats /
1 full refund; one explicit fault-status normalization. Four selected boundary
cases were cross-checked against result/notice pages with scoped, hash-bound evidence
in the private report. This does not verify all 301 records externally or establish
feature timing. No additional race acquisition occurred in this increment.
Local historical checks: 48 synthetic tests passed (15 new); no real-data training.
Current increment CI/merge pending; final receipts belong in its PR and the private
keirin_progress_and_data_quality_2026-10-07.json checkpoint. Do not confuse the prior
PR #207 receipts above with this candidate. The detailed normalization artifact is
keirin_payout_normalization_2026-10-07.json, also outside the public repository.

Next: establish usable point-in-time entry/feature/result evidence over a continuous
period, then review immutable records and freeze chronological evaluation partitions.
Approved real-data training races: 0; real-data training runs: 0; accuracy/ROI unmeasured.
No autonomous collector or learner runs. Production, DB write, external fetch and
runtime activation remain OFF. No overall completion percentage or deadline is
justified by these counts. General-agent blocker BLOCKED_SUSPEND_EXPIRY_GAP remains
unchanged and unqualified; this Keirin increment does not resolve it.

## Result-derived historical form — 2026-10-07

PR #206 is merged at main 2dcebb6dd3b78901ae3d515afa702ac4222564bb,
tree 2c64400069824a928353380eb876f8d1ce3d76c3. All six independent
main-push workflows passed: regression 37585873918, runtime 37585873893,
PostgreSQL 37585873964, UI 37585873906, AWS 37585873924, ML 37585873925.
Its earlier final-head workflows also passed (28 regression jobs). The private
intake snapshot dated 2026-10-07 contains 13 unique factual samples, including
one six-rider race; zero real-data training runs. These are recorded findings,
not new observations in the current slice.

Next implementation on `codex/historical-form-provenance` reconstructs custom
recent form from reviewed earlier results instead of assuming displayed archive
statistics were frozen before a race. It requires namespaced stable rider IDs,
pre-start target entry/cutoff evidence, and result-availability/use/identity
references. It joins identities, not car numbers or fuzzy names. It excludes
future/late/self results, conflicting duplicates and out-of-window races. No
result publication timestamp is inferred from the event date.

DNF/DSQ count in the started-race rate denominator; DNS does not. Mean finish
uses classified finishes only. Dead-heat ranks are retained for these history
features, while dead-heat target labels remain unsupported in training. Missing
history stays missing, with supplied-history coverage and contributing hashes
explicit. These custom window statistics are not claimed to equal an official
published score or complete career record. Candidates still require a separate
review before training; evidence strings do not authenticate source truth.

Historical model input now accepts the four reviewed recent-form fields and
three through nine riders; prospective seven-rider validation is unchanged.
Evaluation reports the test subset for each actual rider count separately.
Local checks: 33 synthetic unit tests passed; a synthetic 18-race form -> training
-> holdout run passed with 8 train / 3 validation / 7 test, including each rider
count from three through nine in test. CI and merge of this follow-up are pending.
No real-data learning, automatic collection, deployment or accuracy improvement
has occurred. The source/use/time/identity evidence for real records remains
unresolved. Next: obtain those inputs through a qualified source and preserve
provenance, then freeze evaluation periods and validate on untouched real data.
Existing suspend-expiry blocker and all production/DB/fetch gates are unchanged.

## Historical training follow-up — 2026-10-07

Added a separate `ml.historical_training` offline path on the development branch.
It requires record-hash-bound operator reviews with source-use, historical-feature
and result-availability evidence references. References are attestations, not an
automatic verification of source permission or truth. Explicit pre-race features
are separate from archived displayed statistics; no historical prediction capture
timestamp is invented. Seven/nine-rider ordinary finishes are supported; dead heats
remain quarantined pending a multi-label contract.

Chronological boundaries are explicit. Complete races stay together and labels
unavailable before the next partition are purged. Training uses train only;
early stopping uses validation; final metrics use the held-out test partition.
Do not repeatedly tune against that test period. This initial path populates
race_score/S/H/B/style only; other shared model features remain missing.

Local evidence: 19 synthetic unit tests pass; a synthetic 12-race mixed 7/9-rider
smoke executed LightGBM training with 8 train / 2 validation / 2 test races and
wrote temporary model artifacts. This demonstrates execution, NOT useful accuracy.
The four existing real samples remain excluded with no reviews and unknown feature
times: zero eligible real records, zero real-data training runs, no new retrieval.
Diagnostic real-sample split dates do not constitute an adopted evaluation period.
Remote main was read as c1cfd45a369c34d4102665579cc4e49842042cff on this turn.
CI workflow now includes these checks; no CI success or main merge claimed here.

Next: substantiate usable historical source access and feature-time evidence,
collect a bounded real dataset, choose and freeze evaluation periods before model
selection, then perform real-data training and evaluate untouched data. There is
no running collector or scheduled training. Production/DB/fetch gates remain OFF.
The separate agent suspend-expiry blocker below is unchanged.

## Planning update — 2026-10-06

Follow-up: historical-source research and offline intake audit implemented locally
on `codex/parallel-keirin-data-plan`. Six candidate sources reviewed to differing
depths; four unique factual sample races saved outside the public repo; all four
quarantined, zero training runs. Seven/nine riders and a dead heat retained.
Eight synthetic intake tests passed. No main merge, CI qualification, bulk crawl,
scheduled collection or model improvement is claimed. See PROSPECTIVE_COLLECTION.md.

Prepared a parallel real-race collection / periodic offline-training plan in
PROSPECTIVE_COLLECTION.md after the user's request. Existing dataset/training/
evaluation code is reusable, but source access, private storage, scheduled worker,
collector integration and operational acceptance remain unresolved. No activation
or actual learning run occurred. Existing production gates remain OFF.

Withdrawn reporting: PR #220–230 as completion forecast; 16.4% as overall progress.
The latter counted completed rows only and ignored partial work and unequal effort.
AGENTS.md now distinguishes implementation, scoped verification and operational
readiness, and requires evidence/assumptions for estimates. This is a planning
branch, not yet a merged implementation. Existing blocker details follow unchanged.

## Current slice: real guest packets across suspend with original kernel guard

Measured result: **BLOCKED_SUSPEND_EXPIRY_GAP**, not suspend qualification. Packet job `111764224176`, regression run `37310432870`, candidate `9846be0336da33b6d2f11781328b59a6a190ed17`, passed all nine experiment records on 2026-10-05 at 21:36:30 JST. The awake control denied all four old/new IPv4/IPv6 qualification probes while all four management probes survived. After actual S3, all four qualification probes still succeeded, without refresh or any preceding post-resume nft read/write. From original installation to first post-resume clock sampling, boottime advanced 11.145488332 seconds; all explicit probes completed within 0.295390938 monotonic seconds of installation. Suspend-window monotonic advanced 0.036644628 seconds and boottime 10.896148706 seconds. Original rules/handles and sentinel remained unchanged; later ordinary awake expiry denied all qualification probes while management survived. Both guest/peer/image/channel/process cleanups completed. Kernel `6.17.0-1022-azure` and QEMU binary/input hashes are in the job and PR #205. This is measured behavior of these exact inputs, not a claim about all kernels or live systems.

Next: preserve BLOCKED and investigate a kernel-enforced deadline or closed boundary that accounts for suspend before a live proposal. Userspace boottime admission alone cannot revoke packets already admitted by the surviving guard. Closed startup ordering and authenticated external management remain unqualified. Final-head five-workflow/28-job and independent main-push integration receipts belong in https://github.com/bzlove178100/-keirin-ai-web/pull/205 ; the measured candidate receipt above does not substitute for them. All activation gates remain OFF.

Updated 2026-10-05 (Asia/Tokyo). PR #204 completed at main `2d8d4718d5fbaa27cfc61bfed8cd333833d6fa7d`, tree `667ed1eddf40cb36ed58c486564bca92aa5ec3ed`. Independent main workflows all succeeded: regression `37305491702` (27/27 jobs), runtime `37305491722` (exact main SHA/push at 20:57:42 JST), UI `37305491697`, AWS `37305491687`, PostgreSQL `37305491681`. VM foundation job `111748042397` passed six records, with actual S3/wakeup and guest reboot/cleanup by 20:52:03 JST. Kernel 6.17.0-1022-azure and QEMU 8.2.2 inputs are hashed in https://github.com/bzlove178100/-keirin-ai-web/pull/204 . Older current-slice headings below are historical.

Add two fresh diskless QEMU guests, one awake and one actual ACPI S3. The emulator still has no NIC/backend, disk, shared filesystem, KVM or live connection. Only internal guest veth/network namespaces carry fixed documentation-address IPv4/IPv6 TCP echo probes. Copy trusted packaged Python/ip/nft/kmod runtime files and read-only matching kernel modules into a private bounded initramfs; use modprobe --show-depends on the host only to discover files, never load host modules. Compile a fixed guest-only PID 1 dispatch after the existing QEMU/opt-in/isolation checks. Keep the original foundation job unchanged and mandatory.

Each guest proves an empty initial ruleset and reachable endpoints before installing any policy: an explicitly OPEN startup negative control, not safe startup. Then install the existing exact eight-second qualification renderer once, retain its handles/rules and unrelated sentinel, and prove old/new qualification and management connections work. The awake case waits ten real seconds and must deny old/new IPv4/IPv6 TCP/443 while old/new TCP/22 echo survives. The S3 case requires real QMP suspend/state/wakeup plus a measured suspend-inclusive clock delta, then probes packets before any post-resume nft read or mutation. Qualification observations must finish before seven monotonic seconds from original installation, with at least ten boottime seconds elapsed. Mixed or late observations are insufficient and fail the experiment.

Report SUSPEND_EXPIRY_OBSERVED only if all four explicit post-resume qualification probes fail. If all four still succeed, report BLOCKED_SUSPEND_EXPIRY_GAP; a green diagnostic CI does not mean the guard qualifies for suspend. Both outcomes must preserve management and unchanged rules/handles, then demonstrate eventual ordinary awake expiry without refresh. Every result keeps activation_allowed=false. No background recovery worker runs in this experiment. Explicit probes are not a packet trace of the kernel's first instruction after resume, and TCP echo is not authenticated SSH.

Local seven packet-evidence/build-isolation + six VM-foundation tests passed (13), packet guest compiled with warnings as errors and refused ordinary host execution. Guest Python syntax checked. First packet CI job `111758239014` stopped before VM launch on standalone nft_counter discovery. The follow-up removes that unsupported standalone-module assumption, requires actual counter-bearing rule creation/readback, and includes dependency stderr on failure; packet/timing gates are unchanged. Second packet job `111759564417` built the image and booted the guest, then PID 1 exited with status 1 before packet evidence. The old parser discarded non-record stderr/console lines, so the underlying Python startup cause is NOT yet known. Preserve a bounded pre-failure console tail (32 lines/4000 characters), with a regression for preceding import errors. Local chroot reproduction was refused by this environment (operation not permitted), not treated as a guest result. The next changed CI must identify the startup cause before any success claim; packet and timing conditions are unchanged. Third job `111761887414` resolved the startup cause: `_Py_HashRandomization_Init` could not obtain random numbers before Python initialization. The initramfs omitted /dev/urandom; add fixed guest character nodes for urandom (1:9) and null (1:3), without copying host entropy or disabling Python hash randomization. These are synthetic experiment runtime inputs, not cryptographic-entropy qualification. Review also found that the peer inherited the original sysfs mount; use socket.if_nameindex() to inspect the actual current network namespace, retaining the exact lo/peer0 and lo/host0 assertions. Kernel sysfs-tagging documentation explains the mount-specific namespace view: https://cdn.kernel.org/doc/html/latest/networking/sysfs-tagging.html . Packet/S3/clock gates remain unchanged; actual packets remain pending. Fourth job `111763147950` now booted Python, loaded modules, isolated the peer, and measured all four unfiltered startup connections successfully. It then stopped at the first nft input transaction because nft -f - opens /dev/stdin, which the minimal image lacked. Add only the fixed guest /dev/stdin -> /proc/self/fd/0 symlink and verify its cpio payload; it resolves in the guest-mounted proc and exposes no host file. No guard was installed in this failed attempt, so it does not measure expiry. The next changed CI must pass the actual rule installation and subsequent packet controls. The corrected candidate subsequently measured the blocking suspend gap above. The new mandatory job requires nine packet experiment records and brings regression to 28 jobs. Require all five final-head workflows/all 28 jobs and independent main-push receipts; record exact observations and any failures/fixes in the PR. No local mocked test is a kernel acceptance receipt.

The measurement requires retaining BLOCKED and investigating a kernel mechanism that includes suspend before any live proposal. A closed-policy-before-link startup implementation, actual external management, privileged tampering, arbitrary endpoints and first live installation remain unqualified. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF. No production host suspend/reboot, packet policy or module change is performed. QEMU package scripts in disposable CI create service metadata; the experiment uses TCG and does not invoke that service or KVM. Do not claim package installation has no service side effects.

## Current slice: diskless disposable guest suspend and boot foundation

Updated 2026-10-05 (Asia/Tokyo). PR #203 completed at main `ea6a025eec07ff415b9c2f5a973ad2f3bb46c963`, tree `3ac83a3ba5ba361361c398cec8fdab8790e1186d`. Independent main workflows all succeeded: regression `37302439098` (26/26 jobs), runtime `37302439121` (exact main SHA/push at 20:29:35 JST), UI `37302439030`, AWS `37302439073`, PostgreSQL `37302439140`. Main lease job `111738110296` passed 65 records; its three clock cases cleaned up at 20:24:08 JST. Exact receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/203 . Older current-slice headings below are historical.

The userspace deadline change does not establish suspend-time kernel packet expiry. Source inspection of the retrieved upstream nf_tables.h found nft_set_elem_expired calling get_jiffies_64, not CLOCK_BOOTTIME. That moving upstream source is not a version-matched proof for the installed Ubuntu kernel, and does not establish its suspend behavior. Version-specific source and real packet observations are still required. Direct retrieval of the v6.17 source failed; do not silently substitute master as a pinned source.

Build a bounded unprivileged QEMU/TCG supervisor and a small static guest PID 1 in a private temporary directory. Reuse the installed disposable CI kernel as read-only input; record kernel/initramfs/QEMU hashes and QEMU version. The fixed command disables default devices, user config, networking, disks and filesystem passthrough; it uses local private serial/QMP sockets and the QEMU syscall sandbox. The guest has only loopback and a fresh private /run. No host service, kernel installation, KVM access, cloud instance, paid resource, live host suspend/reboot or activation is added.

Require actual guest ACPI S3 and QMP SUSPEND/status=suspended before twelve seconds of host elapsed time and system_wakeup/WAKEUP. Guest CLOCK_BOOTTIME must include at least ten seconds more than monotonic, with the same boot ID and private marker retained. Then an actual guest-initiated reboot must produce RESET guest=true, a new boot ID and a fresh empty private /run. A pause, skipped unsupported capability, mocked clock, preserved boot ID or missing event must fail. The host supervisor terminates/reaps only its own QEMU process and removes only its private files; its own boot/network context must remain unchanged. This first slice has no nft policy or recovery worker and cannot qualify packet expiry or fail-closed startup.

Local six supervisor/archive/evidence tests passed, static guest compilation passed with warnings as errors, and ordinary guest-binary execution refused before mounts or power operations. No actual VM was run locally (QEMU/kernel inputs are absent here). CI adds a mandatory separate job, bringing regression to 27 jobs. Require six VM-foundation PASS records, all five final-head workflows/all 27 jobs, then independent main-push receipts before reporting integration. Exact results go in the PR, avoiding documentation-only CI loops.

Next safe slice after this foundation succeeds: add fixed synthetic peer/network packet probes INSIDE the disposable guest, qualify the actual timed-set behavior before/during/after S3 and after boot, and test a deliberately absent startup policy as a negative control. Observe the first post-resume traffic before any userspace guard refresh or recovery action. Real host behavior, privileged guard tampering, external authenticated rescue and first live installation remain unqualified. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF.

## Current slice: suspend-aware admission and recovery deadlines

Updated 2026-10-05 (Asia/Tokyo). PR #202 is complete at main `90e77aca1d320e6abc0918d8e03ea45ca62bccc3`, tree `99ff1fad510bb6c59b951bb8afe1dc7bb17e285a`. Independent main workflows all succeeded: regression `37299274749` (26/26 jobs), runtime `37299274692` (exact main SHA/push verified at 19:59:42 JST), UI `37299274761`, AWS `37299274671`, PostgreSQL `37299274736`. Lease job `111727860100` passed 50 records, including actual worker restart rejection and same-worker SIGSTOP/SIGCONT recovery; cleanup completed at 19:54:10 JST. Exact receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/202 . Older current-slice headings below are historical.

The previous monotonic-only userspace deadlines did not account for host suspend. Bind every preparation/readiness/worker claim to its actual time namespace as well as the existing boot/network/interface context. Guard receipts and worker readiness now carry both original monotonic and CLOCK_BOOTTIME deadlines. Either deadline can expire admission; the worker restores at the earlier remaining duration without rebasing. Sample boottime first when creating deadlines. Missing/non-finite boottime or missing deadline evidence fails closed, with no wall-clock or monotonic fallback. Preserve the original eight-second qualification guard, restoration windows, single-use attempt claim and context/shape checks. All changes remain in the unactivated review/CI fixture.

The existing lease job adds a separately opted-in step with three private network namespaces. Two test children inject only their own boottime observation (+9 seconds for guard expiry and +23 for readiness expiry); this models elapsed suspension and does not change any kernel clock. The third child uses actual unshare --time --fork with unchanged network namespace and zero clock offsets, proving refusal of a different time domain. Each must fail before apply with its specific reason while the parent still accepts the unchanged preparation against its real live worker and guard. Preparation/readiness/claim bytes, guard handles, maintenance policy, unrelated rules and existing/new management connections remain intact; owned resources must all be cleaned. The fixed fault modes are opt-in test entry points, not runtime configuration hooks.

Local 13 lease/clock/restart + 6 shared recovery + 9 context + 7 rescue tests passed (35). One command-free worker test models boottime advancing past its deadline while monotonic remains live and verifies immediate restoration without a fresh sleep. This is control-flow evidence only. CI must retain the existing 50 lease/restart records and add 15 clock-admission records (65 total), all five final-head workflows/all 26 regression jobs, then independent main-push receipts. Record exact final receipts in the PR; do not claim integration from local units alone.

Linux clock semantics: https://cdn.kernel.org/doc/html/latest/core-api/timekeeping.html . Time namespace semantics: https://man7.org/linux/man-pages/man7/time_namespaces.7.html . No actual host suspend, reboot, wall-clock modification or production network change is performed. This userspace admission check does not qualify kernel packet expiry during/after real suspend, or close a suspend between the final check and policy application. A short suspension within both original deadlines is not an unconditional rejection. Actual reboot/persistence, privileged receipt/guard deletion, arbitrary endpoint updates, first live installation and authenticated external rescue remain unqualified. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF.

Next safe slice: inspect the kernel timeout clock and design an isolated disposable-VM suspend/boot qualification with explicit packet probes and fail-closed startup evidence. Keep actual host operations and live activation out of scope until that environment and evidence exist.

## Current slice: single-use recovery attempts across worker restart

Updated 2026-10-05 (Asia/Tokyo). PR #201 is complete at main `0ed57960b86814649c0724e5ee09a8828be49f81`, tree `263f20005d5f03f0cfde07cd8d8fc8e14450899d`. Independent main workflows all succeeded: regression `37295547713` (26/26 jobs), runtime `37295547695` (exact main SHA/push verified at 19:24:41 JST), UI `37295548397`, AWS `37295547918`, PostgreSQL `37295547955`. Guarded rescue job `111715771442` passed 21 records including available/broken paths and complete cleanup. Exact receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/201 . Older current-slice headings below are historical.

Inspection found that worker startup unconditionally replaced readiness and started a new deadline from the current clock. A command-free mocked replay of the actual pre-change worker on this base (same preparation, mocked PIDs 101/202 and clock 100/200) replaced the first deadline 122 with 222. This is local control-flow evidence, NOT an actual systemd restart, host reboot or suspend result. Existing Restart=no and kernel expiry do not make reused worker preparation a single-use record.

Create an exclusive worker.claim in the existing private root-owned attempt directory before publishing readiness. Bind its first PID/start identity to the original attempt/version/boot/netns/interfaces, and require that same claim at controller readiness. Any existing claim, including a partial one left by process loss, consumes the attempt and stops a second worker before deadline creation or readiness replacement. Preserve original no-restart policy, lease duration, recovery windows, context/shape checks and all legacy negative controls. This remains an unactivated CI-only recovery fixture.

The existing lease CI job adds a separate opt-in step with three fresh namespaces: SIGKILL/manual restart before apply; SIGKILL/manual restart after apply/controller death; and SIGSTOP followed by SIGCONT after the original recovery deadline. Restart cases must observe WORKER_ATTEMPT_ALREADY_USED while the original guard is still live, reject stale controller readiness, preserve preparation/readiness/claim bytes, and expire dual-family qualification while management survives. They must not invent successful recovery after losing the worker. The paused same worker must remain stopped through guard expiry, then restore maintenance after its original deadline without rearming. All cases preserve guard handles/unrelated rules and remove owned units/processes/links/tables/claim files. Existing 35 lease records remain mandatory, with 15 new restart/pause records required. Regression remains 26 jobs.

Local 9 lease/restart + 6 shared recovery + 9 context + 7 rescue tests passed (31). Actual systemd/kernel records, all five final-head workflows/all 26 jobs, and independent main-push receipts must be recorded in the PR before reporting integration complete. No actual reboot or host suspend is performed. Linux CLOCK_MONOTONIC stops during system suspend while CLOCK_BOOTTIME includes it; SIGSTOP only stops a process, so this proof cannot qualify host-suspend expiry. See https://cdn.kernel.org/doc/html/latest/core-api/timekeeping.html and https://github.com/systemd/systemd/blob/main/man/systemctl.xml .

Next safe slice: determine and test suspend-aware admission/evidence invalidation without claiming host-level packet expiry from userspace checks. Actual host reboot/persistence/suspend behavior, privileged claim/guard deletion, arbitrary endpoint changes, first live installation and authenticated external rescue remain unqualified. The private /run claim is not reboot-durable storage or protection against another root writer. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF.

## Current slice: restricted rescue under kernel qualification expiry

Updated 2026-10-05 (Asia/Tokyo). PR #200 completed at main `c8824c7f271ab1359d96d738123eb8a5ae68af9f`, tree `c97f66a311045aa3d997f5300ee31deeafdbea66`. Independent main-push workflows all passed: regression `37292654022` (25/25 jobs), runtime `37292654006` (exact main SHA/push), UI `37292654125`, AWS `37292654118`, PostgreSQL `37292654101`. Guarded chrony job `111706473022` passed 26 records and cleaned up at 18:52:15 JST; runtime finished at 18:57:56. Exact receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/200 . Older current-slice headings below are history.

Add explicit `rescue-lease` admission with the existing fixed DHCPv4 qualification tuple and unchanged restricted-rescue policy. Resolve the guarded alias when binding interface identity so BOTH host0 and rescue0 are checked by readiness and the restoring worker. The original eight-second guard is installed before readiness, while the original independent worker retains its 22-second restoration window.

Two mandatory cases run in separate private namespaces: an available static rescue path and that same path deliberately down. Both require real primary administration/DNS/DHCP denial after controller SIGKILL, followed by old/new qualification expiry while candidate rules and the same worker remain. The available path must retain old/new TCP/22; the broken path must remain unusable. The same worker must restore maintenance after expiry without rearming, followed by actual DHCP ACK, cache-flushed A/AAAA upstream queries and primary administration returning in the same private daemons. Wrong rescue source/port remains denied; unrelated rules and guard handles remain unchanged. A successful table restoration cannot override BLOCKED/RESCUE_PATH_UNAVAILABLE. All verdict activation fields remain false; owned teardown removes both guards and all private resources.

Local 7 rescue + 9 context + 6 shared recovery + 6 lease tests passed (28). The new guarded job is separate from the mandatory original available/broken controls, bringing regression to 26 jobs. Actual kernel results, all five final-head workflows/all 26 jobs and independent main-push receipts must be recorded in the PR before reporting integration complete. No local test result is a kernel acceptance receipt.

The second static veth only isolates the tested primary DHCP/DNS/allowance failure. It is not out-of-band from the same kernel/netns/firewall, and TCP echo is not authenticated SSH. No live installer or arbitrary endpoint updates are added. After successful integration, next examine restart/boot/suspend invalidation of prepared qualification and recovery evidence using isolated controls; do not reboot or suspend the live host. Privileged guard tampering, first live installation and external authenticated management remain unqualified. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates stay OFF.

## Current slice: real chrony clients under kernel qualification expiry

Updated 2026-10-05 (Asia/Tokyo). PR #199 is complete at main `b935837609a54306bf33f7ff98a3e835fb229046`, tree `4846850a4832bd551c103b0dc9c4facca0945449`. Independent main workflows all passed: regression `37289811718` (24/24 jobs), runtime `37289811518`, UI `37289811508`, AWS `37289811562`, PostgreSQL `37289811763`. DHCPv6 job `111697308154` passed all existing controls and 16 guarded records. Exact PR/main receipts: https://github.com/bzlove178100/-keirin-ai-web/pull/199 . Older current-slice headings below are history.

Compose the real chrony client lifecycle with the already prepared `time-lease` profile. Each family runs in its own private namespace with a fresh one-shot eight-second guard, unchanged time policy and a 22-second independent restoring worker. No guard is deleted/rearmed between attempts in the same namespace.

Require actual old/new qualification success, controller SIGKILL, then kernel expiry while candidate rules and the same worker remain. After observed expiry, both approved peers must supply two NEW good samples within five seconds to the same capability-free client, with the primary selected, both reachable and existing/new management preserved. The same worker must then restore maintenance without rearming. Existing post-controller (3s), post-restore (two samples/5s), fault preparation (four fresh samples from both peers, one completed burst 4/16, 12s), silent/wrong-origin failover (35s), rejection and approved return (20s) contracts remain unchanged. Guard handles must survive the full failover/rejection/return lifecycle and be removed only by owned teardown.

The legacy fifteen-record unguarded job remains mandatory. One new mandatory guarded job has separate IPv4/IPv6 cases and retains real interleaved/kernel RX/TX evidence, wrong-origin/no-response controls, unapproved-source/TCP denial and complete process/file/link/rule cleanup. Local 15 time + 6 lease + 6 shared recovery + 8 context tests passed (35). This is local evidence only; the PR must record actual guarded kernel results, all five final-head workflows/all 25 regression jobs, and independent main-push receipts before reporting integration complete.

No clock is adjusted: clients and real servers run as nobody with no capabilities, NoNewPrivs and `-x -U`. A same-clock synthetic reference does not establish external UTC accuracy, authenticated NTP/NTS or live-host time qualification. Next after successful integration: guarded restricted-rescue composition. Arbitrary endpoint/address changes, reboot/suspend, privileged guard tampering and first live installation remain unqualified. All runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates remain OFF; no phone/AWS/credential step is needed.

## Current slice: DHCPv6 under kernel qualification expiry

Updated 2026-10-05 (Asia/Tokyo). Resume confirmed PR #198 merged at main `06440cab6f52a63405500ade0f3c286c073d98e2`, tree `b2c14005ee5a4dba1fd720b9d9fcdcf982a3794c`. All independent main-push workflows succeeded: regression `37252751176` (24/24 jobs), runtime `37252751169`, UI `37252751187`, AWS `37252751155`, PostgreSQL `37252751170`. Guarded DNS job `111583551262` succeeded. The prior in-progress main receipt is resolved; older current-slice headings below are historical.

Add explicit `dhcp6-lease` admission using the fixed IPv6 tuple and the unchanged DHCPv6 base policy, including multicast DHCPv6 controls. The existing prepared receipt binds the guard to its attempt/boot/netns/interface, expires after eight seconds, and cannot be refreshed by candidate/maintenance restoration.

The mandatory guarded case reuses the pinned patched CI client in a fresh private namespace after the existing original-defect, patched-lifecycle and unguarded-recovery controls. Require actual old/new qualification success, controller SIGKILL, kernel expiry with candidate rules and the same live 22-second worker still present, then a NEW DHCPv6 Renew after expiry and before restoration. Both inet/netdev DHCPv6 counters and actual address lifetime must increase. Existing/new management must remain usable. The same worker must restore maintenance after expiry without rearming; wrong-source denial, another Renew, Rebind to the allowed alternate DUID and genuine address expiry while the RA route remains all continue under unchanged guard handles. Owned teardown removes guards as well as base tables, links and processes.

Local 4 DHCPv6-recovery + 9 DHCPv6 protocol + 6 shared-recovery + 6 lease + 8 context tests passed (33). No kernel success is inferred from these local tests. Exact final-head CI, guarded PASS records and independent main-push receipts must be recorded in the PR. All five required workflows and all 24 regression jobs must succeed before merge. This adds one mandatory step to the existing client-build job, without duplicating the build or dropping existing controls.

Still unqualified: guarded real chrony client and rescue composition; arbitrary endpoint/address changes; reboot/suspend; privileged guard tampering; first live installation. After successful integration, the next dependency is the real chrony client under the same prepared guard, followed by restricted rescue. The DHCPv6 evidence qualifies only the explicitly patched CI client, not the installed Ubuntu/live-host binary. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates remain OFF. No phone/AWS/credential operation is required or authorized by this slice.

## Current slice: DHCP-delivered DNS under kernel qualification expiry

Updated 2026-10-05 (Asia/Tokyo). PR #197 is merged at main `b9013dc9c8bd144771b418ecdeec0d1d32dad5a6`, tree `88a9ba1fdcee45e8b58645f6eead4d4931a1d5dc`. Independent main workflows all passed: regression `37250898062` (23 jobs), runtime `37250898059` (exact main SHA), UI `37250898068`, AWS `37250898109`, PostgreSQL `37250898048`. Dynamic guard job `111578110677` passed twelve records. Current main and these receipts were rechecked before this slice. Older pending/blocker descriptions are history, not a reason to repeat completed work.

Add explicit `dhcp-dns-lease` admission using the unchanged DHCP-DNS maintenance/candidate policy and existing fixed DHCPv4 guard tuple. Preparation creates and seals the independent eight-second guard; worker readiness and both controller checks require its original bound receipt. No DNS observation grants permission or alters the fixed allowed resolver. Legacy unguarded execution remains a separate mandatory control.

The new mandatory private-netns CI case runs real networkd, resolved and a private bus. After controller SIGKILL it must show old/new qualification success, then kernel expiry with candidate rules still present and the same 22-second worker alive. Cache-flushed A and AAAA queries must still reach the approved upstream. Actual DHCP renewal must deliver an unapproved DNS address without widening access, followed by late PID 1 maintenance restoration without guard rearming. Existing distinct negative transactions, approved return, killed/mixed observations, daemon identity checks and genuine DHCP lease/address/route/DNS expiry continue under the same expired guard. Owned cleanup must remove guards as well as the base tables, links, processes and private files.

Code head `497cb60c6281d20029bf00ced482b3d2e8ee58c9`, tree `2e9701620623998ef9decf58ee8e48817ceb14ba`, regression `37252034264`, guarded DNS job `111581475013`: all 21 records passed at 10:37:20 JST. Kernel-expiry denial with candidate rules, the same live worker, fresh approved A/AAAA queries and management was observed at 10:36:10; actual DHCP unapproved-DNS delivery remained denied at 10:36:17; PID 1 maintenance restoration after expiry passed at 10:36:23. Same-daemon approved return, killed/mixed collectors, genuine DHCP address/route/DNS withdrawal and unchanged guard handles through full cleanup also passed. The legacy DHCP-DNS, dynamic guard and time jobs succeeded. Local 17 related tests passed. No failed attempt or identical rerun occurred. Final-head all-five-workflow/24-job and independent main receipts belong in PR #198: https://github.com/bzlove178100/-keirin-ai-web/pull/198 . All five final workflows and 24 regression jobs must pass before merge; no live apply is authorized.

Still unqualified: guarded DHCPv6, chrony client and rescue composition; arbitrary endpoint changes; reboot/suspend; privileged guard tampering; first live installation. Next dependency slice is DHCPv6 under the same prepared-guard boundary. Runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates remain OFF; no phone/AWS/credential operation is needed.

## Current slice: guarded dynamic dependencies and restoration after expiry

Updated 2026-10-05 (Asia/Tokyo). Start from PR #196 main `43d885ec9b99ab9c74f61260912f39c03a1509ac`, tree `bb58aed189d4ed5299a6b71f47df9c138a0b7a58`. All five independent main-push workflows and 22 regression jobs passed; main regression `37249256571`, runtime `37249256614` (exact main SHA verified at 09:59:08 JST), time `111573315450` (15 records) and lease `111573315341` (35 records). PR #196 is merged; older DRAFT/BLOCKER text below is historical and superseded by its final receipt.

The fixed pure lease renderer now has explicit time, DHCPv4 and IPv6 RA tuple profiles. No caller-supplied addresses or live presets. Shared preparation/admission supports `dhcp4-lease` and `ra6-lease`, preserving their base maintenance/candidate policies while requiring separate fixed guard creation, bound receipt and live lease. Snapshot validation expects the selected profile's fixed rule count and retains handles/policy. Existing legacy profiles and negative controls are unchanged.

A new mandatory private-netns CI job runs real networkd DHCPv4 and IPv6 RA cases with the eight-second kernel guard and 22-second independent worker. Require actual old/new qualification success before expiry; renewal/RA refresh after controller SIGKILL; old/new denial while candidate shape and live worker still remain; dynamic ARP/ND plus existing/new management; subsequent PID 1 maintenance restoration after guard expiry without changing guard handles; then DHCP primary-to-alternate rebind or continued RA refresh followed by genuine route expiry. Owned files/processes/units/links/tables and unrelated-table preservation are checked. Code head `d866cd4d2fc4debab8a96395ea9bea76378231d3`, tree `e3b6e72f3e66fe9101d8843165100cb4dac85adb`, regression `37250237810`, dynamic lease job `111576217409`: all twelve records passed at 10:10:34 JST. IPv4 kernel-expiry denial with ongoing renewal/admin/neighbors was observed at 10:09:10, then the same PID 1 worker restored maintenance at 10:09:24. IPv6 expiry/RA-refresh/admin/ND passed at 10:10:00 and late worker restore at 10:10:08. Post-restore DHCP rebind and IPv6 RA refresh/actual route expiry passed; guard handles were unchanged. Time job `111576217426` passed all fifteen records with actual interleaved/kernel TX evidence at 10:10:02. Existing static guard job also succeeded. Local 3 dynamic-lease + 6 lease + 6 shared + 8 context tests passed (23). Final-head all-five-workflow/23-job acceptance and independent main receipts belong in PR #197: https://github.com/bzlove178100/-keirin-ai-web/pull/197 . No live activation. All five final workflows and 23 jobs must pass before merge.

Scope remains synthetic fixed offered addresses/routes. This does not authorize learning arbitrary endpoints, extend the eight-second lease, qualify DHCPv6/resolved/chrony/rescue composition under the guard, install a live host policy, repair a missing route, authenticate SSH, or handle reboot/suspend/privileged guard tampering. All runtime/provider/credential/prediction/DB/data-fetch/scheduler/report gates remain OFF. Next after this slice is dependency-bound preparation for the remaining profiles; do not repeat completed baseline controls as new progress. Exact code/final/main receipts belong in the PR.

## Chrony peer repair: changed-condition acceptance (2026-10-05)

PR #196 now replaces only healthy approved synthetic NTP responses with four real chronyd 4.5 server processes (one per address/family). Clients request interleaved mode, so actual kernel TX timestamps can be returned on the next exchange. Both client and server run as nobody with no capabilities, NoNewPrivs and `-x -U`; each server binds only its fixed peer address, permits only the fixture host, and uses local stratum 1 without an upstream. Only the private peer namespace permits unprivileged port 123. Same host clock remains a synthetic reference, not external UTC qualification. Silent/wrong-origin fault injection explicitly stops the primary server and hands its socket to the bounded fault peer; return restarts the server, never the client or its sample history. Unapproved-source counters remain real packet-server counters; approved-peer counters now count fault traffic only. EOF/SIGTERM cleanup reaps server children and removes private directories.

The old basic-mode Python server placed T3 before the kernel send; RX repair and burst acquisition could not correct that TX approximation. The exact timing of the historical rejected packets was not captured, so do not claim their per-packet TX delay is proven. The new implementation removes the approximation from healthy measurements and explicitly requires interleaved client reports plus positive server kernel RX/TX counters. Filters, four fresh good samples from both peers, one burst 4/16, twelve-second preparation and original 3/5/35/20-second sample/failover/return deadlines are unchanged.

Code head `b1528692be0385cdbd626377ed857ae09137f052`, tree `e6acff5e906c79c7e5f64dbed9d5f6460422dfc3`, regression `37248568514`: time job `111571313613` passed all fifteen records at 09:44:15 JST. Each of four preparation phases confirmed both clients interleaved and both servers actually using kernel RX/TX. Primary/alternate kernel TX counts: v4 silent 15/15, v4 origin 4/28, v6 silent 16/15, v6 origin 4/29. Lease job `111571313723` passed all 35 records at 09:44:23 JST. Local thirteen time + six lease + six shared + eight context tests passed (33). Final head additionally asserts successful peer exit after cleanup; full final-head and main-push five-workflow/22-job receipts belong in PR #196. Until those receipts pass, no merge or live activation. Previous failed head and diagnosis remain below as history.

Next after integration: qualify guard restoration after expiry and required dynamic network dependencies before any live proposal; boot/suspend/first live install remain unqualified. No phone/AWS/credential steps. All activation gates remain OFF.

## Current slice: require a prepared kernel guard before qualification

Updated: 2026-10-05 (Asia/Tokyo). Base main `a44280a77c1d0d0a44285dae29065c5c67d094c6` is PR #195; its five main workflows and 22 regression jobs succeeded. Previous slice below remains historical evidence.

The new explicit CI-only `time-lease` profile prepares the fixed guard with create-table semantics before starting the independent worker. It seals both table readbacks, retaining handles and all policy fields, and binds the receipt to the attempt/boot/netns/interface context. A conservative eight-second deadline starts before install and never refreshes. Worker readiness publication and both controller readiness checks require a live member, unchanged receipt/snapshot and at least two seconds on that original deadline. Missing, altered, recreated or expired guard stops before candidate mutation. Restore to maintenance deliberately does not require an unexpired guard. Legacy unguarded negative controls remain mandatory.

Local six lease, six shared recovery and eight context tests passed. Code head `aa73bae115810b392a83fcde50057ff840175d3a`, regression `37248051381`, lease job `111569789198` passed all 35 records at 09:36:01 JST: original 20 plus healthy guarded apply/restore and missing/changed/expired/recreated guard refusal with maintenance/admin preservation. PR #196 remains DRAFT and UNMERGED: https://github.com/bzlove178100/-keirin-ai-web/pull/196 . No live installation or activation. All production/runtime/provider/credential/DB/data-fetch/scheduler/report gates remain OFF.

BLOCKER: the same head's existing time job `111569789371` failed IPv4 origin-prime at 09:35:24 JST. Primary good RX rose only 17→20 (required +4); alternate 21→32. Raw primary delay-deviation rejections (`111/111/1101`) rose 12→32; all 52 primary responses were valid, only 20 cumulative good. The single burst 4/16 did not make acquisition reliable. Primary remained selected/reachable, so this is insufficient accepted samples, not transport loss or failed source selection. No unchanged rerun, increased deadline, lowered sample count, disabled filter or merge. Documentation-only CI success must not be interpreted as a timing repair.

Next work: correct the synthetic time peer/transport timing model using the recorded receive/response/delay evidence; verify the cause before choosing a remedy. Preserve the four-good-sample and bounded acquisition contracts, real chrony rejection filters, failover deadlines and original mandatory jobs. Kernel RX timing is already measured; Python response construction and transmit timestamp-to-kernel-send delay remain unqualified. Do not claim this latter hypothesis is proven. A changed-condition time test and all required CI must pass before PR #196 can merge.

The receipt is trusted fixed-installer readback, not a cryptographic attestation or protection against arbitrary root writers. Kernel set expiry remains essential after the last read; checks cannot remove the final-read/commit race. Expiry positivity is checked without assuming a JSON time unit; the admission deadline is the original userspace monotonic bound, not a refreshed kernel countdown. Same-handle privileged member recreation is not qualified. Reboot/suspend, dynamic dependency composition, first live installation and authenticated management access remain open. Exact CI/head/merge receipts will be retained in the PR.


## Current slice: kernel-enforced qualification expiry after process loss

Updated: 2026-10-04 (Asia/Tokyo).

Start from main `e05c17ddaa9fbff58db951db8f509c3fe17b07e3` (PR #194 merged). Final PR and main each passed all five workflows and 21 regression jobs; main regression `37208709975`, runtime `37208709982`, time job `111455278843` (15 records). Main tree `193b044fbe37e2441b135ee7e707f45eda14f8be` matched the accepted PR tree. CI candidate/main dependency repair is complete. The historical chrony rejection cause remains unproven; use raw evidence if it recurs, no blind rerun.

PR #193 showed the remaining final-check race: worker SIGKILL just after readiness plus controller SIGKILL can leave qualification active indefinitely. A new pure review renderer now installs a separate, fixed synthetic inet/netdev guard BEFORE readiness. Timed set membership allows only the fixed IPv4/IPv6 peer TCP/443 while an eight-second kernel lease exists. Every packet is gated, including established TCP. The existing candidate/restore transactions do not own those tables. create-table semantics refuse installation replay while the guards exist; no packet-path update, renewal API, flowtable or broad established bypass is present. The one-minute GC interval intentionally exceeds the lease, so traffic expiry cannot depend on prompt garbage collection.

The new mandatory CI job exercises four separate private namespaces: normal PID 1 restoration; worker death immediately after final readiness followed by candidate apply/controller death; a controller held until AFTER the lease expires before applying; and MAC drift causing worker fail-stop. Require dual-family old/new qualification denial, preserved old/new administration, unchanged unrelated table, unchanged guard handles, refused rearming and two stale candidate replays which cannot reopen access. Existing unguarded negative controls remain mandatory, accurately demonstrating why repeated readiness checks alone are insufficient. The parent observes expiry without mutating nft; its later replay/cleanup is explicitly not recovery.

Local: four lease, eight context, six shared recovery and twelve chrony tests pass (30 total); web/safety regression and diff check clean. Targeted real-kernel acceptance is recorded below. All five workflows and now 22 regression jobs must succeed before merge. Exact head, kernel records and merge/main receipts belong in the PR for this slice.


Initial head `da5c78bb98d1f8f6c5a40a8757d4d33405cdda69`, regression `37209633888`, lease job `111457986532`: normal, worker-loss and delayed-apply each passed all five records. Identity-drift passed baseline/fault but failed old-administration exchange at 23:33:22 JST. Linux v6.17 ARP and ND NETDEV_CHANGEADDR handlers call neigh_changeaddr, which flushes even permanent local neighbors. The old fixture updated only the peer's neighbor mapping. The corrected case now reads back and requires local peer mappings absent after MAC change, then explicitly restores the static local mappings and updates the peer before evaluating expiry. This is deliberate fault-fixture setup, not autonomous recovery; the changed MAC still requires worker context fail-stop. Do not claim the historical log independently captured the flushed neighbor table.

The same initial head's time job `111457986448` failed IPv4 origin-prime at 23:33:12 JST. Raw groups now directly identify delay-deviation rejection (`111/111/1101`): 8 primary, 5 alternate. Diagnostic accepted deltas were primary +4, alternate +7, but the bounded predicate had already timed out; diagnostics are later samples, not proof that the predicate was satisfied before deadline. Kernel RX correction remains valid but does not prevent shared-runner/path/TX jitter or ensure four accepted samples from one-second polling in a fixed window.

Healthy phase preparation now issues exactly one chronyc burst 4/16 to each fixed peer, retaining chrony's good-packet filters, the four-new-good requirement, source preference and twelve-second wait. Require both burst states zero before injecting the fault; normal configured poll 0 and all failover/restoration deadlines remain unchanged. This uses bounded active acquisition instead of assuming every periodic response is accepted. No CI rerun, threshold reduction, filter relaxation, source reset or clock change. Twelve chrony unit tests pass, including command scope/failure and completed-burst requirements. Changed-condition CI must still prove all original fifteen records and all twenty lease records.


Corrected code head `1f4f4bd34ec10200fea82b528a5062163c5fdff3` (tree `e9de122079cad46efdaf799012205c8d8d044350`), regression `37210048538`: lease job `111459213686` passed all twenty records at 23:40:13 JST. The MAC-change readback was actually `[]`, confirming local neighbor removal; explicit static transport restoration let the same changed-MAC worker fail-stop while kernel expiry revoked old/new dual-family qualification. Normal restore, combined worker/controller death, delayed post-expiry apply, no-refresh under traffic, refused rearm and candidate replay denial all passed with existing/new administration preserved. Kernel `6.17.0-1022-azure`. No previous failed job was rerun unchanged.

Time job `111459213731` passed all fifteen records at 23:40:42 JST. Every one of four fresh phases measured +4/+4 accepted samples and burst_finished=true. Raw delay-deviation rejections still occurred (e.g. ten primary rejections cumulatively by IPv6 origin preparation), demonstrating accepted acquisition without disabling rejection. This is acceptance of bounded preparation, not proof that shared-runner timing variance is gone. The remaining full regression jobs were still completing when this targeted evidence was recorded; final-head all-five-workflow/22-job acceptance and merge/main receipts belong in PR #195.

This is an unactivated synthetic guard implementation, not a live firewall installer or permission grant. Expiry revokes the temporary transport allowance; it does not restore table shape, repair a broken management route or establish SSH authentication. Current proof is fixed static peers and the existing dual-family time firewall profile. Other profiles/dynamic DHCP/RA/rescue composition, first live installation, reboot/suspend persistence, same-ifindex reuse and arbitrary privileged guard deletion/rearming remain unqualified. Next qualify the guarded installation/ownership path and required dynamic dependencies before any live proposal. No phone/AWS/SSH/credential operation; all production/runtime/provider/DB/data-fetch/scheduler/report gates stay OFF.

## Completed repair: candidate-bound CI and kernel receive timestamps

Updated: 2026-10-04 (Asia/Tokyo).

At the start of that repair main was `f025ff39bf9d67b4a501b7f214ec95a8aa7bd3e5`; its regression `37192146307` failed the time fixture. PR #194's first diagnostic head `bfec3186dac40d2a3dc35f7f169ceef987f4aca2` passed 21/21 regression jobs but failed runtime `37192519684` because that smoke inspected older main. These failures are retained, not reclassified or rerun unchanged.

The repair changes only the CI smoke entry point: resolve the current Actions run, pin file reads to its SHA, and require actual successful regression/UI workflow results at the same SHA, event, branch, repository, workflow ID and path. It waits at most ten minutes for pending/missing siblings; any completed failure blocks immediately. It does not wait on itself, accept old green main, ignore failure, or return success on timeout. The standalone legacy main-health bridge and strict hosted four-workflow/main-drift verifier are unchanged. On main push, the smoke now waits for that same main commit, removing the earlier timing race. Candidate verification is not a claim that the old main is healthy or that hosted execution is authorized.

The synthetic NTP server now places Linux SO_TIMESTAMPNS_NEW kernel receive time in T2, instead of the time Python returns from recvfrom. This corrects accounting of socket queue/process scheduling time: it belongs to server residence T3-T2, which NTP subtracts from RTT. Reject missing/duplicate/malformed/truncated timestamp controls, without userspace fallback. A CI-only queued-packet control checks the actual receive field against the kernel timestamp after a deliberate 25ms dequeue delay. Existing source preferences, chrony filters, packet validation, fresh-sample requirements, all deadlines and fifteen acceptance records remain unchanged. Raw packet-rejection logs remain enabled. Historical failed-main packet rejection is still not retrospectively proven; successful CI alone cannot establish that all runner jitter is fixed.

Local validation: 10 chrony tests, 9 candidate-CI tests (including real BoundRuntime success/blocking), 4 legacy bridge tests and 15 strict SHA bridge tests pass. Code head `cdbc510f38d7b3b3dc15c49dffd04e20f797446f` (tree `473df2f65a71d842170fb0de787a96f318c29cb3`) passed all five workflows: regression `37207894470` (21/21 jobs), UI `37207894486`, runtime `37207894447`, AWS offline `37207894418`, PostgreSQL `37207894420`. Runtime job `111452832524` completed at 23:09:34 JST and explicitly verified this same SHA using regression/UI run IDs above while old main remained failed. Thus the candidate/main dependency defect is repaired in actual CI. Final documentation-head CI and merge/post-merge receipts are recorded in PR #194. Do not merge unless all applicable workflows succeed. If time acceptance fails again, inspect the new timestamp control and raw measurement evidence before changing anything; no blind retry or threshold relaxation.


Time job `111452833052` passed all fifteen records at 23:05:48 JST. The independent receive-time control measured 0.0251536369 seconds of actual queue residence and confirmed the emitted T2 equals kernel receipt. Fresh accepted deltas (primary, alternate) were IPv4 silent (4,4), IPv4 origin (4,4), IPv6 silent (4,5), IPv6 origin (4,4). Delay-deviation rejections still appeared in raw logs, without failing acceptance. This fixes a measured timestamp-accounting defect; it does not eliminate genuine TX/path jitter or prove the exact rejected subtest in the historical failed main. No filter/deadline change or identical rerun.

No live host, phone, AWS, SSH or credential operation. All runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF. PR #193's worker-loss last-check gap and first live installation remain unqualified; they are separate from this repair.

## Previous diagnostic boundary: chrony per-packet rejection after main failure

Updated: 2026-10-04 (Asia/Tokyo).

PR #193 merged/closed at `f025ff39bf9d67b4a501b7f214ec95a8aa7bd3e5` after final head `22fdb1ae49e189d30228bcf0d273790f009e186c` passed all five workflows and twenty-one regression jobs (`37191720165`). Context job `111405131196` reproduced all fifteen identity/worker-loss records; the last-check gap remains explicitly unqualified. Local/remote main and the tested tree matched after merge.

The later main push regression `37192146307`, time job `111406414809`, FAILED at 18:27:09 JST in IPv4 origin-prime preparation. Primary RX/valid/good changed 20/20/17 to 31/31/20: eleven valid packets but only three new accepted measurements, below the unchanged four-measurement requirement within twelve seconds. Alternate changed 28/28/23 to 40/40/35. Primary remained selected and both sources were reachable with poll 0. Earlier controller/restoration and silent-primary failover assertions passed. Main acceptance is not complete and the successful PR acceptance is not a substitute for this failed later run. No identical rerun was requested.

The last ntpdata NTP tests were all 1; they do not retain every earlier response's rejection bits. Chrony 4.5 official source confirms that accepted-count increments depend on additional maximum-delay, delay-ratio, delay-deviation/quantile and loop tests. The precise failed subtest is still unknown. Shared-runner scheduling and the Python server's userspace receive timestamp are hypotheses, not confirmed causes.

The follow-up adds rawmeasurements logging only inside the existing private unprivileged clockless client, a bounded parser restricted to the two synthetic peers, per-source test-bit-group counts and a sixteen-record tail in preparation/failure evidence. No packet contents, source preference, sampling threshold, poll rate, delay filter or deadline is changed. Eight chrony unit tests pass. Changed-condition CI will retain information absent from the failed main run; success still requires the original fifteen records/four preparations, and a failure must be investigated from actual raw test bits. Do not repeat identical reruns or widen acceptance filters.

The legacy runtime smoke reads the latest completed MAIN CI, so it may correctly block this PR while main regression is failed. Do not relabel that failure as success, bypass the verification step or infer production readiness. Keep any diagnostic PR unmerged unless its applicable integration gate is satisfied. No live/phone/AWS/SSH/credential operation; all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates OFF. First installation and combined worker/controller-loss recovery remain unqualified.

## Previous completed slice: recovery context binding and worker loss at final readiness

Updated: 2026-10-04 (Asia/Tokyo).

PR #192 merged/closed at `25b1bb6b65df1a36fa3a56f927592f9674afbe36`. Final head `d2328adce5dd05f1bfd9d549c533467d6201a102` passed all five workflows and twenty regression jobs (`37190265015`); post-merge main also passed all five workflows and twenty jobs (`37190575050`), plus Pages. Main rescue job `111401692696` and time job `111401692694` each passed fifteen records without a rerun. This continuation rechecked remote main, merged PR, successful main jobs and the clean matching local main. Accepted phone evidence is not repeated.

The shared dynamic CI recovery worker now binds the expected attempt/profile to actual boot/netns and fixed interface name/ifindex/MAC/veth kind (host0, plus rescue0 for rescue). The controller verifies that binding and actual context at preflight and again after table comparison immediately before apply. The PID 1 worker verifies context before readiness and before deadline restoration. Changed, missing or unreadable context stops without overwriting current tables. Dynamic address/route/lease, MTU and link up/down remain outside identity so the existing dynamic and broken-path cases retain their original meaning. All original 5/22-second worker windows, 35-second unit bound and protocol assertions remain.

The new twenty-first job requires fifteen records across five fresh process/netns cases: stable restoration/revocation; same-name/same-MAC interface replacement rejected by a changed real ifindex; post-apply MAC drift stopped without replacement; worker SIGKILL after first readiness caught by the final check; and worker SIGKILL just after the final check followed by candidate installation/controller death. The last case must observe no restoration beyond the original deadline and real old/new qualification still active, reporting BLOCKED/WORKER_LOST_RECOVERY_UNVERIFIED. Identity-drift fail-stop similarly can leave qualification active. These are explicit unresolved operational boundaries, not successful recovery. Every authorization/review gate remains false, and the parent's later teardown is not recovery evidence.

Eight new, six shared recovery, six rescue and seven chrony tests pass locally (27 total); the new actual kernel acceptance passed as recorded below. All five final-head workflows and twenty-one regression jobs are required before integration. See [recovery context review](SECRET_CUSTODY_RECOVERY_CONTEXT_REVIEW.md). Exact code/final-head evidence and merge receipt belong in the PR.

Code head `cf623fd4fc106eaa0640ba2a3180734aa07dea75` (tree `10341d9f5eea121e4e08e1d61136ccaf6ef2f73e`), regression `37191566578`, context job `111404653037`, passed all fifteen records on its first execution, with `SYNTHETIC_RECOVERY_CONTEXT_OK_LAST_CHECK_GAP_UNQUALIFIED` at 2026-10-04 18:15:59 JST. The real same-name/same-MAC replacement changed ifindex 3 to 5 and was refused without table overwrite. Stable context restored/revoked old/new qualification and preserved administration. Post-apply MAC drift stopped restoration while actual qualification remained active. Worker loss after the first check was rejected before apply; loss after the final check allowed candidate installation/controller SIGKILL, then showed no recovery result after the original deadline plus one second and still-working old/new qualification. Both unsafe outcomes were explicitly BLOCKED with all authorization flags false. Each case cleaned up the worker/controller/peer, private files, links and owned tables, preserving the unrelated table until fixture teardown. Kernel `6.17.0-1022-azure`; no code-head retry or deadline relaxation.

The changed shared helper also passed the existing restricted rescue job on this code head; other protocol jobs were still completing when this evidence was recorded. All five workflows and twenty-one regression jobs on the final documentation head remain the integration gate. Exact final results and merge receipt belong in PR #193. This evidence demonstrates the last-check gap; it does not repair it or qualify first live installation.

Boot changes and stale attempts are synthetic negative tests; actual machine reboot, same-index/MAC reuse and arbitrary root writers are not qualified. Repeated point-in-time checks do not close the last-check/commit gap. Next: design separately enforced qualification expiry or recovery that remains effective after worker/controller loss, and test that combined failure before first live installation. Historical chrony sample-rejection causes remain unproven; use retained diagnostics if they recur. No phone/AWS/SSH/live-host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: restricted rescue independent of wrong primary allowances

Updated: 2026-10-04 (Asia/Tokyo).

PR #191 is merged/closed at `dfbb572a7f101b3f979951b085bc93395444393f`. Final head `72597b36c6ae7e27cfa216c0262f10845257198b` passed all five workflows and nineteen regression jobs (`37188298011`); DHCP DNS job `111394917716` reproduced all 37 records. This continuation rechecked the merge, final workflows and matching clean local/remote main. Accepted phone and observation evidence is not repeated.

The new fixed CI rescue profile uses a second static-address/static-neighbor veth for exact peer TCP/22 in both directions, with default-drop inet/netdev protection. It is independent of the exercised primary administration/DHCP/DNS allowance fault, not out-of-band from the kernel, namespace or owned tables. Candidate and ordinary fallback deliberately share incorrect primary peer addresses. A negative control requires both profiles to break existing/new primary administration and fresh DNS while the separate path survives. The separately fixed rescue material is not derived from either corrupted profile or discovered endpoints.

The existing independently supervised PID 1 worker retains its 22-second monotonic deadline and atomic two-table restoration. The controller dies by SIGKILL. Real networkd renewal/rebinding output must increment a dedicated drop counter and not reach the synthetic server; primary administration/DNS must fail while the rescue path still works. After exact restricted rescue restoration, require new DHCP ACK, actual lease/DNSEx, fresh A/AAAA including TCP, primary administration, unchanged daemon identities/unrelated table and revocation of old/new qualification. A second case lowers the separate rescue link after readiness; shape restoration and primary recovery must still occur, but unavailable rescue transport must yield BLOCKED/RESCUE_PATH_UNAVAILABLE with all gates false. No link repair or permission expansion is performed automatically.

Six rescue, seven chrony, six shared recovery, five DHCP DNS and four composition tests pass locally (28 total); git diff --check passes. The twentieth mandatory regression job has passed all fifteen real-kernel records across available/broken rescue cases, as recorded below. All five final-head workflows and twenty regression jobs must pass before integration; exact evidence and merge receipt belong in the PR. See [restricted rescue review](SECRET_CUSTODY_RESTRICTED_RESCUE_REVIEW.md).

Initial rescue head `18ad1e1ea9edf9c7c5d7a0e4b20ffe03e707e944`, regression `37189213031`, job `111397692130`, failed before daemon startup at 17:32:04 JST: the unrelated sentinel table omitted a separator after its nested chain. The emitted nft error identifies the closing table brace. Add the same chain separator used by the existing dynamic fixture; policy shape/isolation/client deadlines and all fifteen acceptance requirements remain unchanged. No rescue acceptance record passed on that initial head.

The initial runtime smoke `37189213111`, job `111397691920`, separately reported verification_failed:github.verify_ci at 17:31:49 JST. It reads latest completed main CI, not this PR's kernel test. Direct Actions GET (the commit helper only lists pull-request events) revealed post-merge main regression `37188611863` on `dfbb572a7f101b3f979951b085bc93395444393f` failed time job `111395857615`. At 17:21:40 JST its origin-prime preparation exceeded twelve seconds after successful IPv4 silent-primary failover/return. The primary was selected, both sources had reach 255/poll 0; primary cumulative RX/valid/good were 31/31/20, alternate 39/39/39. The preparation baseline and per-packet rejection reason were not retained, so the precise cause is unproven. Earlier PR #191 final CI and this PR's unchanged time job `111397692121` both passed. The prior PR acceptance statement remains correct; its later main push run did not pass.

One targeted diagnostic rerun of that failed main time job is authorized by the existing CI workflow scope and has been requested on a newly provisioned runner, with code/assertions/deadlines unchanged. Hypothesis: runner-dependent scheduling/sample acceptance may affect fresh-phase preparation. New information: whether the failure reproduces and the actual fresh-phase/client/server counters in the second run. Success requires all fifteen existing records including all four fresh preparations; a pass does not establish a root-cause fix. If it fails again, stop identical reruns and inspect the retained diagnostics. Do not weaken main verification or bypass the final CI gate. The historical preparation reliability limitation stays recorded regardless of that result.

The single diagnostic rerun (main regression `37188611863`, attempt 2, time job `111398307405`) passed all fifteen records at 17:37:07 JST without code/deadline changes. Fresh good-sample deltas (primary, alternate) were IPv4 silent (4,4), IPv4 origin (4,5), IPv6 silent (4,4), IPv6 origin (4,4), with actual poll 0 throughout. This is successful reproduction on another run, not a root-cause fix or a reliability guarantee. The failed attempt remains evidence. The changed fixture now retains the preparation baseline and bounded last ntpdata snapshots on failure, while preserving the original exception, four-good-sample gate and all time limits. One diagnostic regression test passes; seven chrony plus nineteen rescue/reused tests pass locally (26 total). Future recurrence must use these diagnostics rather than repeated identical reruns. Chrony preparation reliability remains an explicit follow-up alongside recovery identity/worker-loss tests.

Corrected grammar head `64a3ae63f9190036bd574cd46e44663dc7eb597c`, regression `37189615299`, rescue job `111398888857`, passed all eight available-path records, including the wrong-shared-fallback control, real DHCP/DNS/admin denial after controller death, independent restoration, actual ACK/fresh answers, usable-rescue verdict and owned cleanup. At 17:40:03 JST the second case failed before daemon startup with EADDRINUSE when reusing the wildcard administration listener. Both cases shared one process/network namespace; the helper's daemon accept threads can outlive socket context closure, but the exact retaining descriptor was not captured. Each case now runs in a separate bounded child process and fresh network namespace, and the parent waits for full process exit before the next case. One new unit guard rejects reuse of the parent namespace. No traffic, lifetime or verdict assertion is weakened; all fifteen records including the broken-link BLOCKED result remain mandatory. Five rescue, six recovery, five DHCP DNS, four composition and seven chrony tests pass locally (27 total). Failure diagnostics now preserve the original chrony exception even if an auxiliary diagnostic read fails; the existing diagnostic test covers both outcomes.

Head `3ff7ced5deaafa790f70c0a24036bacf3a6ce937`, regression `37189773966`, rescue job `111399353028`, again passed all eight available-path records and reached the broken-case baseline. It then timed out waiting only for a netdev DHCP drop. The journal shows real ACK/T1/T2 setup at 17:43:05 JST and bound-to-renewing at 17:43:13; the twelve-second wait ended at 17:43:21 before observing the later-layer count. The candidate also denies normal UDP output at inet, so netdev-only measurement cannot establish absence of DHCP activity. The correction adds a dedicated matching DHCP drop counter at inet as well, requires fresh non-regressing progress in either layer, prints both before/after counts, and still requires no server receipt, a live address, unfinished recovery and separate-path availability. The twelve-second measurement and 22-second recovery windows are unchanged. A new local test rejects unchanged/regressing counts and covers either observed layer.

The same head's time job `111399353040` passed IPv4 fully, then failed IPv6's existing five-second post-restore two-good-sample wait at 17:43:32 JST. That earlier phase had not used the new diagnostic helper, so its exact baseline/rejection cause remains missing. The unchanged three-second post-controller and five-second post-restore predicates now use the same bounded diagnostic wrapper and preserve original sample/selection/reach requirements and failures. No blind rerun or deadline extension is used. Six rescue, seven chrony and fifteen reused tests pass locally (28 total). Corrected-code acceptance is recorded below.

Corrected code head `14fcf826654b16c6fd311e190203fbcb3c4322d6` (tree `56f40d20f7eff67f30a22785cfb03449b6201d79`), regression `37190000878`, rescue job `111400011794`, passed all fifteen records and `SYNTHETIC_RESTRICTED_RESCUE_OK_NO_LIVE_APPLY` at 2026-10-04 17:47:41 JST. Both AVAILABLE and BROKEN cases measured DHCP drops `{inet: 0, netdev: 0}` to `{inet: 1, netdev: 0}` with no new server receipt: this run directly observed denial at the earlier inet hook. Both cases restored exact restricted shape, revoked old/new qualification, reacquired actual DHCP ACK/fresh DNS/primary administration and cleaned up all owned resources. AVAILABLE verified the separate existing/new/bidirectional path; BROKEN correctly returned BLOCKED/RESCUE_PATH_UNAVAILABLE despite successful shape/primary recovery. All verdict gates remained false. Kernel `6.17.0-1022-azure` and networkd/resolved/dbus hashes match PR #191's recorded binaries.

The same head's time job `111400011614` passed all fifteen records at 17:47:53 JST, with fresh primary/alternate good-sample deltas (4,4) in each of the four IPv4/IPv6 silent/origin preparations and poll 0 throughout. Chronyd/chronyc hashes and version 4.5 match the previous recorded binaries. This validates the changed diagnostic code and original acceptance in this run; it does not establish a fix for the missing historical rejection causes. Four other workflows had passed and the existing DHCPv6 lifecycle job was still running when this targeted evidence was recorded. All five final-documentation-head workflows and twenty regression jobs remain required before merging PR #192; exact final results and merge receipt belong in that PR. No additional identical diagnostic rerun is planned; any recurrence must use the new retained baseline/ntpdata evidence.

This starts from a pretested restricted CI anchor; initial installation from the live unfiltered baseline remains unqualified. TCP echo is administration transport evidence, not SSH authentication. No live second interface, rescue route, source approval or independent host recovery exists by implication. Persistent installation/reboot, worker death after readiness, stale interface/boot identity, non-cooperating writers, combined DHCPv6/RA/route faults and rescue-path repair remain outside scope. Next: bind recovery readiness to boot/interface identities and exercise worker loss after readiness before considering first-install rehearsal. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: caller-bound observation restart and stale-result rejection

Updated: 2026-10-04 (Asia/Tokyo).

PR #190 is merged/closed at `d5f3cf5cb5ed39ded6423522b4faa4ca3a6b0596`; final head `13712ab400fd0b4971aee4ed949208539ef9492e` passed all five workflows and nineteen regression jobs (`37179787609`). Final DHCP DNS job `111369842553` passed twelve standalone plus eighteen composed records; time job `111369842505` passed fifteen prepared-phase records. The exact historical chrony timeout cause remains unproven. This continuation rechecked the merge, final workflows and matching clean local/remote main; no accepted phone evidence is repeated.

The CI collector now pins the caller's expected boot, daemon PID/start/executable, namespace, cgroup, interface and private-bus identities before its first manager read and before publication. Lease/link versions remain a per-collection bracket, separate from daemon identity. The parent launches a collector, records its actual PID/start and publishes the request atomically; the collector checks its own identity. Consumption requires the exact request ID and collector instance, matching expected service identities and current file bracket, ordered integer monotonic times, a collection window of at most four seconds and request age of at most five seconds. Partial/legacy, different-attempt, expired, changed-identity and changed-bracket results are rejected. All review/apply/freshness/qualification/mutation gates remain false. This is CI plumbing, not a new production reader.

Eight new negative/contract tests plus five DHCP DNS, four composition and six resolver tests pass locally (23 total); git diff --check passes. The nineteenth regression job retains its original twelve standalone and eighteen composed records and adds seven mandatory acceptance records: valid caller binding; actual observer SIGKILL/restart with rejection of old complete/partial results; old sandbox cleanup; whole private networkd/resolved/bus replacement with rejection of old expected identities and old completed results; a newly bound collection of the same selected DNS facts plus fresh A/AAAA/admin; replacement cleanup; and peer/link/rule cleanup.

Code head `21ce5116c4ec3591685138150e9a0a0049308656`, regression `37188103326`, DHCP DNS job `111394316107`, passed all twelve standalone, eighteen composed and seven new restart records. The restart success marker appeared at 2026-10-04 17:13:36 JST (08:13:36 UTC runner log). Actual SIGKILL/restart rejected old completed and partial results. After verified teardown, a second real networkd/resolved/bus sandbox acquired the same selected DNS facts; the old expected identity caused the collector to exit before publishing any partial/complete file, and the old completed result was rejected against the new identity. A new caller-bound collection succeeded, with fresh A/AAAA/TCP upstream events, administration, unchanged policy shapes and complete cleanup. The job reported kernel `6.17.0-1022-azure` and the same installed binary hashes as PR #189/#190. No failure or retry occurred in this code-head acceptance. Four other workflows were successful; the existing DHCPv6 lifecycle job was still running when this evidence was recorded. All five workflows and nineteen regression jobs on the final documentation head remain the integration gate; exact final results and merge receipt belong in PR #191.

Whole private-sandbox replacement is the intended restart scope, not an individual service restart retaining the same private bus/mount. Synthetic cases exercise same-PID/different-start and identity/clock changes; real kernel PID reuse and machine reboot are not claimed. Equal brackets and short age do not establish atomicity, authenticated origin, production freshness, protection from arbitrary root writers, or single-use replay protection inside one accepted attempt. The immutable live dependency reader is unchanged and uninvoked. First restricted installation, independent rescue for wrong shared allowances, reboot, non-cooperating writers and recovery-worker death after readiness remain unqualified. Next: review and test an independent restricted rescue path under deliberately wrong shared allowances before considering initial installation. No phone/AWS/SSH/live host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: DHCP DNS changes across independent restricted recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #189 merged at `d68820cd22d848267f5060497ba54b0378d7b1a0`. Final head `8fb75fe66e6f39cc2330fc47c190c1868593be7c` passed all five workflows and nineteen regression jobs (`37178146385`); DHCP DNS job `111364997322` reproduced twelve acceptance records, and resolver job `111364997370` reproduced eighteen. This continuation rechecked merged/closed state, final workflows and matching clean local/remote main.

This slice composes the real private networkd/resolved DHCP DNS fixture with the independent PID 1 recovery worker. A fixed `dhcp-dns` profile restores the exact DHCP DNS maintenance tables, including TCP DNS and excluding unused NTP. Require fresh stub answers after controller SIGKILL, then an actual DHCP renewal to the unapproved DNS source while qualification remains active. Actual observations must require review with all gates false; new DNS output drops and unchanged upstream events prove denial. Independent two-table restoration must revoke old/new TCP qualification while preserving administration and the unchanged DNS configuration. Require a fresh denial after restoration, then actual DHCP renewal back to the approved source, fresh answers and unchanged daemon identities. The complete original twelve-record observation/expiry suite continues under the restored policy. Six added composition records plus the twelve base records are mandatory; the original standalone run remains a separate mandatory step in the same nineteenth job.

Four composition, five DHCP DNS, six shared recovery, six resolver and six chrony tests pass locally (27 total); git diff --check passes.

Corrected DNS code head `7466aba9da805d768ed9d58403edaa8ea8e125fb`, regression `37179484253`, DHCP DNS job `111368947973`, passed all twelve standalone plus eighteen composed acceptance records and `SYNTHETIC_DHCP_DNS_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY` at 14:20:57 JST. The installed binaries/kernel match PR #189. In the real composed run, A increased active transactions 0→1 before restoration and distinct AAAA increased 1→2 afterward; approved-source renewal drained the work and fresh A/AAAA answers succeeded with unchanged daemons/admin. The restored policy subsequently passed the full interrupted/mixed collection, source-change, return and real expiry lifecycle. This proves the exercised order, not simultaneous DHCP mutation and firewall restoration. The full run did not pass because the separate existing chrony job failed as recorded below.

On the same head/run, time job `111368947964` passed IPv4 and IPv6 post-restore samples plus IPv6 silent-primary failover, then exceeded the unchanged 35-second IPv6 wrong-origin failover bound. Its log shows alternate selection at 14:19:11 JST and primary return at 14:19:12, but omits reach, poll and accepted-measurement state at timeout; the historical cause is not established. Existing code started the next fault as soon as primary selection returned, which can reuse old samples. Phase carryover/insufficient fresh alternate samples is a hypothesis to test, not a retroactive diagnosis. The changed fixture requires four fresh good measurements from BOTH sources with primary selected/reachable before each fault (12-second bounded preparation), reads one source-state snapshot per failover predicate, records poll/reach and client/server counters, and preserves the original 35-second failover/20-second return bounds and invalid-response rejection. The same unprivileged clockless client survives throughout; no reset, forced selection or packet-filter change is introduced. One new local test rejects old/one-sided/unreachable measurements. Six chrony plus twenty-one DNS/recovery/resolver tests pass (27 total). Current-head real fresh-phase acceptance and all five workflows/nineteen regression jobs remain required; exact final results and merge receipt belong in PR #190. A later successful prepared-phase run does not prove the missing historical state.

Initial head `c23e575df48f5d068b840aae52e9286293088ed2`, regression `37179257704`, job `111368290742`, passed all twelve standalone records plus fresh queries after controller death, actual changed-DNS denial under qualification and PID 1 restoration with old/new qualification denial. It then failed while waiting fifteen seconds for all transactions to disappear with the unapproved DNS still configured. The retained journal explicitly shows timeout/retry and TCP fallback for transaction 48673 at 14:14:56 JST; a one-second UDP client timeout did not cancel the resolver's continuing work. The earlier source-return drain result does not apply while the source stays blocked. The correction keeps the original A denial, requires its one pending transaction after restoration, then issues distinct AAAA and requires actual active count 1→2 plus a new output drop and no peer receipt. This prevents coalesced/cached failure from being accepted without assuming premature drain. After actual DHCP return to the approved source, the original fifteen-second zero-transaction bound and fresh A/AAAA answer requirements remain. A new local negative test rejects unchanged active count; four composition tests pass (21 total with reused suites). No firewall/client deadline was relaxed and no daemon restart or blind rerun is used. Corrected DNS acceptance subsequently passed as recorded above; the full final CI gate remains required. All five final-head workflows and nineteen regression jobs remain required before integration. See [DHCP DNS review](SECRET_CUSTODY_DHCP_DNS_REVIEW.md); exact final evidence and merge receipt belong in the PR.

This does not prove that DHCP mutation and firewall restoration occur in the same kernel transaction, or qualify production observation/freshness, DHCPv6 DNS, NSS, observer restart/reuse with changed daemon identities, independent rescue for wrong shared allowances, first restricted installation, reboot, non-cooperating writers or recovery-worker death after readiness. Next: bind observation restart/reuse to the expected daemon identities and reject stale completed/partial results; keep the first-install/rescue boundary explicit. Accepted phone evidence stays accepted. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: actual DHCPv4 DNS delivery and interrupted observation

Updated: 2026-10-04 (Asia/Tokyo).

PR #188 merged at `b364f4fcd2400dfa436cb0e995cbec2b0f1ab2a3`. Final head `afc2a2bfe2362e1865af0d6bca852c9316753dab` passed all five workflows and eighteen regression jobs (`37174593370`); final resolver job `111354474154` reproduced all eighteen acceptance records. This continuation rechecked merged/closed state, the final workflows and matching clean local/remote main.

This slice shares a private mount/network/runtime and D-Bus between actual installed networkd and resolved. A bounded synthetic DHCPv4 server supplies option 6; real renewals change the DNS address and restore it, and real lease expiry withdraws it. No SetLinkDNS is used. Require the private lease, actual DNSEx and networkd Describe origin to agree, then query the real stub and observe upstream answers. Unapproved DHCP-provided DNS must be denied without changing either firewall table. Existing administration and the same daemon identities must survive source changes; expiry intentionally removes address/route reachability. Separate collection processes bind a unique attempt ID, monotonic window, boot/process/start/namespace/interface/bus identities and private lease/link file versions. Real SIGKILL after the first read must leave no complete observation. A real renewal between reads must reject the mixed collection. Completion is fixture evidence only: matching brackets do not prove atomicity or live freshness, and all apply/qualification/freshness gates stay false.

Five new, six resolver, fourteen comparison and five DHCP tests pass locally (30 total). A nineteenth mandatory regression job and twelve kernel acceptance records are added. Code head `7638dcc6000d9921752333caf3f0f6b4293a23c8`, regression `37178001953`, new job `111364577877`, passed all twelve acceptance records and `SYNTHETIC_DHCP_DNS_OBSERVATION_OK_NO_LIVE_APPLY` at 04:48:17 UTC on October 4 (13:48 JST). Installed systemd is `255.4-1ubuntu8.17`, kernel `6.17.0-1022-azure`; networkd SHA-256 `12e65fbae70b7cf17a84299c5323eb0735309c2891d3caea321a4ad2093f8c19`, resolved `5e694042ba4bad6c29584334eeb5b06c6abdab17a84d96718dd286e41bff322d`, dbus-daemon `8c479f1fcddfd6693c736ce541da0955f6752834bdeeef4b928e27f5e974c247`. Real acquisition, origin agreement, stub A/AAAA/TCP, SIGKILL partial rejection, renewal-during-collection rejection, unapproved-source denial without widening, approved return with unchanged daemon identities/admin, expiry withdrawal and full cleanup passed. Four completed collection windows were 24.878015, 23.923450, 24.856132 and 23.621945 milliseconds; three had matching selected facts and the expired observation was blocked as EMPTY_RESOLVER_SET. The separate resolver job `111364577855` also reproduced all eighteen previous acceptance records. Other workflows/jobs were still running when this targeted evidence was recorded; all five final-head workflows and nineteen regression jobs remain the merge gate. No failure/retry occurred in this code-head acceptance. See [DHCP DNS observation review](SECRET_CUSTODY_DHCP_DNS_REVIEW.md). Exact final results and merge receipt belong in the PR.

This qualifies neither DHCPv6 DNS nor NSS, production collection, authenticated origin, atomic cross-manager snapshots, first restricted installation, independent rescue from wrong shared allowances, reboot, non-cooperating writers, or worker death after readiness. The collection ID is not a DHCP protocol generation. The prior resolver recovery fixture remains separately mandatory; combined DHCP-DNS plus controller-death restoration is still untested. Next: compose actual DHCP-delivered DNS changes with independent restoration and review bounded observer restart/reuse under changed daemon identities. Accepted phone evidence is not repeated. No phone/AWS/SSH/live host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: isolated real resolver cache and source switching

Updated: 2026-10-04 (Asia/Tokyo).

PR #187 merged at `2cf71d9acae31fb444503fbea77c55a9ea03206a`. Final head `c4b04fed4121cdcadf52c391455c5bd4684dee54` passed all five workflows and seventeen regression jobs (`37171989540`). Dependency job `111346644090` passed fourteen comparison tests, ten reader tests and the separate Ubuntu reader check. This continuation rechecked merged/closed status, final workflows and matching clean local/remote main.

The new CI fixture runs actual systemd-resolved and a private D-Bus daemon in a dedicated mount/network environment with generated read-only configuration and private runtime. It queries the actual stub, measures A/AAAA cache hits and real TTL expiry using upstream events, tests upstream truncation/TCP fallback and stub TCP, composes controller-death restoration with the same resolver, and changes private per-link DNS to an unapproved source without changing firewall rules. Require actual DNSEx readback, bounded failure and output drops with no unapproved server receipt, approved-source return, administration survival and full cleanup. Eighteen acceptance records and the new eighteenth mandatory regression job are required. Six local resolver tests plus five DNS and six shared recovery tests pass (17 total). Corrected code head `e9289e5a9df87f10eddb85230d0de0dbffa3e522`, regression `37174444054`, resolver job `111354030300`, passed all eighteen acceptance records and `SYNTHETIC_RESOLVED_CACHE_SWITCH_RECOVERY_OK_NO_LIVE_APPLY` at 03:35:14 UTC on October 4 (12:35 JST). The actual package reports systemd `255.4-1ubuntu8.17`, kernel `6.17.0-1022-azure`; resolved SHA-256 `5e694042ba4bad6c29584334eeb5b06c6abdab17a84d96718dd286e41bff322d`, dbus-daemon SHA-256 `8c479f1fcddfd6693c736ce541da0955f6752834bdeeef4b928e27f5e974c247`. Both families passed private bus/config/source readback, warm A/AAAA cache with unchanged upstream events, changed answers after real TTL expiry, UDP truncation/TCP and TCP stub cache responses, fresh queries after controller death and after independent restoration, unapproved-source denial without rule changes, source return, administration and full cleanup. Actual pending transaction count was one in each family; after source restoration, zero was reached in 9.008 seconds for IPv4 and 9.203 seconds for IPv6, followed by fresh same-name A/AAAA upstream events. This confirms delayed drain in the reproduced scenario, not instantaneous recovery or a guarantee for other versions. Other code-head jobs were still running when this targeted evidence was recorded. All five workflows and eighteen regression jobs on the final head remain mandatory; exact final results and merge receipt belong in PR #188. See [resolver cache review](SECRET_CUSTODY_RESOLVED_CACHE_REVIEW.md). All five workflows and eighteen regression jobs on the final head remain the merge gate; exact final evidence belongs in the PR.

Initial head `51bcca67c3d792ff0666580ff1d3ab91a4178654`, regression `37174153597`, resolver job `111353154685`, passed direct upstream baseline then stopped before daemon startup: `/run/systemd` already existed in the private runtime and exclusive mkdir raised FileExistsError. The private mount/runtime/config guards had passed. The fixture now accepts an existing real directory after lstat, but rejects symlinks/files; a real temporary-filesystem regression covers these cases. Six resolver plus eleven reused tests pass (17 total). No isolation guard, deadline or network assertion was relaxed. Corrected real-resolver acceptance subsequently passed as recorded above; final complete CI remains required.

Second head `c5f7197dc1b626614471137e24e8de7fde7ab4d5`, regression `37174244369`, resolver job `111353435221`, passed isolation plus IPv4 cache/TTL, truncation/TCP, controller-death and restored fresh queries, and unapproved-source denial. It failed the immediate same-name query after restoring the approved source. The log shows the denied UDP attempt falling back to TCP and the subsequent query remaining in processing; upstream v255 uses a ten-second TCP transaction timeout. A pending old transaction is the hypothesis to measure, not an assertion that configuration readback guarantees immediate recovery. The changed test requires actual positive TransactionStatistics after client timeout, restores the approved source, waits at most fifteen seconds for actual zero active transactions, then flushes only the private cache and requires fresh A/AAAA upstream events. Existing one-second client queries, isolation, policy shape and deny assertions are unchanged. If transactions do not drain, the test fails; no daemon restart or blind retry is used. Corrected acceptance subsequently passed as recorded above; final complete CI remains required.

This uses explicit private SetLinkDNS, not actual DHCP-to-resolved delivery or NSS integration. No production DNS, cache, transport or initial installation is qualified. Next: actual isolated DHCP-provided DNS changes and generation/identity-bound observation, including interrupted collection. Initial restricted installation, independent rescue for wrong shared allowances, reboot, non-cooperating writers and worker death after readiness remain blocked. Do not repeat accepted phone evidence. Installed Ubuntu DHCPv6 remains unqualified. No phone/AWS/SSH/live host/credential action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: DNS observation reconciliation and first-install review

Updated: 2026-10-04 (Asia/Tokyo).

PR #186 merged at `82e6a4f65b479cc85798b1ba94af6c71771e3ef1`. Final head `0cf7e7b53cb7263977bd642cd943db3899a76a5a` passed all five workflows and seventeen regression jobs (`37167335331`); final time job `111332909527` reproduced all fifteen acceptance records. This continuation rechecked the merged PR, final workflows and matching clean local/remote main.

This slice adds a pure comparison of selected private dependency-reader facts. Existing-parser synthetic inputs test resolved/networkd agreement, endpoint addition/removal/change, provider/interface change, default-port representation, unknown/incomplete data and output redaction. Matching observations never authorize endpoints or establish freshness. All decisions retain qualification/mutation/apply/freshness gates false; there is no host reader invocation, policy renderer or apply adapter. Fourteen new comparison tests plus ten existing reader tests pass locally (24 total). The comparison tests are mandatory in the existing dependency CI job; all five final-head workflows and seventeen regression jobs remain the merge gate. Exact final results and merge receipt belong in the PR.

The [DNS reconciliation and first-install review](SECRET_CUSTODY_DNS_RECONCILIATION_REVIEW.md) separates implemented comparison from proposed real-resolver and first-install acceptance. No current report has trustworthy freshness, atomic collection or effective resolver-transport/routing coverage. No live resolver or initial maintenance installation has become qualified. A separately restricted rescue profile and a recovery path demonstrated under deliberately wrong candidate allowances are prerequisites; a timer restoring the same wrong allowance is insufficient. No automatic unfiltered rollback or broader access is introduced.

Next: isolate a real resolver with private IPC/config/runtime, then verify client-path queries, cache/TTL behavior, changed DHCP DNS and denial without widening rules. First-install independent rescue, reboot, non-cooperating writers and worker death after readiness remain blocked. Do not repeat the accepted phone reader observation. Installed Ubuntu DHCPv6 remains unqualified. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: chrony source selection without host clock control

Updated: 2026-10-04 (Asia/Tokyo).

PR #185 merged at `1e534bed3cb3b27720cbd5385942e2e59be208da`. Final head `1ed064012fd25d6fdf15668e6445face7f8d356a` passed all five workflows and sixteen regression jobs (`37165380672`); final DNS job `111327095363` reproduced all sixteen acceptance records. This continuation rechecked the merge, exact final workflows and matching clean local/remote main. Fixed DNS evidence remains accepted with its recorded limits.

The new isolated time fixture uses real chronyd with `-x` and uid/gid 65534, empty capability sets/bounding set and NoNewPrivs. It extracts the Ubuntu chrony package into an owned CI directory without package installation or service scripts; version and executable hashes are recorded. Only two fixed synthetic NTP sources per family are approved. Require primary selection, new accepted measurements after controller SIGKILL and after PID 1 two-table restoration, automatic alternate selection when the primary becomes silent or sends wrong originate timestamps, primary return, and denial of an unapproved source/TCP transport. The same client and administration socket persist across recovery. Read actual chronyc selection/reach and accepted-measurement counters, not just UDP receipt. Five NTP/report/guard and six shared recovery tests pass. Corrected code head `f13291df52c550ed5ae19d46282e3ba91eaf9ef5`, regression `37167200665`, time job `111332494299`, passed all fifteen acceptance records and `SYNTHETIC_TIME_RECOVERY_OK_NO_CLOCK_OR_LIVE_APPLY` at 01:11:47 UTC on October 4 (10:11 JST). Ubuntu package `4.5-1ubuntu4.2`, chronyd 4.5, kernel `6.17.0-1022-azure`; chronyd SHA-256 `7a834e478d8a904c39a348606a5d0ac58fd1ccbca24f333a8170c786af8ca508`, chronyc SHA-256 `271ea54c67206559437bd299d0e08c9e3d42ee6be322b1722e76311cd5d9df8d`. Both families selected the preferred primary without clock capabilities, accepted fresh measurements after controller death and independent restoration, selected the approved alternate for silence and wrong-origin replies, returned to primary, denied the unapproved source/TCP transport, preserved administration and qualification denial, and cleaned up clients, files, links and rules. Other code-head jobs were still running when this targeted evidence was recorded. All five workflows and seventeen regression jobs for the final head remain mandatory; exact final evidence and merge receipt belong in PR #186. See [time recovery review](SECRET_CUSTODY_TIME_RECOVERY_REVIEW.md). All five final-head workflows and seventeen regression jobs are required before merge.

Initial head `dd847428974c748d5472f3b2dd47b865b30e6e0e`, regression `37166897486`, time job `111331572656`, passed baseline and five IPv4 records, including accepted measurements after restoration and alternate selection for silent/wrong-origin replies. It stopped at the unapproved UDP probe: `sendto` returned `EPERM` immediately, but the helper handled only receive timeout. The helper now accepts only EPERM or timeout for an expected denial; positive probes, unrelated errors and any received reply still fail. A local regression covers these distinctions. The actual output-drop increment and unchanged peer counters remain mandatory. Five time tests plus six recovery tests pass. Corrected CI subsequently passed both families and complete cleanup as recorded above; the final complete CI gate remains required.

No host clock setting, host time-service installation/configuration, external time server, NTS/cryptographic authentication, accuracy/UTC traceability, DNS discovery or combined DHCP/RA/DNS/PMTU lifecycle is qualified. Next: resolver integration/discovery and first restricted maintenance installation/recovery design. Nine observed live time entries do not become an approved allowlist. Installed Ubuntu DHCPv6 remains unqualified. Worker death after readiness, non-cooperating root writers, reboot and wrong shared allowlists remain unresolved. No phone/AWS/SSH/live host/credential action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: fixed DNS transport through independent recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #184 merged at `99110f436a3cb8ac1bd1b94342d09e0fdbf43144`. Final corrected head `231acd82c86d806480f47b883fed1412cdc47fa1` passed all five workflows and fifteen regression jobs (`37163379851`). Its PMTU job `111321280325` passed ten standalone and sixteen recovery records. H2d job `111321280201` passed fourteen local and five real-systemd tests including intentional collection before stale reset. This continuation rechecked the merge, exact final workflows and matching clean local/remote main. The earlier reset failure remains historical evidence; its omitted state is not retroactively proved by the reproduced race.

This slice adds mandatory `custody-dns-recovery` with installed `dig` and bounded synthetic DNS servers in a private dual-stack network. Require actual A/AAAA answers over UDP, explicit TCP and UDP truncation→TCP fallback under maintenance, after controller SIGKILL with qualification active, and after independent two-table restoration. A silent approved server must cause a bounded failed query; an unapproved changed endpoint must remain denied over UDP/TCP; re-enabling the original server with changed data must yield fresh answers. Actual unsolicited replies from the approved address must reach netdev then be denied by inet conntrack, and wrong-source replies must be denied at netdev. Existing/new administration, old/new qualification denial, final rule shape and cleanup remain required. Fifteen local DNS/recovery helper tests pass. Corrected code head `6d1e5e762799a8f3a3a145d18e6e299134645625`, regression `37165231450`, DNS job `111326663169`, passed all sixteen acceptance records and `SYNTHETIC_DNS_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY` at 00:32:22 UTC on October 4 (09:32 JST). Installed client identity was `DiG 9.18.39-0ubuntu0.24.04.7-Ubuntu`, kernel `6.17.0-1022-azure`. Actual A/AAAA UDP, TCP and truncation fallback passed in maintenance, while the controller was dead, and after PID 1 restoration. Both families passed bounded outage, changed-endpoint denial, fresh changed answers, unsolicited/wrong-source rejection and cleanup. The other code-head jobs were still running when this targeted evidence was recorded; all five workflows and sixteen regression jobs for the final head remain mandatory. Exact final results and merge receipt belong in PR #185. See [DNS recovery review](SECRET_CUSTODY_DNS_RECOVERY_REVIEW.md). All five final-head workflows and sixteen regression jobs are the integration gate; exact final evidence and merge receipt belong in the PR.

Initial head `2973efc9ff5b19d1dad02148afbf6899ded00519`, regression `37165073764`, DNS job `111326222401`, passed baseline, both maintenance/qualification transport sets, independent restoration and IPv4 post-restoration DNS. It then failed the expected-outage assertion: dig correctly returned exit 9 (no response), but its single-semicolon banner was incorrectly counted as an answer. The parser now excludes both single/double-semicolon diagnostics and requires exactly exit 9 plus no answer lines for negative queries. A regression test rejects arbitrary exit 1, success-without-answer and a failed query containing an answer. Version reporting now checks both stdout/stderr and requires a bounded `DiG ` identity. The changed conditions are result classification/version capture only; no network assertion is skipped. Five DNS and ten helper tests pass (15 total); Corrected DNS acceptance passed as recorded above; the final complete CI gate remains required.

This qualifies fixed DNS transport only, not systemd-resolved/NSS, cache or TTL expiry, automatic resolver discovery/failover, DNSSEC, encrypted DNS, or simultaneous DHCP/RA/PMTU lifecycles. No resolver configuration or host clock is changed. Next: synthetic time-source behavior, resolver integration/discovery design and first restricted maintenance installation/recovery design. Installed Ubuntu DHCPv6 remains unqualified. Worker death after the final readiness check, non-cooperating root writers, reboot and wrong shared allowlists remain unresolved. Completed phone evidence stays accepted. No phone/AWS/SSH/live host/credential action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: routed PMTU after independent restricted recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #183 merged at `98f569e29ac7e5b862f5d298704281164ee6121c`. Its final head `1b08ac107d4ad2bfd4e04e478961d0961bbd40d5` passed all five workflows and fifteen regression jobs. Merge state, final workflows and matching clean local/remote main were rechecked on this continuation; all twelve DHCPv6 composition acceptance records remain accepted.

This slice composes routed IPv4/IPv6 PMTU with the existing independent PID 1 recovery worker. Fixed qualification profiles add only the documentation peer's TCP/443 tuple in both owned tables. After controller SIGKILL, actual qualification exchange must succeed; independent atomic restoration must revoke old/new qualification while existing management/bulk and new management connections work. The existing bulk socket must still report PMTU 1500 after restoration. The original forged-error rejection and real router 1500→1280 blocked-PTB stall/same-flow recovery then run under the restored policy. Final shape and old/new denial are checked again. The original standalone fixture stays mandatory. See [PMTU recovery review](SECRET_CUSTODY_PMTU_RECOVERY_REVIEW.md). Code head `ed5e49640688e2384ae95016a170be795b271dd8` passed all sixteen composition acceptance records in regression run `37162795373`, PMTU job `111319533837`, on kernel `6.17.0-1022-azure`. The ten standalone records also passed. For both families the independently restored bulk socket still reported PMTU 1500; subsequent real router errors quoted 1500-byte packets and announced MTU 1280. Blocking them stalled the transfer, and admitting them delivered all 65,536 bytes on the same socket. IPv4 MSS changed 1448→1228, IPv6 1428→1208, with actual unfragmented wire packet lengths at most 1280 and 1280 observed. Post-restoration forged-error rejection, restored shape, old/new qualification denial, management survival and cleanup passed. The composition ended with `SYNTHETIC_PMTU_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY` at 23:46:31 UTC on October 3 (08:46 JST on October 4). Fourteen local tests and `git diff --check` passed. All five code-head workflows succeeded, including all fifteen regression jobs in run `37162795373`. All five final-head workflows are required before integration; final run IDs and merge receipt belong in PR #184.

The first evidence-only head `d56f6fb9c4d21776e94cacafffad3efbb7c81853` passed PMTU again but failed existing H2d job `111320627742` in run `37163162130`. Invalid probe output was correctly rejected as `PROCESS_EVIDENCE_INVALID`; cleanup then replaced that error with `PROCESS_RESET_FAILED`. The log does not contain reset stderr/state, so transient-unit collection between ownership readback and reset is a hypothesis, not a proven diagnosis of that historical run. H2d cleanup now tolerates a nonzero reset only when a new manager readback verifies `LoadState=not-found`; existing directory/cgroup absence checks still run. A retained or unreadable unit still fails. Two local tests cover absent/retained units and remaining cgroups. A real-systemd test forces collection between readback and the actual stale reset, requires its nonzero exit, preserves the original rejection and verifies cleanup. The probe exits nonzero on SIGTERM so the test retains the failed unit until intentional collection. Fourteen H2d local tests pass (28 total with the PMTU/helper checks). Corrected-head CI remains required; no assertion was skipped and no blind rerun was used.

Next: DNS/time protocol lifecycle and first restricted maintenance installation/recovery design. Static routes/neighbors here do not establish simultaneous DHCP/RA/PMTU composition or a route change during the restoration transaction. Installed Ubuntu DHCPv6 remains unqualified. Worker death after the final readiness check, non-cooperating root writers, reboot and a wrong shared allowlist remain unresolved. Completed phone evidence remains accepted. No phone/AWS/SSH/live host/credential operation; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: patched DHCPv6 with independent restricted recovery

Updated: 2026-10-04 (Asia/Tokyo).

PR #182 merged at `a8cb390df54b1c183623cfee31d7c905eef8dc39`. Final head `a8fb90bfbec4a575a144952805fe2d0c1d6591b0` passed all five workflows and fifteen regression jobs. GitHub merge and final workflows were rechecked on this continuation; its seventeen dynamic-recovery acceptance records remain accepted.

The next slice adds a fixed DHCPv6 profile to the independent PID 1 worker, using only the previously qualified pinned patched CI networkd build. A real Renew must refresh the lease while the controller is dead and qualification is active; the worker then atomically restores inet and netdev, denying established/new qualification traffic while preserving administration. The original complete lifecycle is reused after restore, with a fresh event window for Renew, alternate-DUID Rebind/adoption and lease expiry while RA routing remains. A post-restore wrong-source frame is rejected. The original-client defect control and standalone patched lifecycle remain mandatory. Seventeen local composition/helper tests plus four builder/provenance tests pass (21 total); all five final-head workflows are required before integration. See [DHCPv6 recovery review](SECRET_CUSTODY_DHCPV6_RECOVERY_REVIEW.md).

Initial PR #183 head `54530d4ce47f13850da3fd8a904bfd9b750fe1fc` failed before compilation in run `37161194778`, job `111314797928`: `PINNED_CLIENT_INPUT_MISMATCH`. All three Ubuntu downloads still match their original hashes. The GitHub-generated fix patch changed only its index abbreviations from 11 to 12 hex digits; restoring the 11-digit representation exactly reproduces original SHA-256 `b581a4c784a89648f8a8f25866a2b66ad57e54e6644a3ab2c8b6fe75fef86ffb`. The current generated patch hashes to `f67ad156f3ec7e005cbdeb7975c5f7af201e2ac081714ea9a6d348d465743667`; the official commit API confirms the same one-line getter fix. The original reviewed bytes are now vendored in `tests/fixtures/dhcpv6-t2-fix.patch`. No pin or source change is accepted automatically: the old SHA check and exact applied one-line comparison remain mandatory. The changed condition is local immutable patch input rather than GitHub's generated representation. Corrected code head `27dd63ef9bc003c04c7e2f62e58da1418bd988a7` then passed the actual composition and all five workflows. Regression run `37161487535` passed all fifteen jobs; DHCPv6 job `111315666049` passed both original/standalone controls and all twelve composition acceptance records, ending in `SYNTHETIC_DHCP6_INDEPENDENT_RECOVERY_OK_NO_LIVE_APPLY`. The kernel was `6.17.0-1022-azure`. The independent restoration completed at 23:24:42 UTC, fresh post-restoration Renew at 23:24:44, alternate-DUID Rebind/adoption at 23:25:18 and expiry/final denial at 23:26:06. Owned-build cleanup succeeded and the installed networkd SHA-256 was unchanged. Final-head workflow evidence and merge receipt belong in PR #183.

Next is routed IPv4/IPv6 PMTU recovery composition. Installed Ubuntu DHCPv6 remains unqualified. DNS/time lifecycle, worker death after the last readiness check, non-cooperating root writers, reboot, first maintenance installation and a wrong shared allowlist remain unresolved. Completed phone observations stay accepted. No AWS/SSH/live host/credential operation; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: dynamic configuration with independent restricted recovery

Updated: 2026-10-03 (Asia/Tokyo).

PR #181 is merged at `1dd5666d779d82793b63d4a838b023ce1247d7ed`. Final head `f43ecb26969555a49a78a27e2e83ca30c784ce82` passed all five workflows and all fourteen regression jobs; this continuation rechecked the merge and workflow results against GitHub. Its actual IPv4/IPv6 routed PMTU evidence remains accepted.

PR #182 adds mandatory `custody-dynamic-recovery`, which composes installed networkd DHCPv4 and IPv6 RA/SLAAC/ND, in separate private networks, with PID 1 supervised recovery. Both inet and netdev tables are replaced in one nft transaction. The controller dies by SIGKILL; actual renewal/RA refresh must continue during qualification and after restricted restoration, existing/new administration must survive, and old/new qualification connections must fail. Real worker death before apply, controller death before apply, and independent drift in either table are negative cases. Shape comparisons ignore only handles and counter measurements, so legitimate packet counts cannot masquerade as policy drift. See [dynamic recovery review](SECRET_CUSTODY_DYNAMIC_RECOVERY_REVIEW.md). Code head `69ae85206d5bc193de6f538af2df549f959c16d0` passed all five workflows on its first run; regression `37128722659` passed all fifteen jobs. Dynamic recovery job `111219298078` passed all seventeen acceptance records (eight IPv4, nine IPv6) and `SYNTHETIC_DYNAMIC_RECOVERY_OK_NO_LIVE_APPLY`, using kernel `6.17.0-1022-azure` and installed networkd `255.4-1ubuntu8.17`. This success applies to DHCPv4 and RA/ND, not DHCPv6. Actual post-restoration DHCP Renew/Rebind, RA refresh/ND/expiry, worker/controller death cases, both-table drift and cleanup all passed without skipped assertions. Six new local tests and thirteen reused-helper tests also pass. All five final-head workflows must pass before integration; final evidence and merge receipt belong in PR #182.

This slice does not combine DHCPv6 or routed PMTU with recovery yet; these are the next composition targets. Installed Ubuntu DHCPv6 remains unqualified, while the separate pinned patched CI build remains qualified only in its recorded scope. DNS/time lifecycle, worker death after the last readiness check, concurrent non-cooperating root writers, reboot, first maintenance installation and a wrong shared administration allowlist remain unresolved. Completed phone evidence stays accepted. No phone/AWS/SSH/live host changes or credential use; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: real routed IPv4/IPv6 PMTU fixture

Updated: 2026-10-03 (Asia/Tokyo).

PR #180 merged at `c64253ff9443a19b6fa2c0964e9c4a75c0e34d07`. All five workflows for final head `c0affba6344e3a3589e4fe01bef6c3cb16dcb7b9` succeeded, rechecked on this continuation. Its success qualifies only the pinned patched CI build; installed Ubuntu 8.17 DHCPv6 remains unqualified.

PR #181 adds mandatory `custody-routed-pmtu`. Code head `a0e599ec6dde248882980182c7325cc92ec4b9ba`, regression run `37121414940`, job `111198105956`, passed all ten acceptance records and `SYNTHETIC_ROUTED_PMTU_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`. Both IPv4/IPv6 real routers emitted valid errors quoting 1500-byte TCP packets and announcing MTU 1280. Blocking those errors stalled the queued transfer; admitting only RELATED PMTU errors recovered the same 65,536-byte transfer. Connected MTU and TCP_INFO PMTU read 1500 then 1280; MSS changed 1448→1228 for IPv4 and 1428→1208 for IPv6. Receiver packet lengths were at most 1280, with a 1280-byte packet observed. Wrong source/code, unrelated quoted flow and out-of-window quoted TCP sequence rejection all passed, including the kernel sequence-rejection counter. TCP/443 stayed denied, existing/new administration remained usable, and namespace/process/link/rule cleanup passed. All fourteen regression jobs and all five code-head workflows succeeded. Four new and three shared-helper local tests pass. See [PMTU review](SECRET_CUSTODY_PMTU_REVIEW.md). All five final-head workflows must pass before integration; final results and merge receipt belong in PR #181.

The first PMTU head `8db90623c103fef7c85cf1bf164e8bb943d24c89` failed router setup in run `37121343744`, job `111197907590`: a missing separator after the nested nft chain produced an explicit parser error. The corrected separator/newline was the changed condition; the next run exercised every required assertion successfully. No PMTU success was claimed from the initial setup failure and no failed assertion was skipped.

This is fixed isolated PMTU qualification, separate from DHCP/RA and rollback. Next compose qualified dynamic controls with independently supervised restricted recovery. DNS/time lifecycle, a fixed live DHCPv6 deployment candidate, first restricted maintenance installation and wrong shared allowlist recovery remain unresolved. Completed phone observations remain accepted. No phone/AWS/SSH/live host action; H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: patched DHCPv6 CI lifecycle

Updated: 2026-10-03 (Asia/Tokyo).

PR #179 merged at `e805038a5c1404c260ab1a63a55726c81ec26810`; its IPv6 RA/ND/DAD evidence remains accepted. PR #180 adds paired real networkd source builds in isolated CI. Code head `e066c8c97f086df0f6cc0900337df2a402583b9b` passed all five workflows. Regression run `37118721668`, DHCPv6 job `111190467251`, built both clients, confirmed the typed defect in the original, and passed all eight patched-client acceptance records plus `SYNTHETIC_DHCP6_LIFECYCLE_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`. The patched client acquired its IA_NA address, reported separate timers, refreshed its actual lease, adopted the alternate DUID on the next Renew, preserved administration transport, expired the address while RA routing remained, and cleaned up. All thirteen regression jobs passed. Both root-owned client builds were removed; the installed networkd SHA-256 remained unchanged before and after.

The qualification target is explicitly the minimal custom Ubuntu 255.4-1ubuntu8.17 source build containing official upstream fix `8f5eaeb143dd9e58503980ae5f63dd78c463180e`. Identical build settings and RPATH removal are used for original and patched clients. Four source inputs are SHA-256 pinned; the applied patch is checked as exactly one getter-line change. Internal systemd libraries are statically linked and runtime binaries/manifest verified before use, then bound read-only inside the private client namespace. Twenty-one local tests pass. See [DHCPv6 review](SECRET_CUSTODY_DHCPV6_REVIEW.md) for the source hashes, executable hashes and acceptance evidence. All five final-head workflows must still pass before integration; their results and merge receipt belong in PR #180.

The original installed Ubuntu client remains unqualified: earlier heads `d92e190d82d6e21669a54ff8dc8e8f897137f9a6` and `87cd699cae804a5589764dfd9a9934f6e8bc1fe3` exposed its T2 getter defect. Do not replace this failure with the custom build's success. The first paired build at `a4f032dfc26bcf115e1bb32405a2b7667fb98084` compiled but failed the dependency/search-path gate; identical RPATH removal corrected that build-artifact issue and the next run verified no shared-systemd dependency. No protocol assertion was waived. Historical failures and the changed validation target remain recorded.

Next implement actual constrained-path IPv4/IPv6 PMTU, then compose dynamic control dependencies with independently supervised restricted recovery. Live DHCPv6 still needs an independently reviewed fixed deployment candidate; this CI build is not an installed or vendor-supported remedy. DNS/time lifecycle, first restricted maintenance installation and wrong shared allowlist recovery remain unresolved. Completed phone observations remain accepted; no phone/AWS/SSH/host action is requested. H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: IPv6 RA/ND/DAD control fixture

Updated: 2026-10-03 (Asia/Tokyo).

PR #178 merged at `5dd41f9fd28738530b05754582940ef19d08c521`. All five workflows succeeded for final head `89ca803cec06501f4e9b07f18eec4dcdd9266cae`, rechecked on this continuation. Restricted-link DHCPv4 acquisition/renewal/rebinding/expiry and administration survival are complete only in the recorded isolated scope.

The new mandatory IPv6 job reuses the private networkd launcher with a fixed IPv6 profile. It requires actual RA/SLAAC route acquisition/refresh/expiry, dynamic neighbor rediscovery, duplicate-address refusal, header rejection counters and existing/new off-link administration transport. See [IPv6 control review](SECRET_CUSTODY_IPV6_CONTROL_REVIEW.md). Four new local guard/checksum/empty-state tests and five shared DHCP tests pass; actual changed-head CI and all five final-head workflows must pass before integration. Initial head `af9a4a152b53329e2b45b9cb4d74afe0a2113e0f` failed before rule installation because an address-free IPv6 query returned an empty list; the unsafe first-element assumption is corrected with a reproducing local test. No protocol assertion is skipped. Corrected code head `153d681d755c2e332873370eadc01041a55fca42` passed IPv6 job `111179939207` in regression run `37114983663` on kernel `6.17.0-1022-azure`, networkd `255.4-1ubuntu8.17`, with all nine PASS records and `SYNTHETIC_IPV6_RA_ND_DAD_OK_NO_LIVE_APPLY`. Final-head workflow results and merge evidence belong in PR #179.

This is not DHCPv6, PMTU, router/neighbor authentication, complete IPv6 validation or live qualification. Next implement real DHCPv6 lifecycle and constrained-path PMTU, then compose qualified dynamic controls with independently supervised restricted recovery. First maintenance-anchor installation and recovery from a wrong shared allowlist remain unresolved. Completed phone observations remain accepted; no phone/AWS/SSH/host action is needed. H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: DHCPv4 lifecycle composed with restricted link policy

Updated: 2026-10-03 (Asia/Tokyo).

PR #177 merged at `e6f7c597d24c73f0d8f8852631b3c06bd87f67a6`. All five workflows succeeded for its final head `8d3af4b191c246359d3005a7ac773e41d0dda147`, rechecked on this continuation. The protocol-specific versus all-protocol packet-socket distinction and capability-free worker boundary remain accepted.

The next change strengthens the mandatory real networkd DHCPv4 fixture: inet and default-drop netdev restrictions exist before initial acquisition, then remain through unicast renewal, alternate-server rebinding and expiry. It adds pre-rule positive packet controls, exact drop counters for wrong tuples/fragments, qdisc-bypass controls, actual ARP without static neighbors and expired-address reachability refusal. Existing/new TCP administration transport and all prior lifecycle assertions remain required. See [composition review](SECRET_CUSTODY_DHCP_LINK_REVIEW.md). Five DHCP and three packet local tests pass. Code head `d6554eb9184a6ff83c825a015e6ed2f7d7b634bf` passed regression run `37113754710`, DHCP job `111176470089`, with all ten PASS records and `SYNTHETIC_DHCPV4_LINK_POLICY_COMPOSITION_OK_NO_LIVE_APPLY` on kernel `6.17.0-1022-azure`, nftables `1.0.9` and networkd `255.4-1ubuntu8.17`. All eleven regression jobs succeeded, including unchanged transition, recovery and packet-boundary jobs. Require all five final-head workflows successful before integration; their results and merge receipt belong in PR #178.

This is a fixed synthetic IPv4 composition, not a live policy, server authentication, ETH_P_ALL capture isolation, address renumbering, ARP spoofing defense or complete maintenance qualification. Next qualify IPv6 control traffic, then dynamic-dependency composition with restricted recovery. The first restricted maintenance anchor and recovery from an incorrect shared allowlist remain unresolved. Completed phone observations remain accepted; no repeated phone/AWS/SSH/host operation is needed. H2a and all runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gates remain OFF.

## Previous completed slice: raw packet filtering measured; DHCP link-policy composition next

Updated: 2026-10-03 (Asia/Tokyo).

PR #176 is merged at `d82ed0cf76d3f3bc240b8fba447c081d0465eec9`. Its final head `526dca65c4101a71176e23ceafcb45b8d7ab7bab` passed all five workflows, rechecked on this resumption. The real DHCPv4 lifecycle is complete in its recorded isolated scope. Completed live phone observations remain accepted; do not request identical retries.

PR #177 adds a mandatory CI fixture that measures ordinary UDP, protocol-specific AF_PACKET and ETH_P_ALL receive paths separately. It checks inet versus netdev ingress/egress, normal and qdisc-bypass transmission, wrong tuples/fragments, a separately executed capability-free child and owned cleanup. See [packet boundary review](SECRET_CUSTODY_RAW_PACKET_REVIEW.md). Code head `ce4fa08d8377b4dbf1634231598aa159d6af157c` passed the complete real-kernel job `111173559093` in regression run `37112699408`, including all six PASS records and `SYNTHETIC_RAW_PACKET_BOUNDARY_OK_NO_LIVE_APPLY`, on kernel `6.17.0-1022-azure`. Three local tests passed. The review records the EPERM assertion, direct-egress protocol matching and capability-free checkout-access corrections with their failed and successful evidence. Final-head workflow results and merge receipt are recorded in PR #177; require all five workflows successful before integration.

The design keeps raw capabilities out of the application worker. netdev ingress is not a confidentiality boundary against privileged ETH_P_ALL capture. These are synthetic packet/permission tests, not a live policy or DHCP authentication. Next compose restricted link rules with the actual DHCP lifecycle and existing administration assertions, then IPv6 control packets and fallback. First restricted maintenance installation/recovery remains unresolved. No phone operation or AWS/SSH/host mutation is requested; H2a and every runtime/provider/credential/prediction/DB-write/data-fetch/scheduler/report gate remain OFF.

## Previous completed slice: isolated DHCPv4 lifecycle passed; control-packet qualification remains

Updated: 2026-10-03 (Asia/Tokyo).

PR #175 merged at `06646c9b40726517e71da98bcd9509ebc1395b43` after all five workflows succeeded on head `59246821baf89b7bac3a7284e729ba29b52526f1`. The complete user dependency report is accepted below; no identical phone retry is needed.

PR #176 adds `tests/test_secret_custody_network_dhcp.py` and a mandatory Ubuntu CI job. It uses the actual networkd client in private network/mount/runtime/config namespaces and a synthetic DHCP server to test unicast renewal, broadcast rebinding to an alternate server, TCP transport continuity and lease expiry. See [scope and limitations](SECRET_CUSTODY_NETWORK_DHCP_REVIEW.md). Five local parser/namespace/runtime refusal tests pass. The actual lifecycle passed for code head `c7b040e515f72291168ffc42c2ac0bc9d8f9c22f` in regression run `37029254624`, DHCP job `110911645738`, on networkd `255.4-1ubuntu8.17`. Acquisition, unicast renewal with inet counters, alternate-server rebinding with existing/new administration transport, expiry/removal, negative reachability and cleanup all passed. Existing transition and independent recovery jobs also passed.

Resumed PR #176 after the user's pause. Previous head `796f6cf685022501408551008d2c2b1c4092e28a` failed initial acquisition in run `36945051624`, job `110645135668`; all other jobs/workflows passed. Ubuntu's downstream patch uses container detection for link initialization, unlike the upstream read-only-sysfs predicate previously assumed. The correction adds a marker only within verified private runtime storage and a real before/after container-detection check. It keeps isolation and lifecycle deadlines/assertions intact. The corrected real lifecycle now passes; this resolves the CI initialization incident in the measured fixture scope. Final-head workflow results and the merge receipt are recorded in PR #176; require all five workflows green before integration. No phone operation is needed.

Source review identified a material enforcement distinction: DHCP discovery/rebinding use raw packet sockets; bound renewal uses UDP. Only renewal asserts inet firewall counter passage. Passing this fixture must not be described as raw-frame filtering, DHCP authentication, address renumbering or complete maintenance qualification. The existing static transition/watchdog tests remain intact.

Next after this slice: address raw-socket/control-packet enforcement, then DHCPv6/RA/ND/PMTU and composition with fallback. Initial restricted maintenance installation and recovery from a wrong shared allowlist remain unresolved. No live firewall command, independent AWS/SSH access, new resource/IAM/inventory or credential is introduced. H2a and every runtime/provider/prediction/DB-write/data-fetch/scheduler/report gate remain inactive/OFF.

## Accepted live evidence and maintenance design: live dependencies observed; maintenance policy design

Updated: 2026-10-02 08:40 JST (Asia/Tokyo).

PR #174 merged at `1aa360b257da55d91facb857ff16b8be41a63d3e`. Its corrected head `e0ae01e3d92d84e4f127e997cd36bcd9b54a3864` passed all five workflows, rechecked on resumption. Regression run `36904707742` includes successful independent recovery job `110512222225` and local reader job `110512222345`. The earlier CI parser defect is historical and corrected.

The user has now supplied the complete requested dependency evidence: IMG_8937–IMG_8946, terminal captures at 08:17–08:32 JST. The immutable reader finished with `LOCAL_DEPENDENCIES_OBSERVED_WITH_UNRESOLVED_ITEMS_NO_MUTATION` and returned to the prompt. All selected sections were observed; `mutation=false`, `qualification=false`. This closes the request for that reader output. Do not ask for another identical run or more screenshots of these sections.

Sanitized observations: two interfaces; one DNS endpoint consistent with networkd's DHCPv4 provider data; zero fallback DNS entries; nine Chrony sources, one selected; nine IPv4 and seven IPv6 routes; DHCPv4 address/default-route configuration, DHCPv6 global address configuration, and an RA-derived IPv6 default route. One SSH endpoint tuple is caller-supplied/unverified. These are private user-supplied observations, not an independent Work host session, durable endpoint guarantees or packet-policy qualification. Exact addresses, allowlists and account identifiers stay out of public GitHub.

See [maintenance dependency design](SECRET_CUSTODY_NETWORK_MAINTENANCE_DESIGN.md) for the evidence-to-test matrix and initial-anchor decision. Next repository implementation is an isolated dynamic-address/control-packet fixture: real renewal/rebind, RA/ND and PMTU behavior with negative controls, preserving the existing transition/recovery tests. A UDP echo on DHCP ports does not qualify lease renewal. No live firewall installer or command is ready; the initial restricted maintenance anchor and recovery from a wrong shared allowlist remain unresolved.

H1 and measured H2a/H2b/H2c/H2d are complete. Keep H2a inactive and every runtime/provider/credential/prediction/data-fetch/scheduler/report gate OFF. No extra AWS inventory, IAM change, resource, secret, reboot or live firewall action follows from this evidence. Current unfiltered host state is not an allowed automatic fallback.

## Historical PR #174 preparation: independent recovery rehearsal and private dependency reader

Updated: 2026-10-02 (Asia/Tokyo).

PR #173 is merged at `180e590d1cede88f1326642170b73856d40deeea`. All five workflows passed for head `c321c22f89ec56c3432115993371535b0f9cc1dd`; regression run `36900487170`, job `110498113203`, completed all seven real IPv4/IPv6 transition markers with `SYNTHETIC_NETWORK_TRANSITION_OK_NO_LIVE_APPLY`. The initial fixture failure below was corrected before that successful run. No live firewall changed.

This follow-up implements a PID-1-supervised watchdog rehearsal in disposable network namespaces and a bounded local-only dependency reader. See [review and limits](SECRET_CUSTODY_NETWORK_RECOVERY_REVIEW.md). The real systemd test kills the applying child before/after apply, requires restricted fallback, verifies new/existing administration and qualification traffic in both families, and rejects unknown owned-table drift. Cooperative locks are not protection against arbitrary root writers. Independent recovery, initial anchor, persistence and live concurrency remain unqualified. Require the current PR's actual CI results before claiming this new rehearsal passed.

Initial PR #174 head `0396f275d7e14ef7672e9480284e34841685dd4d` passed the actual independent recovery job `110510991785` (run `36904340074`). The dependency job rejected the real DNS response format. The correction uses explicit D-Bus Properties.Get calls (honoring no-auto-start) and parses the returned variant array correctly, as verified against systemd v255 source. The original private reader is not approved for phone use. Require corrected-head CI; do not skip the failing assertion or ask the user to diagnose this CI-only defect.

The reader selects local interface/address/route/networkd/DNS/Chrony facts without external probes, raw config or credentials. Seven fixed commands are bounded by time/output; unavailable or unsupported sections remain unknown. Default output is counts only; `--private` emits selected private endpoints to the phone terminal. Keep those values out of public GitHub. A report is observation with unresolved items, never a completed policy or apply authorization.

Next: finish exact-head CI and read back the merge; then provide one immutable/hash-checked private reader command for the existing Termius session. This supplies missing dependency evidence, not a repeat of completed H1/H2/nft/UFW probes. Review that new private output before preparing actual profiles and an initial-anchor recovery proposal. Do not invent browser SSH ranges, DNS/NTP/renewal destinations or a recovery path. No live apply artifact exists yet and no firewall approval is requested now.

The user's 02:07–02:16 baseline below remains accepted. H1 and H2a/H2b/H2c/H2d are complete in their measured scopes. H2a remains inactive; all runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Work has no independent AWS/SSH connection. No third inventory run, IAM expansion, new resource, credential entry, production DB action, stress or reboot is authorized by this development step.

## Historical PR #173 preparation: network baseline and isolated transition rehearsal

Updated: 2026-10-02, carrying completed 02:07–02:16 JST evidence (Asia/Tokyo).

PR #172 is merged at `92a4dfed17a385a7045decebb661aa70619b0305`. The user's IMG_8930 at 02:07 shows the corrected observer at `78bbea96eec8d9c8228fe07c4e9ed71dbc1a3e2f`, SHA-256 `92a2f6a135c73d6ed972b61f203ee035e28c5ff7a473934b809041dac8aeb712`, succeeding with `H3_HOST_NETWORK_OBSERVED_NO_MUTATION`. Empty nft objects/base chains, zero exposed legacy IPv4 tables, IPv6 legacy tables not exposed, SSH wildcard listeners in both families, DNS/time-sync/DHCP-related listener ports and forwarding flags were observed. This supersedes the pending/correction boundary below; the failed PR #171 observer must not be retried.

IMG_8933–IMG_8935 at 02:12–02:13 show one visible SSH/TCP rule, a Custom IPv4 /32, browser SSH IPv4 enabled and browser IPv6 unchecked. Private addresses are omitted. Current screenshots do not re-show the port field; earlier configuration and successful Termius use TCP 22. The /32 is a public source address, not a unique-device guarantee; the browser checkbox does not disable host IPv6. Preserve the known manual/template difference. IMG_8936 at 02:16 shows UFW's own `Status: inactive`, despite its loaded/active/enabled systemd unit. Service state is not firewall state. These are user-supplied observations, not an independent Work AWS/SSH session or full effective-policy/reboot qualification.

The [transition proposal and rehearsal](SECRET_CUSTODY_NETWORK_TRANSITION_REVIEW.md) defines a default-deny maintenance fallback and an atomic qualification transition that preserves the same administration paths. It must remove qualification allowances including established flows, preserve unrelated tables, and stop on unknown owned-table drift. No fallback to unrestricted egress or world-open SSH is permitted. The initial maintenance anchor and independently supervised recovery remain unresolved live boundaries.

This development adds fixed synthetic nft profiles and mandatory isolated IPv4/IPv6 packet tests for connection preservation, positive/negative reachability, failed-transaction atomicity, restricted rollback and ownership drift. It is CI-only; it has no live apply path. Exact-head CI and merge evidence belong in the associated PR. Local Work cannot unshare; local guard tests alone do not qualify kernel behavior. TCP-22 echo tests are transport evidence, not authenticated SSH. No live policy was applied or existing phone command repeated.

Initial CI on `224f0be5add39e9cd27770993e8070f3785178b9` stopped while loading the unrelated fixture table, before packet assertions. No live host was involved. The one-line nested nft fixture was replaced with explicit statement/newline boundaries, and bounded synthetic-only command diagnostics were added. The original log did not include nft stderr; do not invent its exact parser message. Require the changed-code kernel run to succeed; no test is skipped or weakened.

Next: implement the bounded private dependency reader and initial-anchor recovery design, then the actual private profiles, independent watchdog and concurrency/ownership guard. Missing inputs include browser-SSH source-range lifecycle and independent recovery, effective upstream DNS/NTP, DHCP/IPv6 control/PMTU dependencies, exact bootstrap/runtime destinations and future policy ownership. Do not invent them, request secrets, repeat general baseline/probes, or widen egress to make tests pass. There is not yet a concrete live apply artifact to approve. H2a authorization does not imply firewall apply.

H1, corrected H2a install and measured H2b/H2c/H2d results remain complete. The H2a placeholder stays inactive. All runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Host/cloud hardening, persistence, local IPC/syscall/application capacity, TLS and full controller/reboot recovery remain incomplete. Host remains untrusted / no-secret.

## Historical boundary at 01:56 JST: readback failure and parser correction

Updated: 2026-10-02 01:56 JST evidence (Asia/Tokyo).

The user's IMG_8929 shows the immutable PR #171 observer at commit `60b435c8e2e04d9dc14bbc5070e867cdfa8ad996`, SHA-256 `d94175d03b18fa167fa98b76379d62ef8df178e4a7fe21e899437a93a08ef572`, ending with `STOP NETWORK_READBACK_UNAVAILABLE` and `RESULT H3_NETWORK_OBSERVATION_INCOMPLETE_NO_MUTATION`, followed by the prompt. This is an unsuccessful host observation. No host facts were emitted; effective network policy remains unknown. The screenshot cannot identify the failed stage or exception type. Do not repeat that unchanged command or claim a host configuration failure.

A concrete observer defect is reproduced locally: `ss` can render scoped IPv6 as `[fe80::1234]%interface:546`. The old `strip("[]").split("%", 1)[0]` leaves a closing bracket and raises ValueError. The iproute2 v6.1.0 source brackets the address before appending the interface scope, confirming that this is a legitimate representation. The original tests exercised only scope inside brackets and real unscoped loopback sockets. This is a verified parser defect and a plausible explanation of the live STOP, **not yet a confirmed live root cause**.

The correction supports both bracket/scope placements and scoped wildcards, while rejecting malformed brackets, duplicate/empty zones and invalid addresses. It also attributes read/parse failures to fixed stage and category codes without exception text, raw addresses or command diagnostics. No read is skipped; facts stay buffered until complete success. The fixed read-only commands, byte/time bounds, no-mutation scope and all disabled gates remain unchanged.

Sixteen offline tests cover the correction and error attribution. Mandatory existing CI adds an actual scope-bearing IPv6 UDP socket inside its disposable isolated network namespace, alongside nft and IPv4/IPv6 checks. All five workflows must pass on the correction commit before merge/readback and a replacement immutable phone command. CI success alone does not resolve the live incident. One changed-code phone run should either complete with `H3_HOST_NETWORK_OBSERVED_NO_MUTATION` or provide a new fixed STOP/STAGE pair; diagnose that pair rather than repeating unchanged commands.

H1, H2a recovery/installation, H2b, H2c and the ten H2d PASS records at 01:38 JST remain completed in their measured scopes (PR #170). Do not repeat provisioning, login/key/keyboard setup, rollback/apply or those completed probes. The H2a placeholder remains inactive. Work has no independent host/AWS session and the user supplies the live terminal evidence.

After one successful host readback, inspect the current Lightsail IPv4 and IPv6 firewall entries from the existing phone session. The earlier SSH edit screenshots did not expose the complete saved policy. Unknown/nonempty host rules require private review; do not flush or replace them. No IAM expansion, new inventory workflow dispatch, firewall change, stress or reboot follows from this correction. Preserve phone SSH and the recorded manual/template difference.

See [network readback review](SECRET_CUSTODY_HOST_NETWORK_READBACK_REVIEW.md). All runtime/provider/credential/prediction/data-fetch/scheduler/report gates remain OFF. Local IPC/syscall, application capacity, complete host/cloud ingress and default-deny egress, TLS, whole-controller and reboot recovery qualification remain pending. The host stays untrusted/no-secret.

## Historical failed H2a attempt and correction: H2a authorized; first apply failed; correction under validation

Updated: 2026-10-02 00:06 JST evidence (Asia/Tokyo).

The user explicitly said `適用して` at 2026-10-01 23:56:43 JST after the exact H2a identity/files/inactive-unit scope was presented. That authorization remains valid for diagnosis, bounded recovery and corrected application within the same scope; **do not ask for the same permission again**. It does not activate runtime, provider, credentials, networking changes or any other gate.

PR #166 merged offline preparation. The user's first live command pinned commit `5cc75aa40523e405ccd0a6515386d3a41eeb886d` and script SHA-256 `50a92a2b0c4585cc965a91faf737d81d337408573cf2668dd26dc49a825473e1`. At 00:00 JST it returned `STOP HOST_COMMAND_FAILED` / `RESULT NO_RUNTIME_AUTHORIZED_DO_NOT_RETRY_APPLY`. This was **not a successful installation**.

At 00:06 JST screenshot IMG_8924 confirmed: the receipt directory exists; the reserved code/config directories and unit file are absent; dedicated user/group lookups each return 2; systemd reports not-found/inactive, empty fragment/drop-ins/unit-file state, and show exit 0. Receipt contents have not independently been read back. The failure is consistent with the invalid `useradd --key CREATE_MAIL_SPOOL=no` argument found in our implementation. The prior mocked account tests missed the real parser boundary. The correction removes that invalid login.defs override; system accounts already skip mail creation. Fixed stage-specific command errors retain diagnostic privacy.

[H2a review and recovery](SECRET_CUSTODY_HOST_H2A_REVIEW.md) describes the defect, primary source and new real CLI test: installed Ubuntu 24.04 account tools target only a disposable chroot database, while the manager/process adapter remains synthetic. It reproduces the invalid command, checks receipt-only partial state, then exercises bounded rollback, corrected apply and verification. Require this CI step and existing regression checks to pass on the exact correction commit before merge or phone execution. Local Work has only UID/GID 0 and rejects the account CLI audit interface; it cannot substitute for this CI gate.

After CI/merge, use an immutable, hash-checked corrected script. Run its existing ownership-checked rollback once, then apply only if rollback succeeds; verify afterwards. Preserve the existing receipt schema for compatibility. No blind recursive removal, unchanged retry, approval bypass, password/key request or firewall widening. Any new STOP requires diagnosis. Successful offline tests are not live success; await the phone result `INSTALLED_DISABLED_NOT_QUALIFIED` before recording installation.

The candidate remains **untrusted / no-secret**; H2-H7 effective qualification and all runtime/credential gates remain pending/OFF. Work has no independently verified AWS/SSH session. The user's Termius connection works. Do not repeat provisioning, cost approval, IAM/bootstrap, inventory, key import, keyboard setup or H1.

## Previous milestone: creation and H1 completed

Updated: 2026-10-01 23:23 JST (Asia/Tokyo).

The user's phone screenshots confirm completion of the approved single Tokyo candidate and attached static IPv4, successful native Termius SSH login, command execution and the read-only H1 result `PREFLIGHT_OK_NO_MUTATION` with zero warnings/failures. See [creation and H1 evidence](SECRET_CUSTODY_HOST_H1_EVIDENCE.md) for the sanitized chronology, immutable script identity and limits.

The host remains **untrusted / no-secret**. H2-H7, workload capacity, effective sandbox/default-deny egress, static egress, TLS and reboot/recovery qualification are pending. H2a authorization, correction and successful installation are recorded above; effective qualification remains pending. No runtime/provider activation or custody secret use follows from H1.

Do not repeat creation, its cost approval, IAM/bootstrap, inventory, phone browser keyboard attempts, key import or H1 just to resume. The existing phone Termius path works. Work has no independently verified AWS/host session; use existing evidence and connectors within their actual permissions.

The phone administration change added one observed-source IPv4 /32 for SSH while preserving browser SSH IPv4 access. The 02:12–02:13 saved-rule UI evidence above supersedes the earlier pending readback; effective reachability remains unqualified. The original CloudFormation template still describes browser-only ingress. Review this manual difference before any stack update; keep IPs/key material private.

The dated sections below are historical observations at their stated stage. Their earlier zero-resource counts and untested-login statements are superseded by the evidence above, not instructions to repeat those operations.

## Scoped creation authorization (historical; operation now complete) — 2026-10-01 20:56:49 JST

The user replied `続けて` directly to the explicit approval request for the presented candidate file, one Tokyo Ubuntu 24.04 / 1 GB / 2 vCPU / 40 GB instance, USD 7/month base bundle (tax/transfer overage separate), one attached static IPv4, browser-SSH-only initial ingress and retention of successfully created resources on failure. In that conversational context, this authorizes proceeding with that exact one-candidate creation. Do not ask the same cost/configuration question again.

The approved template remains blob `4c8913e893ece7ed95e35827af6bf9406783e59e`. Its default and repository metadata remain non-authorizing; the live parameter may now be set to `ONE_CANDIDATE_USD7_APPROVED` for this approved operation. Proposed inputs remain stack `keirin-ai-custody-h1`, instance `keirin-custody-h1`, static IP `keirin-custody-h1-ip`, zone `ap-northeast-1a`, blueprint `ubuntu_24_04`, bundle `micro_3_0`, and existing default key `LightsailDefaultKeyPair`.

Authorization is not completion. No CREATE change set, instance, static IP or SSH login has been performed by this turn. The next required evidence is the authenticated intended-account/Tokyo context, absent proposed stack name, current selected blueprint/bundle and the actual resolved change set with exactly two Add actions. Verify preserve-successful-resources and deletion-policy behavior before Execute. A matching actual proposal can proceed under the existing approval; a different scope, cost, account, ingress or failure behavior requires resolving that difference before execution.

The usable AWS session is on the user's phone; Work has no verified AWS control-plane session and the existing GitHub role cannot provision. Guide the existing phone session without retrying the known Work login failure. Do not repeat inventory/bootstrap, expand IAM, create/download keys or introduce extra resources. Hosted execution, real credentials, hardening, Supabase changes and production prediction remain outside this authorization.

## Creation configuration and public-price review — 2026-10-01 (before approval)

At the earlier offline review, the paid scope was fully specified but not yet authorized or executed; subsequent authorization is recorded above. AWS's [current public pricing](https://aws.amazon.com/lightsail/pricing/) was rechecked on 2026-10-01: Linux/Unix with public IPv4, 1 GB memory, 2 vCPU, 40 GB disk and 2 TB transfer is USD 7/month. The [billing FAQ](https://docs.aws.amazon.com/en_en/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html) confirms no additional static-IP charge while attached, and USD 0.005/hour when unattached for more than one hour. Taxes, currency conversion and transfer overage are outside the bundle ceiling; no free-trial credit is assumed.

The exact candidate remains unchanged from main `16c31f91a4205991c28ac2a33e8c64678a2a4f29`, blob `4c8913e893ece7ed95e35827af6bf9406783e59e`. Its two resources are CustodyCandidate and CustodyStaticIp. The proposed new stack name is `keirin-ai-custody-h1`; stack-name absence and independent account identity are still unverified. The selected zone is `ap-northeast-1a` and the existing key parameter is `LightsailDefaultKeyPair`, observed by inventory run #2. Blueprint/bundle availability evidence remains the 18:28 catalog run; public-price verification is not a new AWS API observation.

At this earlier review point, the cost decision was still pending and the acknowledgement remained NOT_AUTHORIZED. The subsequent 20:56:49 JST authorization is recorded above. The actual CREATE change set and account/stack checks remain pending; do not confuse approval with execution or GitHub authentication with AWS access.

## Corrected inventory verified on 2026-10-01 (historical, before creation)

At 20:37:39 JST the user explicitly authorized one additional corrected read-only inventory run. [Inventory run #2](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36856726931) was dispatched exactly once from main `de7cd0b97bb009f5f9394512f94bf5be33d5251b` (PR #161 merged). Job `110350863079` completed successfully, including OIDC authentication and all three inventory reads. The version 2 result was emitted at 11:39:38 UTC / 20:39:38 JST.

| Observation | Verified result |
| --- | --- |
| Region | ap-northeast-1 |
| Instances / static IPs / key pairs | 0 / 0 / 1 |
| Proposed instance / static-IP name collisions | false / false |
| Tokyo default key present | true |
| Review reasons | empty |
| Key login / independent account identity / stack-name inventory | Not verified |
| Live creation authorized | false |

The corrected default-key classifier is now verified against AWS metadata. This resolves the earlier default-key identity uncertainty; version 1's absence flag remains invalid historical evidence. No key was created or downloaded and no private key material was read. Metadata presence does not verify SSH login.

Both authorized inventory runs are complete. Do not dispatch a third run or repeat the IAM/bootstrap setup automatically. Next, verify the intended account, proposed stack name and current blueprint/bundle/price before preparing the exact two-resource CREATE change set for separate approval. No paid host/IP creation, provisioning permission, runtime activation or Supabase change was authorized by this inventory execution.

## Concrete host proposal prepared offline (historical)

The user authorized the exact Tokyo GetInstances/GetStaticIps/GetKeyPairs IAM update plus one inventory run on 2026-10-01. The reviewed single-role, non-replacement change set preserved trust and all other role properties. CloudFormation reached UPDATE_COMPLETE at 19:52:49 JST. Separate post-update IAM policy/trust read-back was not performed.

[Inventory run #1](https://github.com/bzlove178100/-keirin-ai-web/actions/runs/36852494617) succeeded on main `a713b6d57199975e13c32edd84cee9d2ed2da602` at 19:59:23 JST: Tokyo instances 0, static IPs 0, key pairs 1; both proposed name-collision flags false. This consumed the first one-run authorization; the separately authorized corrected run #2 is recorded above.

Version 1 used a download filename stem for the default-key match; its false default-key flag/reason remains invalid as absence evidence. Version 2 corrected the API name to `LightsailDefaultKeyPair` with independent literal regression fixtures, passed 33 local tests and all five applicable CI workflows, and is now verified by run #2. The existing Tokyo default key was observed without an IAM expansion. Full evidence and retry/stop conditions are in `AWS_LIGHTSAIL_INVENTORY_REVIEW.md` and `WORK_RESUME.md`.

`review/aws_lightsail_candidate.json` proposes exactly one Tokyo Ubuntu 24.04 LTS / micro_3_0 candidate and one attached static IPv4. The planned names are keirin-custody-h1 and keirin-custody-h1-ip, not verified existing resources. The USD 7/month figure is the observed bundle price, subject to a fresh pre-execution price check.

The template rejects its default acknowledgement, wrong region or mismatching expected account. It requires an existing Tokyo Lightsail key pair, requests only browser-SSH source alias ingress, embeds no launch script/credentials and retains both resources on stack removal. The review explains failure-retention costs, change-set review, actual firewall verification and separately authorized cleanup. Local cfn-lint 1.57.1 passed with no findings and 10 candidate safety-contract tests passed; the offline CI repeats these checks.

The host proposal remains offline: no host, static IP or key was created. The authorized IAM update and both inventory runs are complete. Default-key identity is resolved; independent account/stack checks and deployment permissions remain unresolved. The role has six read actions (three catalog plus three Tokyo inventory), with no provisioning permission. Read `SECRET_CUSTODY_HOST_PROVISIONING_REVIEW.md` for the subsequent execution sequence.

## Product direction

`AI_AGENT_REQUIREMENTS.md` is authoritative. The target is a broad autonomous AI agent for research, text/image/video/code generation, learning/evaluation, task execution, recovery and reporting. Keirin AI is the first major execution target, not the only scope.

## Fixed safety state

Unless a new, specific boundary is explicitly authorized:

- deployed hosted task/provider execution: **OFF**;
- production prediction: **OFF**;
- keirin prediction DB writes: **OFF**;
- automatic external keirin race-data fetching: **OFF**;
- provider generation/write bindings: **unbound**;
- report delivery / live 21:00 scheduling: **OFF / unconfigured**;
- scheduler / recurrence: **OFF**;
- no real provider/OAuth refresh exchange is connected;
- no real provider credential or refresh secret is stored in the custody project;
- no live secret-store schema has been applied to the custody project;
- one paid candidate and attached static IPv4 exist; H1 passed, full hardening is pending.

Agent-only checkpoint/activity persistence and queue coordination in `keirin-ai-staging` were separately authorized. Exact-task lease acquisition is deployed. No always-on worker is active.

## Verified repository state

The live observation ran against main `f08bfbb3ed59478653f9055757b138e7c0141dcf` (PR #157 merged). PR #157 head `e21f161075908fac10e938a56c11ab6440640cc5` passed all five applicable workflows: collection progress UI regression, agent runtime read-only smoke, aws observation offline contract, keirin-ai regression and agent checkpoint PostgreSQL contract.

PR #151 introduced the reviewed OIDC read-only observation package; #152 added catalog-error privacy and #153 added offline CloudFormation template validation. The live run is separate evidence that the deployed OIDC role and catalog reads worked.

Resolve current main from GitHub on the next resumption; embedded SHAs are historical evidence, not a permanently current branch pointer. The PostgreSQL contract retains the application stack, lease/trust/hostname, row-lock/deadline, TLS/restart recovery and audit-redaction checks.

## Runtime staging project

Existing runtime/checkpoint staging remains `keirin-ai-staging` in `ap-northeast-1`. Provider/runtime execution gates, prediction DB writes and external race-data fetching remain OFF.

Do not repurpose this shared application staging Vault for real agent refresh-secret custody. The 2026-09-30 Phase A inventory confirmed `service_role` can directly access decrypted Vault data in that project.

## Secret-custody project

A dedicated `keirin-ai-secret-custody` project exists in `ap-northeast-1` (Tokyo). The organization plan remains Free and the project-creation cost check returned 0 per month. The project was `ACTIVE_HEALTHY` at the last live check.

No paid add-on, database password, Vault secret, binding row, provider credential, Edge Function or hosted worker has been created for the custody path.

## C0 / C1 complete boundary

`SECRET_CUSTODY_C0_C1_EVIDENCE.md` records the dedicated-project provisioning and catalog-only inventory. The observed database is PostgreSQL 17.6 family, primary, with `supabase_vault` 0.3.1. Proposed private roles/schema were absent. No secret row/value/name/description or provider credential was read and no DDL/DML was submitted during C1.

Project isolation, not revocation of Supabase-managed platform privileges, is the selected blast-radius boundary.

## C2 review artifacts complete

PR #138 added `SECRET_CUSTODY_C2_REVIEW.md`, the candidate/rollback SQL outside `supabase/migrations`, and regression guards. The reviewed model retains the dedicated LOGIN host / NOLOGIN broker split, private metadata schema, forced RLS, exact read/CAS functions, no runtime `vault.create_secret` capability, no password, no binding row and no secret provisioning.

**C2 has not been applied to Supabase.**

## Management-plane preflight

PR #139 added `SECRET_CUSTODY_MANAGEMENT_PLANE_PREFLIGHT.md` with three hard gates:

1. Data API disabled;
2. Postgres SSL enforcement enabled;
3. database/pooler network restrictions limited to the approved hardened-host egress CIDR set.

Their authoritative live state remains unknown until verified through the Dashboard or an appropriately scoped Management API path. Unavailable/denied reads remain unknown; no world-open placeholder CIDR is accepted; management changes are not batched with C2 DDL.

## Hardened-host candidate

PR #140 selected Amazon Lightsail Linux/Unix Micro 1 GB in Tokyo (`ap-northeast-1`) as the first later qualification candidate: 2 vCPU, 1 GB RAM, 40 GB SSD, 2 TB transfer, reviewed maximum bundle price USD 7/month, with an attached static IPv4.

The provider boundary was re-checked on 2026-10-01. Lightsail remains the first candidate: current public documentation still shows Tokyo support and the USD 7 Micro 1 GB public-IPv4 bundle shape. Railway and Render do not currently provide a lower-friction equivalent for this design's Tokyo + stable-egress requirement, and DigitalOcean has no Tokyo region.

AWS account bootstrap is now complete. The user created the Proof of Concept account, upgraded it to the paid usage model, activated advanced features, and created the `ai-agent-team` management boundary. A USD 10 monthly AWS Budget exists and its charge-type filter excludes Credit and Refund so AWS usage remains visible while promotional credits are available. The single candidate and attached static IPv4 have now been created; H1 passed. If 1 GB proves insufficient, do not weaken safeguards to preserve the USD 7 target.

## Host safety reviews complete

PR #141 added the read-only H0-H7 hardening qualification review and offline `review/lightsail_host_preflight.sh`. PR #142 added the fail-closed provisioning review and `review/lightsail_provisioning_manifest.template.json` with `authorized_for_live_create=false`. PR #144 added the declarative hardening package review, offline validator and regression guards with `authorized_for_live_apply=false`. PR #145 added fail-closed recovery/rollback review artifacts with `authorized_for_live_recovery=false`. PR #146 added the read-only AWS control-plane observation review and sanitized observation template with `authorized_for_live_create=false`.

The created candidate remains **untrusted / no-secret** after H1. Passing repository review or host hardening by itself does not authorize C2 DDL or credential use.

The hardening package is declarative data, not an executable host mutation script. The recovery plan keeps the runtime disabled and host no-secret on preflight, hardening, network/TLS, capacity or reboot/recovery failure. Automatic AWS destruction/resize/reboot/snapshot/replacement, automatic firewall relaxation/egress widening, protected Supabase/Vault/provider/prediction/race-data mutations, insecure TLS/plaintext fallback and credential introduction during recovery are forbidden by the reviewed contracts.

## AWS GitHub OIDC read-only automation

`AWS_GITHUB_OIDC_READONLY_OBSERVATION.md`, `review/aws_github_oidc_readonly_role.yaml`, `review/aws_lightsail_readonly_observation.sh` and the manual-dispatch workflow define the short-lived OIDC observation path. The deployed role was successfully assumed in run #1 and the three catalog calls passed.

The reviewed role is restricted to the immutable GitHub owner/repository IDs, branch main, audience sts.amazonaws.com, and the three catalog actions `GetRegions`, `GetBlueprints`, `GetBundles`. The separately approved update added only Tokyo `GetInstances`, `GetStaticIps`, `GetKeyPairs`. It has no Lightsail mutation permission. Do not widen it for provisioning without a separate review/authorization.

CloudFormation/SCP and browser/app troubleshooting are completed history for this boundary. Do not repeat failed CloudShell/mobile-editor paths or recreate the stack/secret. Offline checks still enforce exact Tokyo, active identifiable Ubuntu LTS, the matching bundle shape/public IPv4 and a finite nonnegative price at or below USD 7. Passing catalog reads does not verify allocation, host safety or provisioning permissions.

## AWS control-plane observation review complete

`SECRET_CUSTODY_AWS_CONTROL_PLANE_OBSERVATION_REVIEW.md` and `review/lightsail_control_plane_observation.template.json` define the reviewed observation boundary. The template fixes the expected region/host shape/price ceiling while leaving every live observation value unset. It keeps `authorized_for_live_create=false`, rejects automatic size/region substitution, forbids sensitive account/key/IP/credential material and keeps every runtime/provider/prediction gate disabled.

The initial authenticated catalog observation passed; see the verified values above. Static IPv4 creation/attachment was subsequently observed through the phone console; see the H1 evidence. Unknown, ambiguous or mismatching future values fail closed. Passing observation still requires a separate explicit live-provision instruction before any Lightsail instance or static IP is created.

## Cost / availability boundary

Keep the Supabase Free project for architecture, review and no-secret qualification while it remains operationally suitable. Free is not approved for real always-on credential custody because low-activity Free projects can be paused. Before C4 real credential activation, require either a paid-plan availability boundary or an equivalent separately reviewed solution.

Exactly one USD 7/month candidate has been created under the scoped approval. Continue qualification with synthetic/no-secret inputs; a rejection requires a separately reviewed and authorized cleanup decision. Do not keep multiple paid hosts running for convenience.

## Next work / next boundary

1. Creation, native SSH and read-only H1 are complete. Use `SECRET_CUSTODY_HOST_H1_EVIDENCE.md`; do not recreate or re-run setup without a changed condition.
2. H2a installation and measured H2b/H2c/H2d verification are complete. H3 dependency observation is also complete; follow the current maintenance design above, not historical phone-run instructions.
3. Confirm complete relevant current firewall rules before H3/H4; preserve the bounded phone/browser administration path. The manual /32 source differs from the original browser-only template.
4. Qualify effective sandbox/resource limits, no-secret capacity, default-deny egress, verified static egress, TLS verify-full and reboot/recovery before introducing custody credentials.
5. Use verified hardened-host egress for separately authorized Supabase network restrictions; verify Data API disabled and SSL enforcement, changing each separately only if required.
6. Require fresh explicit authorization for C2 live DDL, clearly synthetic material for C3, and a separate availability/cost decision and authorization for C4 real credentials.

Live hosted execution, long-lived worker, scheduler/recurrence, provider generation/write, production prediction, prediction DB writes, race-data auto-fetch and report delivery remain disabled.

## 21:00 report requirement

The product requirement remains daily 21:00 Asia/Tokyo reporting of daily sales, monthly sales and activity. Sales source, accounting rules and delivery destination remain unresolved. Missing sales values must never be shown as zero. Live report delivery/scheduling remains disabled.

## Constraints

Do not commit private race histories, prediction snapshots, model artifacts, credentials, private file identifiers, host allowlists, provider account identifiers or personal data. Prefer current `main`, current CI, deployed metadata and direct bounded checks over older handoff notes.

## Catalog command error privacy (2026-10-01, historical validation)

PR #152 is merged (`cb32f7f2351536cfef26ac0702252aeb8e593574`). The follow-up suppresses raw stderr from all three catalog AWS CLI commands, including warnings on successful commands. Failures report only the fixed operation name and exit status, preserve the original nonzero status, and stop before subsequent commands or a success report. Partial stdout remains in the temporary directory and is removed on exit. This intentionally sacrifices raw diagnostic detail to avoid publishing account IDs or role ARNs. It does not change credential-action logging or AWS CLI internal retry behavior.

Local shell syntax validation and 58 offline tests passed, including synthetic private stderr/partial-stdout canaries at each of the three failure points. No real AWS calls were made during that historical validation. Later bootstrap and live observation passed, as recorded above. The historical pending-policy/access incident is no longer the current boundary.

## OIDC template preflight (2026-10-01, historical validation)

Verified base: PR #153 merged, main `c3fd6d1488f1b4c8113ca652ca7dd109c15413d4`; its five exact-head CI workflows succeeded. The unchanged OIDC CloudFormation template passed local `cfn-lint==1.57.1` for Tokyo with no findings and no AWS credentials in the validation process environment. The offline CI now repeats that template check alongside the existing catalog tests. This is local schema validation, not AWS account/change-set validation or deployment.

The SCP change and OIDC bootstrap were subsequently completed, and live run #1 succeeded. Those later observations supersede the old browser/session blocker. Offline work itself did not verify live AWS state. The successful live run also reported checkout Node.js deprecation and ubuntu-latest migration notices; these remain nonblocking maintenance follow-ups.
