# FINAL 5：第二段階AIの合成専用試作

基準main d069ab9b6adcf9585954a5bae7be7df0546e473c、直前#267
20e4ba0cfaf6058e0901350943309df17e2712acは全7CI/回帰47件/Python80/新規Chrome2成功。
既存の確率順基準・結果診断を維持し、独立したオフライン学習/推論CLIを追加する。
依存#266 ae2658f7acadb597bf67217c165afe722a651587は変更しない。

## 今回できることと位置付け

保存済み合成ML履歴から、既存5カテゴリ各最大3点の候補を学習で最大5点へ絞る。
LightGBM binary分類器で「候補が確定3連単と一致するか」を学習し、その未校正スコア順に選ぶ。
これは比較可能な試作のための技術上の目的変数であり、利用者が承認した商品アルゴリズムではない。
展開整合性、根拠の強さ、確信度、分散、オッズ価値・利益を学習したとの主張はしない。
実会員画面、既存Workbenchの予測/結果診断API、第一段階モデルを変更・自動置換しない。

## 入力と特徴

`ml.final_five_ranker` は明示的syntheticモードだけ受け付ける。
既存ML履歴検証・選択を再利用し、保留、通常結果競合、最新同時刻予測競合、不正履歴を除外。
同じレースの最新有効snapshotを1件採用し、重複や古い保存でサンプル数を増やさない。
不正記録の除外は他の有効記録の真正性を保証しない。未提供の保留や別保存先の検知はしない。
保留訂正の通常履歴/学習への反映は引き続き未接続。

固定した特徴は未校正確率、元候補内の確率順位、元カテゴリ内順位、7/9車数、候補数、
5カテゴリのone-hot。カテゴリは予測時の既知odds帯で既に決まった元出力を保持する。
結果、払戻odds、結果確認時刻、race ID、日付、snapshot digestは特徴にしない。
odds値自体を特徴にせず、未知oddsの補完や確率×oddsの金銭EVを作らない。
全210/504表から候補を追加せず、5点未満も補完しない。
同一スコアは元確率降順、さらに車番tuple昇順。元確率/odds/カテゴリ/カテゴリ順位を保持する。
ranking_scoreは未校正の比較スコアであり、的中確率・確信度とは表示しない。

## 時系列分離と比較

呼出し時にtimezone付きcutoffを1つ指定する。ランダム分割・自動cutoff選択をしない。
学習は予測保存時刻と結果確認時刻の両方がcutoffより前のレースだけ。
予測は古くても結果がcutoff以降なら学習から除外する。cutoffちょうどの予測は検証側。
timezone表記差は同じ時点として比較する。
最低5つの異なる学習予測時刻、正負両ラベル、検証レース1件以上を技術上の実行条件とする。
これは統計的十分性ではない。不足時は学習せず、理由付きreport、model=null、CLI exit 2。

候補内に正解がない学習レースも全候補negativeとして保持し、都合のよい的中例だけにしない。
各レースの候補weight合計は1。3点と15点のレースで学習の総weightを増減させない。
固定40round・固定parameterで1回学習。検証ラベルによる早期停止/調整/モデル選択はしない。
モデル保存内容を再読込してから検証する。新たな推論も学習済みrace IDとcutoff前を拒否する。

比較対象は既存の確率順最大5点。同じsnapshot、同じ候補集合、同じ選定点数で照合する。
7/9車×3/4/5点の6群別に対象数、両方的中/試作のみ/基準のみ/両方不的中、元候補外を表示。
0件の率はnull、異なる点数を混ぜた全体的中率や金銭収益は出さない。
学習manifestは学習レースだけ。検証結果を変えてもモデル/選定は変わらず、比較結果だけが変わる。

評価名はretrospective_second_stage_chronological_holdout。あくまで第二段階の時系列分離であり、
第一段階モデルの実際の学習入力独立性は確認できない。元snapshotのtrained_at検証を超えた保証はしない。
元履歴のローカル時刻/合成申告/digestは独立した証明ではない。全体の前向き実績や実精度とは扱わない。
cutoffや目的変数を結果を見ながら何度も変えた場合の汚染を検知する台帳も未実装。

