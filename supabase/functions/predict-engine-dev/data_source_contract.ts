export const DATA_SOURCE_CONTRACT_VERSION='2026-09-v1';
export const DATA_SOURCE_MODE='caller_supplied_only';
export const PRODUCTION_DATA_SOURCE_CONNECTED=false;
export type RaceDataEnvelope={source_type:'manual'|'approved_api'|'licensed_feed'|'test_fixture';source_name?:string;fetched_at?:string;race_data:Record<string,unknown>;};
