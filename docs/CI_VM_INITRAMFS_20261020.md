# 合成VMの初期ファイル展開失敗

対象：Draft #266、機能候補81b716458668152f3055e27fe89779c3acb292b4。
ML39408953490はsuccess（新規Python6、Chrome4を含む）。下記は別の既存VM回帰。

回帰39408953553のjob118581685104（inbound-boot）、118581685315（inbound-lease）、
118581685361（persistence）、118581685468（inbound-persistence invalid）、
118581685609（erofs-suspend）のログを確認した。
共通してkernel 7.0.0-1017-azure、systemd 255.4-1ubuntu8.18で、初回起動中に
`Initramfs unpacking failed: write error` → `VM_FAIL SYSTEMD_GUEST_EXEC_FAILED errno=2`。
ゲストの安全性判定へ到達せず、観測期限で失敗した。前候補のjob timeoutやQMP初回フレーム問題とは区別する。

同runの成功job118581685272（systemd-boot）、118581685331（inbound-persistence crash）、
118581685433（persistence-crash）はkernel 6.17.0-1022-azure、systemd 255.4-1ubuntu8.17。
QEMUバイナリhashは共通。失敗候補はこのVM実装を前headから変更していない。
環境差との相関は確認できたが、kernel変更だけが原因とはまだ確定していない。

既存systemd VMは512M。展開前archive、展開先rootfs、kernelのメモリ競合/容量不足を仮説として、
この使い捨てVMだけ固定1024Mへ変更する。新規ホスト/課金/本番メモリ設定変更ではない。
archive圧縮後bytes・展開対象ファイルbytes・VMメモリをprovenanceへ記録する。
QEMU/guest PID1の既存検査を通過したゲスト内でだけ、RAM/空きRAM/rootfs容量と空きinodeを出力する。
host実行拒否、160MiB画像上限、外部NICなし、ホストマウントなし、各期限、ポリシー/復元判定を維持。
packet-only VM512Mと最小VM256Mは今回の失敗対象ではなく、変更しない。

参考一次資料：
- https://github.com/torvalds/linux/blob/master/init/initramfs.c （write errorは展開ファイルの書込不足を示すが、errnoまではこの文字列にない）
- https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html （tmpfsの容量既定値は物理RAMの半分。ただし今回のrootfs種別は追加診断で確認する）

ローカル：既存systemd5/inbound11/inbound-lease3試験成功。Cをstatic/-Werrorでコンパイルし、
host実行がcapacity読取前にexit2/VM_GUEST_PID1_REQUIREDとなることを確認。
ローカルにQEMUはなく実VMは未実行。新候補のCIと実際のkernel/容量ログで判定する。
新環境で起動・全安全性判定が通らなければ未解決。同一失敗の無条件再実行や検査の緩和はしない。
本修正は試験環境の互換対応候補であり、任意kernel/ホストの動作保証や本番受入ではない。
最新head、CI結果、残件はPR本文を正とする。公開/配備未承認、HOLD/OFFを維持。
