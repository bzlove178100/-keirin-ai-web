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

候補では次を文字列ではなく固定契約として検査する。

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
