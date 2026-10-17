# 未公開の統合候補・再開記録

2026-10-17 22:32 JST更新。ユーザー指示により通常作業の3工程ごとの停止・確認を廃止。
問題がなく許可済み作業が残る間は実行中に次へ進む。必要な承認・既存停止条件だけ維持する。
定期実行は中断後の再開用であり、各工程を1時間おきに制限しない。利用率20%の取得・停止は保証できない。

## 基準と対象

- main: `3795de4d36c4a7834d033b3a2a038c757e7a0923`
- #258: `df740d0984c0ac5f2cc4a5f39deddfdf84338a3a`
- #259: `d688e810eb739b1f6e795ef7e8dbb9c64d05c44f`
- #260検証開始head: `42be2a843554d299356ce6e7788436ae7f0b64cf`
- 前回残CIの回帰39035081577・DB39035081587は両方success。前回ML/UIの成功と合わせ4系統成功確定。
- 公開PRは#250/#257/#258/#259/#260で変更なし。非公開Work・未pushセッションは未確認。

## 今回の実装

`ml.prepare_integrated_candidate`は、ローカルGitの完全SHAを指定して各PRの差分をcheckout外の新しい候補ディレクトリへ書き出す。
ブランチ・追跡ファイル・index.htmlを変更せず、merge/cherry-pick/push/fetchやコード実行をしない。
baseが祖先でない場合、変更ファイルの重複、短縮/可変ref、出力上書き、非通常ファイルを拒否する。
削除を含む差分を反映し、全ファイルのSHA256、入力commit、担当差分をmanifestへ記録する。
manifestのverificationはnot_run。生成できたことを受入成功にしない。

独立CI `keirin-integrated-candidate.yml` が固定#258/#259と対象#260 headを合成し、同じ候補上でPython settlement/evaluation、ブラウザ履歴/バックテスト、実LightGBM合成モデル、保存復元、owner handler/client、完全ownerページ390px/1280pxを検証する。
このCIは#260ブランチだけに限定。read-only、認証保存なし、公開Gitの固定SHAだけ取得する。
mainや他PR headが進んだ場合は次回照合し、ピンを無条件に更新しない。競合は停止してレビューする。

## 再現

ローカルに上記commitと最新#260を取得済みであることが前提。出力先は未作成のcheckout外ディレクトリ。

```sh
python -m ml.prepare_integrated_candidate \
  --base 3795de4d36c4a7834d033b3a2a038c757e7a0923 \
  --component df740d0984c0ac5f2cc4a5f39deddfdf84338a3a \
  --component d688e810eb739b1f6e795ef7e8dbb9c64d05c44f \
  --component FULL_REVIEWED_MODEL_HEAD_SHA \
  --output-dir /tmp/keirin-integrated-new
```

`source/`が未公開の検証用ソース。既存`ml.prepare_owner_web_preview`をその中から実行すると、#259のindexへowner追加差分を適用した別の候補HTMLを生成できる。ソース側のbundleはnullを維持。合成bundle配置やindex適用を本番へ行わない。

## ローカル検証

- 新しい候補作成試験1件成功：独立差分/削除/全hash、重複・既存出力・checkout内出力・可変refの拒否、元repo不変。
- 上記3headの統合候補でsettlement/evaluation/collection 26試験、workbench 17試験成功。
- 同候補の7/9車Phase32→履歴pipeline→builder→backtest、ブラウザ取込/時刻/学習準備のNode試験成功。
- 初回Pythonコマンドに不要な`discover`引数が混ざり、26件成功後に存在しないモジュールで終了1。コマンドを修正し26件成功・終了0を確認。製品修正なし。
- 一時環境に残っていたLightGBM4.7.0のimportを実確認して使用。実データは使わない。
- ローカルChromeは利用できず、統合候補の完全画面試験は新CI待ち。前head単体のChrome成功と混同しない。

## 次回

最新head・CIの確定結果はPR #260本文を正とする。f7f0996の統合CI39036662516で43試験と390px/1280pxの完全画面が成功し、統合受入工程は完了。
残CIのうちML39036662426/UI39036662460/DB39036662459もsuccess確認済み。回帰39036662441のみ未完だったため次回はこの差分のみ確認。
通常作業は3工程で止めない。次の追加は下記の生成モデルを共有する可搬パッケージ。マージ・配備・実認証は既存承認後。

## 同じ学習済み合成成果物を画面まで通す可搬パッケージ

従来の完全owner画面試験は手作りの予測fixture、実LightGBM生成のAPI試験は別bundleだった。
`ml.owner_review_package`は既存のWeb候補生成と合成LightGBM bundle生成をまとめ、7/9車の予測ID・モデルhash・各ファイルhashを結び付けた未公開パッケージを作る。
同じ成果物を完全owner画面へ通すよう試験を変更。生成元ディレクトリから移動後も、再学習せず検証・画面試験を行う。

```sh
python -m ml.owner_review_package prepare --synthetic --output-dir /tmp/keirin-owner-review-new
python -m ml.owner_review_package verify --package-dir /tmp/keirin-owner-review-new
```

`web/`、`bundle/`、完了時だけ書かれる`package.json`で構成。verifyは学習依存をimportせず、モジュールを実行せずJSONとして照合する。
上書き、欠損、リンク、余分なファイル、hash不一致、receipt間の予測不一致、生成途中のパッケージを拒否する。
hashは転送時の一致確認であり、署名・信頼・データ許諾・認証の証明ではない。verify成功は画面/API試験成功を意味しない。
既存index・認証・serverのnull bundleはそのまま。候補は未配備で、ダブルクリックでログイン動作する公開サービスではない。
生成時だけコード生成fixtureの学習を行い、保存実資料を使わない。新headの結果はPR本文で区別する。

ローカル2試験成功。実LightGBMによる7/9車package作成、別ディレクトリへのコピー・元の削除後のverify、
学習関連importを禁止した新Pythonプロセスでの一致、ファイル破損/欠損/追加/リンク、receiptとモデルの取り違え、
生成途中の失敗・完了receipt不在、合成指定不足、上書き拒否を確認。Node構文・差分検査も成功。
完全画面は手作りfixtureを生成bundleへ切り替え、統合CIでは生成→ディレクトリ移動→verify→画面操作とする。
この変更後のChromeはCI待ち。以前の成功を新実装の証拠にしない。

KEIRIN.JP HOLD、実取得・実学習・予想DB書込・本番予想OFF。合成認証は実認証成功ではない。
原本9fbb95d探索/再実装、許諾再調査、Jarvis・共有WORK文書・他PR担当ファイルの編集なし。
マージ・認証/権限変更・課金・問い合わせ・公開・配備は別途承認後。CI/合成成功は実精度・利益・運用成功を示さない。
