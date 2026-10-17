# 競輪AI開発Function：未配備候補の固定と戻し方

2026-10-17 JST。基準mainは `c9d94b16d3020c9e71405c62fb015cbbf61a710f`。
これは配備前レビュー用の記録であり、Supabase配備・実Function呼出し・認証変更は行っていない。

## 読み取りで確認した現行配備

対象は `keirin-ai-staging` の3つの開発Functionだけ。全てACTIVEかつ `verify_jwt=true`。

- `predict-engine-dev` v16：旧main `3795de4` 相当。新しい `synthetic_model_view` と合成bundleは未配備。
- `history-builder-dev` v6：旧7車処理。現行mainの7/9車共通契約は未配備。
- `backtest-engine-dev` v5：旧7車/210通り処理。現行mainの7/9車共通契約は未配備。

取得したソースは配備前後比較と戻し用にだけ使う。agent系Functionは対象外で、ソースを取得していない。

## 追加した事前検査

`ml.keirin_dev_deployment_package` は次をcheckout外の新規ディレクトリへまとめ、hash付きmanifestを最後に書く。

- 現行mainから3 Functionと相対依存を固定したcandidate。
- 読み取った現行配備ソースをそのまま保持したrollback。
- `ml.owner_review_package` がコード生成fixtureだけで作った7車/9車の合成bundle。
- Functionごとのentrypoint、`verify_jwt=true`、配備順、逆順のrollback順、追加・変更ファイル一覧。

候補では次の設定文字列の存在を静的検査する。任意のコードの動作や安全性を証明する検査ではなく、レビュー済みソースのhash固定・既存回帰試験と併用する。

- DB書込OFF。
- production source未接続、caller supplied only。
- ownerのroleとplanの両方を要求。
- 合成モデル応答を保存しない。
- history/backtestのDB書込・外部取得・保存OFF。

出力先の既存利用、symlink、余分・欠損・改変ファイル、観測hashの不一致、合成owner packageのhash不一致、7/9車以外、OFF契約の後退を拒否する。生成器は配備APIを呼ばず、鍵・セッション・実データを受け取らない。

## 実生成したレビュー用manifest

ローカルの保存済みLightGBM 4.7.0 / NumPy 2.5.4依存を再利用し、ネットワーク取得なしでコード生成fixtureからowner packageを作成した。最初の実行は新環境にLightGBMがなく失敗したため、その条件のまま反復していない。

- owner package manifest SHA-256：`a2c4f43aa05068c2c533f8060bc1f7ce109c1fc4c83b81065e560a844c48d0ad`
- deployment package manifest SHA-256：`3c8cc0a06822d7f4660f0da51221351cf80609f5bbd7621feb0f4342e9b0d32d`
- candidate commit：`c9d94b16d3020c9e71405c62fb015cbbf61a710f`
- rollback参照commit：`3795de4d36c4a7834d033b3a2a038c757e7a0923`
- rider count：7 / 9。
- `prepared_only=true`、`deployed=false`、`real_auth_verified=false`、`real_data_operation_verified=false`。

差分は以下に限定された。

- predict：index変更、model preview・合成bundle・既存Web validatorの3依存追加。engine/race/source/persistence契約は配備版と同hash。
- history：index変更、7/9車共通probability依存追加。
- backtest：index変更、7/9車共通probability依存追加。

## 検証と承認境界

新規2試験は、候補/現行配備/合成bundleの固定、移動後の再検証、差分算出、観測・bundle・候補の改変拒否、OFF契約後退の拒否を確認。CIでは同試験に加えてDenoで3 entrypointのmodule graphを検査する。

配備する場合も、最初にremoteのversion・status・verify_jwt・ソースhashがこの観測から変わっていないか照合し、変化していれば停止して作り直す。承認後の候補順はbacktest→history→predict、問題時の戻し順はpredict→history→backtest。各Functionごとに配備後の読み戻しとowner認証下の合成dry-runを確認し、次へ進む。実データは使わない。

現時点では配備、#261のマージ/公開、実認証、DB書込、外部取得、実データ学習、本番予想を実行していない。KEIRIN.JP HOLDと既存owner条件を維持する。

## 原本保存の訂正・配備直前確認（2026-10-18 JST）

上記の初回deployment manifest `3c8cc0a0…` は配備に使用しない。
再取得した3 Functionはversion/status/verify_jwtが同一だが、初回の戻し用7ファイルには
取得APIのcontentより末尾LFが1文字ずつ多かった。7本とも差はこの1バイトだけと確認。
以前の「取得原本と同hash」「4依存が配備版と同hash」は厳密なbyte比較として撤回する。
Functionの配備変更や意味上のコード差を観測したわけではない。

手渡し保存を繰り返さず、`capture-observation` を追加した。`get_edge_function` の
JSON応答3件を配列として保存した入力から、UTF-8 contentをstrip/改行補完せず取り込む。
ACTIVE・verify_jwt=true・import_map=false・正の整数version・既知3対象・正確なファイル集合を
出力前に検査。重複・欠落・未知ファイル・パス逸脱・既存出力を拒否する。
これは呼出元提供の観測の保存であり、ライブ接続や観測時刻の独立証明ではない。

```sh
python -m ml.keirin_dev_deployment_package capture-observation \
  --sources-json /path/to/connector-responses.json \
  --output-dir /path/to/new-observation \
  --project-id APPROVED_PROJECT_ID --project-name APPROVED_PROJECT_NAME \
  --observed-at ACTUAL_OBSERVATION_TIME
```

既存の合成owner packageを再利用し、修正済みobservationからpackageを再生成。
manifest SHA-256は `e0b0f8004eec7d954171cdc00b7aff87e962feda79da9764aa1b5d88f44a4553`。
candidateは同じ `c9d94b1`、全candidate/bundle hashは初回と一致。学習は再実行していない。
rollback7本は今回取得APIのcontentとUTF-8 byte一致。metadataの時刻は呼出元入力である。

新規2試験を含む計4試験成功。末尾LFなし・LF1個・LF2個・CRLF・日本語を含め、
capture→package→rollbackのbyte一致、不正入力10種類の出力前拒否を確認。
新headのCIはPR本文で追跡し、旧headの成功を引き継がない。

ユーザーの23:51 JST「続けて」は、直前に提示した#262反映→配備直前照合→
backtest/history/predict段階配備とowner合成確認→成功後の#261/Pagesという範囲で受領。
実取得・実学習・DB書込・本番予想・権限変更・課金は承認範囲外。
現在の検証ブラウザは未ログイン。owner実認証を確保するまでFunction置換を開始しない。
新しい候補の保存とCI確認は進めるが、認証・配備・実データ運用を成功扱いしない。