## CLIと保存

```sh
python -m ml.final_five_ranker fit synthetic-ml-histories.json \
  --cutoff 2026-10-24T10:00:00+09:00 --synthetic --output experiment.json
python -m ml.final_five_ranker predict experiment.json synthetic-snapshot.json \
  --synthetic --output challenger-picks.json
```

fit入力はML通常/保留履歴のJSON配列。WorkbenchセッションenvelopeやPhase32履歴は別形式。
上記日付は例であり、実行時に利用者が対象fixtureに合う境界を指定する。
出力はモデルとreportを含む1つのJSON。モデルはLightGBM native textで、pickleを使わない。
特徴順/方式/parameters/停止条件/学習manifest/全体SHA-256を検査し、異なる仕様・破損を拒否する。
学習履歴のhashはnormalの省略/明示を正規化し、同値な重複の入力順でモデルIDを変えない。
SHA-256は署名ではなく、再作成できる者の改ざん防止や出所・権利の証明ではない。
既存出力の上書きを拒否し、入力ファイル/Workbench保存物を変更しない。
CLIのファイル出力はWorkBenchの自動保存/電源断復旧契約を継承しない。モデルの自動配備や昇格もない。
生成モデル/実験結果はローカルの試験用であり、リポジトリへモデル本体をcommitしない。

## 検証と残件

新規Python9試験：実LightGBM学習→保存/別プロセス再読込→推論、7/9車と3/4/5点の同点数比較、
正確な分母/0件null、学習ラベルの効果、候補外negative、検証ラベル/払戻oddsからの学習/選定独立、
境界ちょうど/結果到着遅れ/timezone、保留/競合/不正/重複/最新/順序、学習不足時の停止、
モデル破損/特徴/停止条件の改変、既知レース/過去予測拒否、CLI上書き拒否と入力不変を検証する。
fixtureは意図的に簡単な生成パターン。的中差は実装動作の検証に限り、実力向上の証拠にしない。
画面変更はないため新規Chromeケースは追加しない。既存成功Chrome証拠を再利用し、変更headのCIは#267へ記録。

残件：商品としての目的変数/評価軸/受入基準、第一段階も含む独立データ検証、実用的な特徴、
再試行/選択汚染の記録、画面とモデル管理への接続、DREAM TICKET、会員/商品/課金、実データ受入。
本試作の技術検証を商品FINAL 5完成やサブスク開始と扱わない。
KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFF。API20/12/11/7は記録値。
マージ/公開/Function配備は未承認。現行原本保存/段階backend受入/復元は#266本文を厳守する。

## 保存済みモデルの画面接続（2026-10-21、未公開候補）

c3395104cab7debc6c6b77f2096a1327024c1f5bの全7系統CI/回帰47件は成功。
runtime39544435731/job119039280176で同一head verified=true。確定証拠は#267本文。
その後の本候補は、学習済みモデルを明示指定した場合だけ合成Workbenchから比較表示する。

```sh
python -m ml.synthetic_workbench --synthetic --port 8765 \
  --state-dir /absolute/path/outside/repository/state \
  --final-five-experiment /absolute/path/outside/repository/experiment.json
```

`experiment.json` は上記fit CLIの出力。ファイルは起動時に一度だけ読み、既存のモデル仕様/
特徴順/停止条件/manifest/hash/native textを検証してプロセス内へ固定する。
通常ファイル/単一リンク/8 MiB上限を要求し、symlink/FIFO/破損/学習不足model=nullは起動拒否。
モデル検証は状態ディレクトリ・lock作成前に行う。指定なしなら既存機能は従来どおり起動する。
既存reportは信用・表示・推論に使用しない。モデルの検証は独立した出所や学習権利の証明ではない。

