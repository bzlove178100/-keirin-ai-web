"""Prepare a synthetic-only owner API module outside the checkout; never deploy."""
import argparse
import hashlib
import json
from pathlib import Path

from ml.model_web_response import model_web_response
from ml.synthetic_workbench import Workbench


def prepare_bundle(output_dir):
    output_dir = Path(output_dir)
    if output_dir.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('bundle_output_must_be_outside_repository')
    # A new directory prevents overwriting an existing package. No input model,
    # session, source record, URL or credential is accepted by this generator.
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    app = Workbench()
    try:
        views = []
        for count in (7, 9):
            state = app.predict(count)
            key = state['current']['snapshot_id']
            views.append(model_web_response(app.snapshots[key], key))
        bundle = {'schema_version':'keirin-synthetic-model-bundle-v1', 'views':views}
        source = 'export const SYNTHETIC_MODEL_VIEWS: unknown = ' + json.dumps(bundle,ensure_ascii=True,allow_nan=False,separators=(',',':')) + ';\n'
        path = output_dir/'synthetic_model_views.ts'
        with path.open('x',encoding='utf-8') as handle:
            handle.write(source)
        receipt = {'schema_version':'keirin-synthetic-model-bundle-receipt-v1',
                   'synthetic_only':True, 'deployed':False,
                   'module_sha256':hashlib.sha256(source.encode()).hexdigest(),
                   'snapshots':[{'snapshot_id':v['snapshot_id'], 'snapshot_sha256':v['snapshot_sha256'],
                                 'model_artifact_sha256':v['model_artifact_sha256'],
                                 'rider_count':v['quality']['rider_count']} for v in views]}
        with (output_dir/'bundle_receipt.json').open('x',encoding='utf-8') as handle:
            json.dump(receipt,handle,ensure_ascii=False,indent=2)
        return receipt
    finally:
        app.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic',action='store_true',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_bundle(args.output_dir),ensure_ascii=False))


if __name__ == '__main__': main()
