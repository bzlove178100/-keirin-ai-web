import '../../../model-web-response.js';

type RecordValue = Record<string, unknown>;
const validateView = (globalThis as unknown as {
  KeirinModelWeb: { validate(value: unknown): RecordValue }
}).KeirinModelWeb.validate;
const object = (v: unknown): v is RecordValue => v !== null && typeof v === 'object' && !Array.isArray(v);
const exact = (v: unknown, keys: string[]): v is RecordValue =>
  object(v) && Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k));

function catalog(bundle: unknown): RecordValue[] {
  if (!exact(bundle, ['schema_version', 'views']) || bundle.schema_version !== 'keirin-synthetic-model-bundle-v1' ||
      !Array.isArray(bundle.views) || bundle.views.length !== 2) throw Error('model_bundle_invalid');
  const views = bundle.views.map(v => validateView(v));
  const ids = views.map(v => v.snapshot_id);
  const counts = views.map(v => (v.quality as RecordValue).rider_count).sort();
  if (new Set(ids).size !== 2 || counts.join(',') !== '7,9' ||
      views.some(v => (v.race as RecordValue).venue !== 'SYNTHETIC')) throw Error('model_bundle_invalid');
  return views;
}

export function modelPreviewStatus(bundle: unknown) {
  try {
    return {available:true, scope:'bundled_synthetic_snapshots', snapshots:catalog(bundle).map(v => ({
      snapshot_id:v.snapshot_id, rider_count:(v.quality as RecordValue).rider_count,
      captured_at:v.captured_at, model_artifact_sha256:v.model_artifact_sha256,
    }))};
  } catch {
    return {available:false, scope:'bundled_synthetic_snapshots', snapshots:[]};
  }
}

// The entry point calls this only after the unchanged owner verifier succeeds.
// The bundle is a server module, never caller-supplied JSON or a requested URL.
export function modelPreviewResponse(request: RecordValue, bundle: unknown) {
  const failure = (error: string, status: number) => ({status, body:{success:false,
    mode:'synthetic_model_view', error, prediction_generated:false, saved:false,
    production_prediction_enabled:false, external_fetch_enabled:false, db_write_enabled:false}});
  if (!exact(request, ['mode','snapshot_id']) || request.mode !== 'synthetic_model_view' ||
      typeof request.snapshot_id !== 'string' || !/^[0-9a-f]{32}$/.test(request.snapshot_id))
    return failure('model_view_request_invalid',400);
  if (bundle === null) return failure('synthetic_model_bundle_not_prepared',503);
  try {
    const view = catalog(bundle).find(v => v.snapshot_id === request.snapshot_id);
    if (!view) return failure('synthetic_snapshot_not_found',404);
    return {status:200, body:{success:true, schema_version:'keirin-owner-ml-preview-v1',
      service:'predict-engine-dev',
      mode:'synthetic_model_view', input_source:'server_bundled_synthetic_snapshot',
      prediction_generated:false, saved:false, production_prediction_enabled:false,
      external_fetch_enabled:false, db_write_enabled:false, monetary_ev_enabled:false,
      model_view:structuredClone(view)}};
  } catch {
    return failure('synthetic_model_bundle_invalid',503);
  }
}