既存の合成予測画面から「第二段階AIと基準を合成比較」を開く。
`GET /api/final-five-challenger/<snapshot-id>` と `/final-five-challenger/<snapshot-id>` は
同一origin/loopback/CSP/no-storeを共有する。任意query/path/model指定、upload/fit/切替APIはない。
既存snapshotを完全検証し、同じ最大15候補を確率順基準と保存済みモデルでそれぞれ最大5点へ絞る。
7/9車・3/4/5点の不足、元確率/odds/カテゴリ/順位、未校正比較スコア、モデルhashとcutoffを表示。
モデル本文・学習manifest・元全確率表・結果・実験reportはブラウザへ返さない。

モデル指定なし、学習に使用済みのrace ID、cutoffより前の予測、同じ合成予測セッション内の
ML保留と一致するレースはblockedでAI候補なし。確率順基準は表示する。未知対象は404、
不正snapshotは409。同一origin違反は403。モデル未指定で自動学習したり基準をAI出力へ代用しない。
この保留検査は現在の予測セッションに存在するML保留だけで、別の確認一式/別保存先にある
未提供保留の横断検知ではない。保留訂正や学習可能化を行わない。

再確認時は両列を消去し、遅い旧応答を破棄する。通信失敗・不正応答でも候補とモデル表示を消す。
保存停止中は最後の確認済みメモリであることを明示。表示で予測/結果/確認一式を書き換えない。
ページ閲覧からの第一・第二段階の再学習、モデル昇格、課金はない。
モデルファイルを外部変更しても稼働中の固定モデルは変わらない。変更適用は明示的な再起動のみ。
再起動時にファイルが不正なら起動拒否し、旧モデルへ黙って戻らない。モデル指定なしで再開した
場合はAI候補なし。モデルの自動保存/選択/切替/履歴台帳・選定結果の永続保存は今回の範囲外。

新規Python/API6試験と変更が影響する既存基準6試験がローカル成功。
初回の新規試験は2成功/4エラー。境界前fixtureを1日前へずらして第一段階trained_atより前に
したため既存の時刻検査で拒否された。学習対象から除いたday6を使うfixtureへ修正し6/6成功。
製品の時刻検査は変更していない。JS構文/diff check成功。
新Chrome2ケース（390/1280幅・各7/9車×3/4/5点）を既存ML CIへ追加。
画面/新head CIの確定結果はPR本文を正とし、記録だけでcommit/CIを再起動しない。

商品選定規則・第一段階を含む独立評価・実験選択汚染の記録・実用特徴・DREAM・会員/課金・
実データ受入は未完。本比較画面は合成専用で、商品受入・実精度/利益・本番完成を意味しない。
API20/12/11/7記録値、HOLD/OFF、#266の将来の現行原本保存/段階backend受入/復元条件を維持。
#266/#267のマージ・Web公開・Function配備は未承認。

## モデルと選定の永続台帳（2026-10-21、合成専用CLI）

直前cb632bed30666eec361df61019b85c7f1a8db3c7の比較画面は全7CI/回帰47件成功。
runtime39546345822/job119045279911は同一head verified=true。確定証拠は#267本文。
次の残件として `ml.final_five_selection_ledger` を追加。既存fit/Workbench/画面/APIは変更しない。

```sh
python -m ml.final_five_selection_ledger record experiment.json synthetic-snapshot.json \
  --synthetic --state-dir /absolute/path/outside/repository/selection-state \
  --request-id 11111111111111111111111111111111 --reason '合成比較の選定を保存'
python -m ml.final_five_selection_ledger inspect --synthetic \
  --state-dir /absolute/path/outside/repository/selection-state
python -m ml.final_five_selection_ledger show 11111111111111111111111111111111 \
  --synthetic --state-dir /absolute/path/outside/repository/selection-state
```

recordは明示指定した既存experimentのmodelとML snapshotを検証し、同一候補・同点数の
基準/第二段階選定、モデルhash、snapshot hash、順序、理由、未検証のローカル保存時刻を保存する。
モデル本体と元snapshotも台帳に保持するため、元ファイルを変更/削除しても保存済み選定を検証できる。
experimentのreportは信用/表示/保存/選定に使用しない。学習済みrace、cutoff前、不正モデル/予測は拒否。
実データと認定する機能はなく、明示syntheticと既存合成契約の両方を要求する。
モデル管理は保存した選定に結び付くモデルの保持まで。active/bestモデルの自動選択・昇格・配備はない。

