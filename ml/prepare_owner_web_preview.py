"""Prepare a reviewable owner-Web candidate outside the checkout. No deployment."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ('prospective-tools-core.js', 'model-web-response.js', 'model-owner-preview.js')
BOOTSTRAP = """const ownerModelPreview = (() => {
try { return KeirinOwnerModelPreview.attach({
  document, host: document.getElementById('owner-model-host'),
  get: () => authenticatedGet(DEV_ENGINE_URL),
  post: body => authenticatedPost(DEV_ENGINE_URL, body),
  identity: () => currentSession?.user?.id || null,
  renderCategory
}); } catch (_) {
  const unavailable = () => { document.getElementById('owner-model-host').textContent = '合成モデル画面を読み込めませんでした。ページを再読み込みしてください。'; };
  unavailable();
  return Object.freeze({ reset: unavailable });
}
})();
"""


def prepare_html(source, *, allow_integrated=False):
    replacements = [
        ('<footer class="note">', '<div id="owner-model-host"></div>\n<footer class="note">'),
        ('<script src="prospective-tools-core.js"></script>',
         '\n'.join(f'<script src="{name}"></script>' for name in SCRIPTS)),
        ('function clearSession() {', 'function clearSession() {\n  ownerModelPreview.reset();'),
        ('async function logout() {', 'async function logout() {\n  ownerModelPreview.reset();'),
        ("element('login').addEventListener('click',login);", BOOTSTRAP + "\nelement('login').addEventListener('click',login);"),
    ]
    if 'owner-model-host' in source or 'ownerModelPreview' in source:
        if not allow_integrated:
            raise ValueError('owner_web_already_prepared')
        legacy = source
        for old, new in replacements:
            if legacy.count(new) != 1:
                raise ValueError('owner_web_integration_anchor_changed')
            legacy = legacy.replace(new, old)
        if prepare_html(legacy) != source:
            raise ValueError('owner_web_integration_anchor_changed')
        return source
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError('owner_web_integration_anchor_changed')
        source = source.replace(old, new)
    return source


def prepare(output_dir):
    output = Path(output_dir).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('output_must_be_outside_repository')
    source = (ROOT/'index.html').read_text(encoding='utf-8')
    html = prepare_html(source, allow_integrated=True)
    output.mkdir(parents=True, exist_ok=False)
    (output/'index.html').write_text(html, encoding='utf-8')
    patch = ''.join(difflib.unified_diff(source.splitlines(True), html.splitlines(True),
                                       fromfile='a/index.html', tofile='b/index.html'))
    (output/'owner-web-integration.patch').write_text(patch, encoding='utf-8')
    for name in SCRIPTS:
        (output/name).write_bytes((ROOT/name).read_bytes())
    receipt = {'schema_version':'keirin-owner-web-candidate-v1', 'deployed':False,
               'source_already_integrated': html == source,
               'source_index_sha256':hashlib.sha256(source.encode()).hexdigest(),
               'files':{name:hashlib.sha256((output/name).read_bytes()).hexdigest()
                        for name in ['index.html','owner-web-integration.patch',*SCRIPTS]}}
    (output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output_dir),ensure_ascii=False))


if __name__ == '__main__':
    main()
