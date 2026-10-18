# 申告済みレース状態を通常処理へ混入させない修正候補

2026-10-18 JST。基準main `4a975d000f3f45ba37dcc5256c41faed4980d474`。
#264/#261は承認後に公開済み。実ownerの7/9車合成受入と公開後CIは完了し、
最後の回帰39096495293も47/47 jobs成功。最新の公開・復元記録は#261末尾。
今回の候補は未マージ・未配備。公開済みの成功と混同しない。

## 問題と変更

ML側の既存 `race_conditions` は欠車・中止を拒否するが、Phase32側は同じ申告を
予測時に無視し、履歴のtraining_input作成時には落としていた。
合成結合試験で申告が消えることを再現してから修正した。

- 既存契約 `race_status: scheduled` と空の `withdrawn_car_numbers` を共通化。
  不明な状態、欠車申告、null/型違い/不足/追加キーは拒否する。
- ブラウザ、predict、history pipeline/builder、backtest、Python履歴・学習適格判定で
  申告を検査。正常な申告はsnapshotからtraining_inputへコピーして保持する。
- Webは不適格な申告をAPI要求前に止め、以前の予測・保存対象を消去。
  snapshot/履歴取込・学習準備・収集件数にも同じ検査を適用する。
  宣言があるのに検査scriptが読めない場合も処理しない。
- フィールドがない旧形式は従来どおり。省略を正常確認済みとは扱わない。
  推論方式、カテゴリ、認証/owner条件、DB・本番のOFF条件は変更しない。
- predictの追加共有依存を既存の3-Function配備候補生成器へ含める。
  この生成器だけではhistory-pipeline-devは梱包されない。将来の配備前に同Functionも
  最新原本・候補・復元対象を別途揃える。3-Function packageだけで全体反映済みと扱わない。

## 今回確認した範囲

- 生成7/9車でengine→browser/Edge history pipeline→builder→backtestまで成功。
  9種の不適格申告を各入口で拒否、422・保存false、子Function呼出しなしを確認。
- 実Web scriptと実handlerの結合で正常7/9車のsnapshot→履歴→評価、申告保持、
  異常申告の通信前停止・旧表示/保存対象消去・取込拒否・script不在時停止を確認。
- Python settlement12試験、collection5試験、配備候補4試験成功。
  新規試験は7/9車の保持・コピー独立性・不適格申告の学習/評価除外を確認。
- 保存済み合成bundleを再学習せず再利用し、実owner handlerの7/9車表示、既存権限制限、
  predictの異常申告422を確認。Auth/profileは合成stubで、配備済みAPIの再試験ではない。
- 変更に関係するWeb captureと既存静的回帰、diff検査成功。
- offline evaluation試験はローカルにLightGBMがなくimport時点で停止。
  再インストール・反復はせず、既存ML CIで確認する。新head CIはPR本文を正とする。

## 限界と次回

これは入力に明示された予測時レース状態の扱い。情報源の真正性や未申告の欠車を
自動確認せず、欠車レースの予測・返還計算・同着複数決着の評価を実装したものではない。
ML側にある結果保留処理と、Phase32側の結果申告・保留の接続は次の未完項目。

まずこの候補の未完CIだけ確認し、成功済み試験を理由なく反復しない。
マージ/Pages/API配備は新たな承認後。既存#264/#261の個別承認を本PRに拡張しない。
現行API predict19/history11/backtest10/history-pipeline6を変更していない。
KEIRIN.JP HOLD、実取得・実学習・予想DB書込・本番予想OFFを維持。
共有WORK/Jarvis・データ問い合わせ・課金・他案件は未変更。
他の公開PR #250/#257は今回のファイルと非重複。非公開Work/未push作業は未確認。
