"""Display-only contract for frozen synthetic ML output; no auth assertion."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import re

from ml.model_history import validate_snapshot

WEB_SCHEMA = 'keirin-ml-web-response-v1'


def model_web_response(snapshot, snapshot_id):
    if not isinstance(snapshot_id, str) or not re.fullmatch('[0-9a-f]{32}', snapshot_id):
        raise ValueError('snapshot_id_invalid')
    validate_snapshot(snapshot, synthetic=True)
    prediction = snapshot['prediction']
    quality = prediction['input_quality']
    selection = prediction['selected_predictions']
    # Project allowlisted display fields only. Full scores, histories, auth claims
    # and arbitrary artifact metadata never become a browser/API response here.
    categories = {}
    for key, category in selection['categories'].items():
        categories[key] = {field:deepcopy(category[field]) for field in ('category_name','status','category_note')}
        categories[key]['picks'] = [{field:deepcopy(pick[field]) for field in
                                    ('rank','combo_key','estimated_probability','odds')} for pick in category['picks']]
    return {
        'schema_version':WEB_SCHEMA, 'scope':'frozen_synthetic_snapshot_display',
        'evidence_scope':'synthetic_test_only', 'authentication_status':'not_asserted',
        'entitlement_status':'not_asserted', 'production_prediction_enabled':False,
        'external_fetch_enabled':False, 'db_write_enabled':False,
        'supervised_training_enabled':False, 'monetary_ev_enabled':False,
        'probability_calibration_status':'uncalibrated',
        'snapshot_id':snapshot_id, 'snapshot_sha256':snapshot['snapshot_sha256'],
        'captured_at':snapshot['captured_at'], 'generated_at':prediction['generated_at'],
        'race':{field:deepcopy(prediction['race'][field]) for field in ('date','venue','race_number','scheduled_start_jst')},
        'model':{field:prediction[field] for field in ('model_version','inference_version','adapter_version')},
        'model_artifact_sha256':prediction['model_artifact']['sha256'],
        'quality':{field:quality[field] for field in ('rider_count','known_trifecta_odds_count','possible_trifecta_count')},
        'selection_policy':selection['selection_policy'], 'total_picks':selection['total_picks'],
        'categories':categories,
    }


def render_model_web_preview(snapshot_id):
    if not isinstance(snapshot_id, str) or not re.fullmatch('[0-9a-f]{32}', snapshot_id):
        raise ValueError('snapshot_id_invalid')
    root = Path(__file__).resolve().parents[1]
    web = (root/'index.html').read_text(encoding='utf-8')
    start, end = 'function appendPick(box, pick) {', 'function renderDryRun(data) {'
    if web.count(start) != 1 or web.count(end) != 1:
        raise ValueError('existing_category_renderer_not_found')
    renderer = web[web.index(start):web.index(end)]
    if re.findall(r'^function (\w+)\(', renderer, re.M) != ['appendPick','renderCategory']:
        raise ValueError('existing_category_renderer_changed')
    # Only two pure DOM renderers are reused. No owner login, live API bootstrap,
    # Phase32 validation or history capture code is executed in this local page.
    adapter = (root/'model-web-response.js').read_text(encoding='utf-8')
    bootstrap = """
const element=id=>document.getElementById(id);
const renderer=(id,category)=>renderCategory(id,category);
KeirinModelWeb.load('/api/model-view/' + SNAPSHOT_ID, {document,renderCategory:renderer});
""".replace('SNAPSHOT_ID', json.dumps(snapshot_id))
    script = renderer + '\n' + adapter + '\n' + bootstrap
    if '</script' in script.lower():
        raise ValueError('inline_script_boundary_invalid')
    template = (root/'ml/templates/model_web_preview.html').read_text(encoding='utf-8')
    html = template.replace('/* MODEL_WEB_SCRIPT */',script)
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return html, digest
