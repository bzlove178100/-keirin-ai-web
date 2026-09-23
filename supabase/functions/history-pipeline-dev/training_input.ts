export const TRAINING_SCHEMA='keirin-training-input-v1';

export function buildTrainingInput(s:any,er:any,evaluationScope:string){
  const race=structuredClone(s?.race_data?.race??{});
  const players=structuredClone(s?.race_data?.players??[]);
  const context=structuredClone(s?.race_data?.prediction_context??null);
  const raw=structuredClone(s?.race_data?.odds?.trifecta??{});
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
