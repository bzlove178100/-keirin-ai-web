export const PERSISTENCE_CONTRACT_VERSION='2026-09-v1';
export const DB_WRITE_ENABLED=false;
export const PERSISTENCE_MODE='disabled_until_validation';
export async function savePredictionDisabled():Promise<never>{throw new Error('Prediction persistence is disabled');}
