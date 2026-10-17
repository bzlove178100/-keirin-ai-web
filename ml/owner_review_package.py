"""Prepare or verify a portable synthetic owner-review package; never deploy."""
import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = 'keirin-owner-review-package-v1'
MODULE_PREFIX = 'export const SYNTHETIC_MODEL_VIEWS: unknown = '
FILES = (
    'web/index.html', 'web/owner-web-integration.patch',
    'web/prospective-tools-core.js', 'web/model-web-response.js',
    'web/model-owner-preview.js', 'web/receipt.json',
    'bundle/synthetic_model_views.ts', 'bundle/bundle_receipt.json',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(package_dir):
    root = Path(package_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('package_directory_required')
    expected = set(FILES) | {'package.json'}
    found = set()
    for path in root.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('package_regular_files_required')
        if path.is_file():
            found.add(path.relative_to(root).as_posix())
    if found != expected:
        raise ValueError('package_file_set_mismatch')
    manifest = json.loads((root/'package.json').read_text())
    if (manifest.get('schema_version') != SCHEMA or
            manifest.get('synthetic_only') is not True or
            manifest.get('deployed') is not False or
            manifest.get('real_auth_verified') is not False or
            set(manifest.get('files', {})) != set(FILES)):
        raise ValueError('package_manifest_invalid')
    for name in FILES:
        if digest(root/name) != manifest['files'][name]:
            raise ValueError('package_digest_mismatch:' + name)
    web = json.loads((root/'web/receipt.json').read_text())
    bundle = json.loads((root/'bundle/bundle_receipt.json').read_text())
    if (web.get('schema_version') != 'keirin-owner-web-candidate-v1' or
            web.get('deployed') is not False or
            bundle.get('schema_version') != 'keirin-synthetic-model-bundle-receipt-v1' or
            bundle.get('synthetic_only') is not True or bundle.get('deployed') is not False):
        raise ValueError('package_component_receipt_invalid')
    if set(web.get('files', {})) != {Path(n).name for n in FILES if n.startswith('web/') and n != 'web/receipt.json'}:
        raise ValueError('package_web_files_mismatch')
    for name, value in web['files'].items():
        if value != manifest['files']['web/' + name]:
            raise ValueError('package_web_receipt_mismatch')
    if bundle.get('module_sha256') != manifest['files']['bundle/synthetic_model_views.ts']:
        raise ValueError('package_bundle_receipt_mismatch')
    raw = (root/'bundle/synthetic_model_views.ts').read_text()
    if not raw.startswith(MODULE_PREFIX) or not raw.endswith(';\n'):
        raise ValueError('package_module_format_invalid')
    payload = json.loads(raw[len(MODULE_PREFIX):-2])
    if payload.get('schema_version') != 'keirin-synthetic-model-bundle-v1':
        raise ValueError('package_bundle_schema_invalid')
    views = payload.get('views', [])
    if [v['quality']['rider_count'] for v in views] != [7, 9]:
        raise ValueError('package_rider_counts_mismatch')
    snapshots = [{key: v[key] for key in ('snapshot_id', 'snapshot_sha256', 'model_artifact_sha256')}
                 | {'rider_count': v['quality']['rider_count']} for v in views]
    if bundle.get('snapshots') != snapshots or manifest.get('snapshots') != snapshots:
        raise ValueError('package_snapshot_mismatch')
    return {'schema_version': SCHEMA, 'integrity_verified': True,
            'synthetic_only': True, 'deployed': False, 'real_auth_verified': False,
            'snapshots': snapshots, 'files': manifest['files']}


def prepare(output_dir, *, synthetic=False):
    if synthetic is not True:
        raise ValueError('synthetic_mode_required')
    root = Path(__file__).resolve().parents[1]
    output = Path(output_dir).resolve()
    if output == root or root in output.parents:
        raise ValueError('output_must_be_outside_repository')
    output.mkdir(parents=True, exist_ok=False)
    # Verification alone has no model dependency and never retrains.
    from ml.prepare_owner_web_preview import prepare as prepare_web
    from ml.synthetic_model_bundle import prepare_bundle
    prepare_web(output/'web')
    bundle = prepare_bundle(output/'bundle')
    manifest = {'schema_version': SCHEMA, 'synthetic_only': True,
                'deployed': False, 'real_auth_verified': False,
                'snapshots': bundle['snapshots'],
                'files': {name: digest(output/name) for name in FILES}}
    # The completion receipt is written last. A partial export cannot verify.
    (output/'package.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return verify(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare')
    create.add_argument('--synthetic', action='store_true', required=True)
    create.add_argument('--output-dir', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('--package-dir', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output_dir, synthetic=args.synthetic) if args.command == 'prepare' else verify(args.package_dir)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
