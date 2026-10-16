# 7車・9車 settlement / evaluation 新規実装

2026-10-17 JST。基準main: 3795de4d36c4a7834d033b3a2a038c757e7a0923。

## 承認・所在

原本9fbb95dは未回収。Claude側の探索報告を受領後、原本回収を保留し、
新規実装→合成試験→独立Draft PRへ切り替える提案に対し、ユーザーが
2026-10-17 03:22 JSTに「続けて」と承認した。本変更は9fbb95dの復元ではない。
原本探索の報告とデータ利用条件は資料PR #257に保存済み。

着手時の公開PRは#250（AGENTSのみ）と#257（資料のみ）。対象コードの
重複PRなし。他Workの未公開作業は未確認。Jarvis・共有WORK文書は編集しない。

## 範囲と契約

- ml/settle_snapshot.py: 通常7車（1〜7）または9車（1〜9）の重複のない整数車番。
  bool・小数・文字列・範囲外・欠落を拒否。カテゴリ買い目も出走車の組合せに限定。
- ml/evaluation_protocol.py: 7車/9車に対応。既存の正規数字文字列の入力互換性を維持し、
  人数に応じた車番範囲を適用。bool・小数・重複・不正な人数は除外。
- 全組合せの確率表は既存permutations検証を再利用。7車210通り、9車504通り。
  欠落・重複・範囲外・合計確率不整合を拒否。
- エンジン識別子は既存契約を維持。Phase32の生成処理は入力車番の順列を使用する。
- 欠車で6車/8車になるケース、同着、上流Web/取得・予想機能の全9車対応は対象外。
  通常7車/9車の本処理が通ることはサービス全体の対応完了を意味しない。

## 検証記録

- 修正前、追加した9車settlement→evaluation試験はseven_riders_requiredで失敗。
  7車の不正車番にboolが通る問題と、list/dictでTypeErrorになる問題も再現。
- 修正後: settlement 11、offline evaluation 10、collection status 5、計26テスト成功。
- tests/test_ml_dataset.py、tests/test_trifecta_adapter.py成功。git diff --check成功。
- 7車/9車の往復、混合16レースの合成holdout、210/504通り、異常入力の隔離、
  synthetic既定除外、時刻順序、DB・本番フラグ拒否を確認。
- ローカルでLightGBMが未導入だったため、既存ml/requirements.txtの依存を
  /tmp/keirin-test-depsへ導入して検証。依存定義は変更しない。
- 再現コマンド（既存依存導入済み環境）:
  PYTHONPATH=.:tests python -m unittest test_settle_snapshot test_offline_evaluation test_collection_status -q
  python tests/test_ml_dataset.py
  python tests/test_trifecta_adapter.py
- リモートCIはDraft PR作成後にexact headの状態をPR本文で記録。前回資料PRのCIを流用しない。

## 停止条件・次の一手

KEIRIN.JP HOLD、外部実取得・実学習・予想DB書込・本番予想OFF。
生成した合成fixtureのみ使用し、保存資料・未許諾データは学習に使用しない。
新規問い合わせ・認証/権限変更・課金・本番操作・マージは行わない。
次は本Draftの差分レビューとexact head CI確認。マージは別途承認後。
データ提供元の許諾/費用/提供仕様は未確認項目が残り、採用可能とはしていない。