request-idは32桁の小文字hex。通信/出力や保存中断後の同じ要求は同じIDで再試行する。
同一ID/モデル/snapshot/理由は元の時刻と選定を返してファイルも増やさない。IDの別内容利用は拒否。
新IDは同じ組合せでも別の選定として追記する。理由は空白のみ不可、500文字以内、制御文字不可。
inspectは同じraceの先行記録数、同じモデル/snapshotの先行記録数、別モデルの先行使用を表示。
異なるsnapshotでも同じraceなら選び直しの数へ含める。以前の選定を最新/都合のよい結果で置換しない。
showは1件の表示用選定とhashを返す。inspect/showはモデル本文/manifest/元全確率表を出力しない。

本台帳は `retrospective_synthetic_receipt`、evaluation_eligible=false、product_acceptance=false。
発走前に記録した証明ではなく、保存時刻をcaptured_atへ移したり前向き実績にしない。
結果/払戻/的中率を収集・集計せず、同じレースの記録数を評価サンプル数へ変換しない。
training_attempts_tracked=false。実験を学習前に登録する機能はなく、cutoff/目的変数/学習の再試行や
別台帳/未提供履歴の選択汚染は検出できない。この未完範囲を本台帳で解消済みとしない。
standalone入力には保留履歴が含まれないためhold_status=not_checked_in_standalone_ledger。
別Workbench等の保留を検知/解除せず、評価適格性も付与しない。既存画面の保留停止は維持する。

保存先はrepo外に限定。最大5モデル/20snapshot/100選定/32 MiB。上限到達時は拒否し、古い記録を
削除/間引きしない。APIによる書換/削除/import/mergeはない。新しい台帳への分割で横断追跡はされない。
入力ファイルは通常ファイル/単一link/8 MiB以下、symlink/FIFO拒否。モデルとsnapshotの入力原本は不変。
保存は既存SessionStoreの別固定ファイルとlockを再利用。予測セッション/保留確認一式とは分離する。
排他lock・一時書込→file fsync→replace→directory fsyncが成功してからメモリと応答を更新。
失敗時は前のメモリを保持し、inspect/showを含め再起動まで停止。replace後のfsync失敗は保存不確実。
再起動時は採用された完全checkpointを検証し、同一IDの再試行で二重登録しない。
途中の.partialを完成保存物と扱わず、自動で復元/削除しない。他processの変更を上書きせず停止する。
復元時に全モデル/元snapshot/参照/順序/停止条件を検証し、基準と推論を再計算して保存値と完全照合する。
現在の依存環境で推論値が一致しない場合も拒否し、保存値を再計算結果で書き換えない。
破損は拒否し原本を保持。hashは署名・来歴/権利証明ではなく、有効な古い台帳への差戻し検知は保証しない。
ローカルPOSIXの検証であり、任意ホストの電源断耐久性や本番の保存基盤受入を意味しない。

新規Python9試験：7/9車×3/4/5点・再読込照合/学習なし、重複/別内容ID/モデル変更履歴、
gate/不正入力/既知race拒否、hash再計算後の内容破損、上限/原本不変、保存前後fsync障害、
実SIGKILL前後2境界、lock/外部変更/入力link/FIFO/サイズ、別processのrecord/inspect/showを検証。
ローカル9/9成功。画面変更なし、新規Chromeは追加しない。ML CIへ新規9試験を追加し、
新headのCIは#267本文へ確定保存する。結果記録だけのcommit/旧成功CIの手動再実行なし。

残件：画面保存接続、学習前の実験登録/失敗/再試行/検証集合の再使用記録、商品目的変数/受入基準、
第一段階を含む独立評価、DREAM、会員/課金/実データ受入。実精度・利益・商品完成とは扱わない。
API20/12/11/7記録値、KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFFを維持。
#266/#267マージ・公開・Function配備未承認。将来の現行原本保存・段階受入・復元は#266本文を厳守。

