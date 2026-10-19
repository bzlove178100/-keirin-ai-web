# QMP初回フレーム失敗の再発記録

対象head: daa9f9efb3eb59e2ced8338aeb4eaa4af9f79981（Draft #266）。
回帰39177306812は47 jobs中46 success、custody-inbound-leaseだけfailure。
失敗job: https://github.com/bzlove178100/-keirin-ai-web/actions/runs/39177306812/job/117822523447

2026-10-18T23:51:49Z、QMP.__init__の最初のフレームは次の内容だった。

```json
{"timestamp":{"seconds":1792367509,"microseconds":901989},"event":"RESUME"}
```

greetingのQMPキーがないため、capabilities送信・query-block・guest qualificationより前に拒否した。
今回初めて、この再発の先頭フレームを特定できた。過去#246時点の失敗と同一原因とは証明していない。
失敗時の観測: QEMU 8.2.2（package 1:8.2.2+ds-0ubuntu1.18）、kernel 6.17.0-1022-azure、systemd 255.4。
今回の候補はVM supervisor/inbound leaseコードをmainから変更していない。

公式QMP仕様は接続時のgreeting、その後のcapabilities交渉を定め、交渉前に非同期イベントを送らない。
参照: https://www.qemu.org/docs/master/interop/qmp-spec.html
現行observerの拒否は維持する。イベントを飛ばす、再接続、無条件再試行、期限延長、guest保護解除は行わない。
ログはRESUMEが先に届いた事実を示す。なぜこの順序になったかは未確定。
ローカルにQEMUがないため実VM再現は未実施。上流sourceの取得も失敗し、読めた扱いにはしていない。
次の診断は、同一CI QEMU版の起動・monitor接続時系列を保持して順序を説明できる最小再現。
同じheadを再実行して成功するだけでは、根本原因や恒久修正の証明にならない。

runtime39177306779/job117822522997は23:38:40Z〜23:58:42Zの回帰待ちでblocked。
終了時の観測はregression in_progress。後に確定した回帰failureとは区別する。
5系統の成功は維持し、このheadを全CI成功とは記録しない。
今回の独立した競輪機能変更は未公開Draftで進める。新head CIが成功しても、過去失敗の根本原因は未確定のまま。
マージ・配備・実稼働の承認はなく、HOLD/OFFは変更しない。
