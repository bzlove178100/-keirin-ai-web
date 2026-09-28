import { applyAutomaticBankFit } from '../predict-engine-dev/bank_fit_auto.ts';

export const TRAINING_SCHEMA='keirin-training-input-v1';

export function buildTrainingInput(s:any,er:any,evaluationScope:string){
  const bankFit=applyAutomaticBankFit(s?.race_data??{});
  const normalized:any=bankFit.raceData??s?.race_data??{};
  const race=structuredClone(normalized?.race??{});
  const players=structuredClone(normalized?.players??[]);
  const bankContext=structuredClone(normalized?.bank_context??null);
  const context=structuredClone(normalized?.prediction_context??null);
  const raw=structuredClone(normalized?.odds?.trifecta??{});
  const ignored=new Set<string>(Array.isArray(er?.odds_sanitization?.ignored_combos)?er.odds_sanitization.ignored_combos:[]);
  const source=String(context?.source??'');
  const kdreams=/K[-\s]?Dreams|Kドリームス|ケイドリームス/i.test(source);
  const removed:string[]=[];
  for(const key of Object.keys(raw)){
    if(ignored.has(key)||(kdreams&&Number(raw[key])===9999.9)){
      delete raw[key];
      removed.push(key);
    }
  }
  return{
    schema_version:TRAINING_SCHEMA,
    captured_at:s.captured_at,
    race,
    players,
    bank_context:bankContext,
    bank_fit_automation:structuredClone(bankFit.report),
    odds:{trifecta:raw},
    prediction_context:context,
    odds_sanitization:{
      policy:er?.odds_sanitization?.policy??'snapshot_safety_filter',
      source_matched:er?.odds_sanitization?.source_matched??kdreams,
      removed_combos:[...new Set([...ignored,...removed])].sort()
    },
    evaluation_scope:evaluationScope
  };
}