## 合成比較画面から選定を保存・確認（2026-10-21、未公開候補）

上記CLIの台帳を再利用し、Workbenchへ `--final-five-selection-dir` を明示指定した場合だけ保存を有効化する。
指定なしは保存不可の表示。閲覧/再確認/起動/既存記録の照会では選定を追記しない。モデルの学習/切替/昇格なし。

```sh
python -m ml.synthetic_workbench --synthetic --port 8765 \
  --state-dir /absolute/path/outside/repository/state \
  --final-five-experiment /absolute/path/outside/repository/experiment.json \
  --final-five-selection-dir /absolute/path/outside/repository/selection-state
```

比較画面の理由欄→「選定を保存」で、既存snapshot/modelと理由を保存する。
`POST /api/final-five-selection` はsnapshot_id/snapshot_sha256/model_sha256/request_id/reasonの5項目だけ。
loopback/同一origin/既存X-Keirin-Local/small JSONを要求。表示後にモデル/元予測が変わった要求、
同じ予測セッションのML保留、学習済みrace/cutoff前、保存停止中、元セッションの外部変更は拒否。
送信時に全session契約を再検証。予測セッションと台帳の変更は1つのapp lockで直列化する。
これは提供された現在の予測セッション内の保留検査であり、別確認一式や未提供保留の横断検知ではない。
保存先/上限/モデル/入力/再計算検証はCLIと共通。台帳に保留解除や評価適格性を付与しない。
新規保存は予測/通常結果/保留履歴/確認一式を書き換えない。台帳破損で起動拒否した場合も取得済みlockを解放。

ブラウザは送信前に要求内容とUUIDをlocalStorageへ保持する。保持失敗/不正保存要求では新規送信しない。
保存の応答喪失/不正応答を成功と表示せず、同じIDで確認/再送する。連打で複数要求を作らない。
未確認要求のID/理由を黙って変更せず、現在モデルと一致しない要求は再送しない。
成功確認後の「別の選定として記録」は新IDで追記。以前のサーバー記録を削除/置換しない。
同じoriginとsnapshotで再読込すると保持IDを照会する。別port/端末やブラウザ保存喪失ではID保持を保証せず、
要求IDの手入力かCLI inspect/showで確認する。ブラウザの控えをサーバー保存成功の証拠にはしない。

`GET /api/final-five-selection/<request-id>` は保存済み1件を返す。モデル本体/学習manifest/元全確率表は返さない。
現在のモデルなし/保留後でも過去記録を確認できるが、過去の記録と明示し現在のAI候補/保留状態を変更しない。
不明ID/保存先未指定は404、台帳保存停止/外部変更は503。query/任意パスは受け付けない。
照会/保存応答のschema・停止条件・対象hash・基準/AI候補を確認し、不正/失敗時は過去の確認詳細を消す。
遅い旧照会は破棄。画面再確認で候補を消し保存を無効化する既存動作とCSP/no-storeを維持。
保存時刻は未検証ローカル時刻。記録は後からの合成比較であり、前向き実績や商品受入ではない。

新規Python/API6＋変更が影響する既存challenger6がローカル成功。新規Chrome2ケース（390/1280幅）を追加。
7/9車×3/4/5点の明示保存、サーバー保存後の応答喪失→同ID再送、reload/再起動、選び直し保持、
不正/遅い旧照会の消去、表示後の保留による保存拒否、ブラウザ控え破損の停止、モデルなしの過去照会を対象とする。
実API生成データを実JS検証関数へ渡す照合と、不正な内側の安全主張の拒否もローカル成功。
JS構文/diff check成功。実Chromeと全CIの確定証拠は#267本文を優先する。
学習前の実験登録/失敗/再試行/検証集合再使用、第一段階を含む独立評価、商品目的変数/受入、DREAM、会員/課金は残る。
API20/12/11/7記録値、HOLD/OFF、#266/#267未マージ/未公開/未配備、将来の現行原本/段階受入/復元条件を維持。
