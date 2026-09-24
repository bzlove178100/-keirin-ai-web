from __future__ import annotations

from pathlib import Path

INDEX = Path("index.html")

ANCHOR = '''  <p class="sub">個人利用版・owner認証対応</p>
</header>'''
REPLACEMENT = '''  <p class="sub">個人利用版・owner認証対応</p>
  <p class="note"><a id="prospective-tools-link" href="prospective-tools.html" style="color:#93c5fd">前向き検証ツール（端末内処理）を開く</a></p>
</header>'''


def patch(text: str) -> str:
    if 'id="prospective-tools-link"' in text:
        return text
    if ANCHOR not in text:
        raise RuntimeError("header anchor not found")
    return text.replace(ANCHOR, REPLACEMENT, 1)


def main() -> int:
    original = INDEX.read_text(encoding="utf-8")
    updated = patch(original)
    if updated == original:
        print("prospective tools launcher already applied")
        return 0
    INDEX.write_text(updated, encoding="utf-8")
    print("prospective tools launcher applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
