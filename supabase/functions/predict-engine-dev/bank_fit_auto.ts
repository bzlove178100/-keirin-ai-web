export const BANK_FIT_AUTO_VERSION='bank-fit-heuristic-v1';

type AnyRecord=Record<string,unknown>;

const finite=(v:unknown):number|null=>{if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null};
const clamp=(v:number,min:number,max:number)=>Math.min(max,Math.max(min,v));
const pct=(v:unknown):number|null=>{const n=finite(v);if(n===null)return null;return n<=1?n*100:n};
const round=(v:number,d=3)=>{const p=10**d;return Math.round((v+Number.EPSILON)*p)/p};

function historyComponent(raw:unknown,weight:number){
  if(!raw||typeof raw!=='object'||Array.isArray(raw))return null;
  const h=raw as AnyRecord,starts=Math.max(0,finite(h.starts)??0);
  if(starts<=0)return null;
  const win=pct(h.win_rate),top2=pct(h.top2_rate),top3=pct(h.top3_rate),avg=finite(h.avg_finish);
  let rawScore=0,fields=0;
  if(win!==null){rawScore+=(win-14.3)/12;fields++;}
  if(top2!==null){rawScore+=(top2-28.6)/18;fields++;}
  if(top3!==null){rawScore+=(top3-42.9)/24;fields++;}
  if(avg!==null){rawScore+=(4-avg)/1.5;fields++;}
  if(fields===0)return null;
  const sampleWeight=Math.min(1,Math.sqrt(starts/12));
  const score=clamp((rawScore/fields)*3*sampleWeight*weight,-3*weight,3*weight);
  return{score:round(score),starts,fields,sample_weight:round(sampleWeight)};
}

function contextComponents(player:AnyRecord,ctx:AnyRecord){
  const style=String(player.style??'');
  const parts:Record<string,number>={};
  const track=finite(ctx.track_length_m),stretch=finite(ctx.home_stretch_m),cant=finite(ctx.max_banking_deg),wind=finite(ctx.wind_speed_mps);
  const windDirection=String(ctx.wind_direction??'unknown');

  if(track!==null){
    if(track<=350)parts.track_length=style==='逃'?0.8:style==='追'?-0.3:0.25;
    else if(track>=480)parts.track_length=style==='追'?0.8:style==='逃'?-0.3:0.3;
    else parts.track_length=0;
  }
  if(stretch!==null){
    if(stretch<=45)parts.home_stretch=style==='逃'?1.0:style==='追'?-0.4:0.2;
    else if(stretch>=60)parts.home_stretch=style==='追'?1.0:style==='逃'?-0.4:0.4;
    else parts.home_stretch=0;
  }
  if(cant!==null){
    if(cant>=32)parts.cant=style==='両'?0.5:style==='逃'?0.3:0.15;
    else if(cant<=27)parts.cant=style==='追'?0.25:style==='逃'?-0.15:0;
    else parts.cant=0;
  }
  if(wind!==null){
    if(wind<1)parts.wind=0;
    else if(windDirection==='home_headwind')parts.wind=(style==='逃'?-1.0:style==='追'?0.7:0.4)*Math.min(1.5,wind/3);
    else if(windDirection==='home_tailwind')parts.wind=(style==='逃'?1.0:style==='追'?-0.2:0.3)*Math.min(1.5,wind/3);
    else if(windDirection==='crosswind')parts.wind=style==='両'?0.1:-0.1*Math.min(1.5,wind/4);
    else parts.wind=0;
  }
  return parts;
}

function confidenceFor(ctx:AnyRecord,venueHist:any,similarHist:any){
  let evidence=0;
  for(const key of['track_length_m','home_stretch_m','max_banking_deg','wind_speed_mps'])if(finite(ctx[key])!==null)evidence++;
  if(String(ctx.surface_condition??'unknown')!=='unknown')evidence+=0.5;
  if(String(ctx.weather??'unknown')!=='unknown')evidence+=0.5;
  evidence+=Math.min(2,(venueHist?.starts??0)/6);
  evidence+=Math.min(1.5,(similarHist?.starts??0)/10);
  return evidence>=6?'high':evidence>=3?'medium':'low';
}

export function applyAutomaticBankFit(input:unknown){
  if(!input||typeof input!=='object'||Array.isArray(input))return{raceData:input,report:{version:BANK_FIT_AUTO_VERSION,applied:false,reason:'race_data_not_object',computed_cars:[],preserved_cars:[]}};
  const raceData=structuredClone(input as AnyRecord);
  const ctxRaw=raceData.bank_context;
  const ctx=ctxRaw&&typeof ctxRaw==='object'&&!Array.isArray(ctxRaw)?ctxRaw as AnyRecord:{};
  const players=Array.isArray(raceData.players)?raceData.players as AnyRecord[]:[];
  const computed:number[]=[],preserved:number[]=[],skipped:number[]=[];
  const details:AnyRecord[]=[];

  for(const p of players){
    const car=Number(p.car_number),existing=p.bank_fit&&typeof p.bank_fit==='object'&&!Array.isArray(p.bank_fit)?p.bank_fit as AnyRecord:{};
    if(finite(existing.score)!==null){preserved.push(car);details.push({car_number:car,source:'provided',score:Number(existing.score)});continue;}
    const bankHistory=p.bank_history&&typeof p.bank_history==='object'&&!Array.isArray(p.bank_history)?p.bank_history as AnyRecord:{};
    const venueHist=historyComponent(bankHistory.venue,1);
    const similarHist=historyComponent(bankHistory.similar,0.65);
    const components=contextComponents(p,ctx);
    if(venueHist)components.venue_history=venueHist.score;
    if(similarHist)components.similar_bank_history=similarHist.score;
    const usable=Object.keys(components).length>0;
    if(!usable){skipped.push(car);details.push({car_number:car,source:'none',score:null});continue;}
    const raw=Object.values(components).reduce((a,b)=>a+Number(b),0);
    const score=round(clamp(raw,-10,10));
    const confidence=confidenceFor(ctx,venueHist,similarHist);
    p.bank_fit={...existing,score,auto:{version:BANK_FIT_AUTO_VERSION,confidence,components:Object.fromEntries(Object.entries(components).map(([k,v])=>[k,round(v)])),context:{track_length_m:finite(ctx.track_length_m),home_stretch_m:finite(ctx.home_stretch_m),max_banking_deg:finite(ctx.max_banking_deg),wind_speed_mps:finite(ctx.wind_speed_mps),wind_direction:String(ctx.wind_direction??'unknown'),surface_condition:String(ctx.surface_condition??'unknown'),weather:String(ctx.weather??'unknown')},history:{venue:venueHist,similar:similarHist},note:'Transparent heuristic v1; not statistically calibrated. Existing explicit bank_fit.score is never overwritten.'}};
    computed.push(car);details.push({car_number:car,source:'auto',score,confidence});
  }
  return{raceData,report:{version:BANK_FIT_AUTO_VERSION,applied:computed.length>0,computed_cars:computed,preserved_cars:preserved,skipped_cars:skipped,details,policy:'preserve_explicit_score_else_compute_from_bank_context_and_history',calibration_status:'heuristic_uncalibrated'}};
}
