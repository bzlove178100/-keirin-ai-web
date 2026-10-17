# 未公開の統合候補・再開記録

2026-10-17、ユーザー承認の「問題がなければ3工程ごとに継続確認」の第1工程。
工程は統合候補作成・対象検証・GitHub保存までを1単位とする。CI結果の確定前は完了数へ加算しない。

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

最新head・新統合CI・他CIの確定結果はPR #260本文を正とする。残CIだけ確認し、成功なら第1工程完了（1/3）を記録。
次の未完了候補は、同じ生成モデルbundleをAPIと完全画面で共有する受入、および公開前の候補パッケージの対応/復元確認。既存試験で満たされていれば再実装せず、差分だけ扱う。
3工程完了時に自動タスクを停止し、次の3工程はユーザー確認後。3工程を利用枠20%と見なさない。

KEIRIN.JP HOLD、実取得・実学習・予想DB書込・本番予想OFF。合成認証は実認証成功ではない。
原本9fbb95d探索/再実装、許諾再調査、Jarvis・共有WORK文書・他PR担当ファイルの編集なし。
マージ・認証/権限変更・課金・問い合わせ・公開・配備は別途承認後。CI/合成成功は実精度・利益・運用成功を示さない。
