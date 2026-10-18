# owner合成モデル画面の接続候補

2026-10-17。基準main `c9d94b16d3020c9e71405c62fb015cbbf61a710f`。
#258/#259/#260はユーザー承認後にマージ済み。各PR headの全CI成功、最終main485ファイル/modeが統合受入候補と一致。
同PRを再マージしない。mainのPages/push CIの最新結果は#260本文を参照する。

## 今回の差分

#259のマージでindex.htmlの同時編集が解消したため、新しい独立ブランチで既存の生成patchをindexへ接続。
公開中の別PRは#250/#257でdocsのみ。非公開Work/未pushセッションは未確認。

- 既存の認証済み通信・5カテゴリ描画を使い、合成モデルの確認パネルを追加。
- 保存済み一覧→7/9車選択→結果表示。ログアウト/セッション消去時にパネルをreset。
- 独自認証・新しい鍵/権限・自動API要求は追加しない。手動確認ボタンでだけモデル一覧を取得。
- パネルscript不在/初期化失敗はパネル内のエラーに留め、既存ログイン/ログアウト処理を継続。
- Web候補生成は、全挿入箇所を逆変換・再適用して一致する既存接続済みページだけを再利用。
  二重追加・一部欠落は拒否。既に接続済みならpatchは空で、receiptのsource_already_integrated=trueを返す。
- server bundleはnullのまま。API配備・bundle配置・実認証確認は未実施。画面を出すだけで予測結果を捏造しない。

## 検証

ローカルowner API/Web/package計6試験成功。実LightGBM合成bundle、owner照合stub、7/9車の表示・失敗消去、移動/破損拒否を含む。
既存Web capture、7/9車取込、収集準備表示、Python回帰が成功。
既存UI生成スクリプト2本が新indexを変更しないこと、認証済み通信helper/rendererのmainとのbyte一致、Node構文、diff検査を確認。
完全ページ390px/1280pxのCIにはパネルscript404時の既存ログイン/ログアウト継続も追加。新headのCI結果はPR本文に記録し、未確認を成功にしない。

## 境界・次回

この新Draftのマージ・公開反映は未承認。22:58 JSTの承認は#258/#259/#260の取り込みと既存Pages反映に限定。
本候補のCIが成功したら差分レビューと公開範囲を確定。別途承認なしにマージしない。
合成bundleを含むAPI配備・実認証も別承認。今の公開環境でモデルを利用可能と報告しない。
既存owner APIの配備版は今回未取得。新パネルが旧応答/未準備応答を受けた場合は拒否/未準備を表示する。

通常の1工程/3工程ごとの承認停止は廃止済み。許可済み作業は続け、承認境界/作業を妨げる問題だけで停止。
KEIRIN.JP HOLD、実取得・実学習・予想DB書込・本番予想OFF。未許諾/保存実資料の学習なし。
価格・会員商品制御・FINAL5/DREAM TICKET・実精度評価は未完。Jarvis/共有WORK文書は未編集。

## 2026-10-18 新Work: backend受入成功後の統合

12:49 JSTのユーザー承認で#264をmerge/Pages反映。mainは
`bcc9108be7b62226a4bd618bfac34dec6428905b`、treeは検証済み#264と同じ
`2e94188b6803c7a2cf5799a44be71c68f3420364`。
Pages39094993832、ML39094993993、UI39094994029、DB39094994041、
回帰39094993994は全success。公開indexとmainのSHA256は
`e9daa88852891313b30d847b877add7dfac7de40205373b6bb4c23555fb6c50c`で一致。

新ブラウザーは未ログインだった。安全な認証入力後、Web/server/devのowner認証と
role=owner/plan=ownerを画面で確認。認証情報の抽出・差替え・権限変更は行っていない。
GitHub保存済み生成器を使用。旧owner packageの実在と全hash、manifest
`a2c4f43aa05068c2c533f8060bc1f7ce109c1fc4c83b81065e560a844c48d0ad`
を検証して合成bundleを再利用した。scratchが無ければ生成器から再構成する。
旧deployment packageは版が古いため再配備に流用しない。

最新predict18/history10/backtest9を観測し、content無変形で戻し用7本を固定。
返却名の各slug/接頭辞だけを厳密照合して取り除き、取得contentとのbyte一致を確認。
新deployment manifestは
`de2f0d4f0eeff8334d16cf257884c44b5500a7a96fee3fe25c5fac47f2d317e3`。
backtest10 → history11 → predict19の順で段階配備し、各段階で全ソースreadback一致、
ACTIVE/verify_jwt=true、実owner合成受入を確認した。history-pipelineは変更なし。

- 生成fixture 7/9車のバックテスト2件成功、保存0件。
- 生成fixtureの9-8-7/7-6-5履歴→評価成功、504/210確率を保持。
- 公開Webと配備済みpredictから7/9車とも9点表示、保存0件、補完なし。
- そのWeb出力をJSON保存し、そのままhistoryへ再入力して評価まで成功。
  9車: capture 03:58:59.966Z < scheduled/result 04:01:00Z。
  7車: capture 04:00:51.941Z < scheduled/result 04:02:00Z。
  結果時刻が実際に到来してからAPIを実行し、端末時計やsnapshotを変更していない。
- 7車入力の初回はファイル選択で予定時刻/確認欄が初期化されたため、表示は成功したが
  保存ボタンが無効だった。保存クリックの待機がタイムアウトした後に画面で原因確認。
  予定時刻と確認を入力し直した新予測から保存・履歴化した。認証や安全条件は回避していない。

これにより#262/#263/#264のbackend成功条件を満たしたため、既存の条件付き承認に従い
#261へ最新mainを統合。自動mergeに競合なし。index SHA256は既存の隔離合成検証済み
`4cd2de949f030f2393738c1120d3ed7c09497cd43b16ebbe77e40ab91ceb3f66`と一致。
合格済みローカル試験は再実行せず、新しい統合headのCI成功後にmerge/Pagesと実ownerの
7/9車モデル表示を確認する。本文記載時点ではその公開・モデル表示はまだ未実施。

上記は全てコード生成データによる構造・動作確認。実データ精度・ROI・商用完成ではない。
KEIRIN.JP HOLD、実取得/実学習/予想DB書込/本番予想OFFを維持。
失敗時は後続を止め、必要な対象をpredict→history→backtestの逆順で観測原本へ戻す。
共有WORK/Jarvis・他案件・自動継続タスク・問い合わせ・課金を変更していない。
