const assert=require('node:assert/strict');
const layout=require('../assets/layout-contract.json');
const keys=Object.keys(layout);
const fail=(test,msg)=>assert(test,msg);
const aware=s=>typeof s==='string' && /(?:Z|[+-]\d\d:\d\d)$/.test(s) && Number.isFinite(Date.parse(s));
const integer=v=>typeof v==='string'&&/^\d+$/.test(v)||typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
const isoDate=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s;
function validate(data){
 const p=data.period;fail(p&&isoDate(p.start_date)&&isoDate(p.end_date),'valid period dates from period.py are required');
 const days=(Date.parse(p.end_date)-Date.parse(p.start_date))/86400000+1;
 fail(Number.isInteger(days)&&days>0,'invalid inclusive period');
 fail(days===7 || data.allow_nonweekly===true,'report includes '+days+' dates; weekly report must have 7');
 fail(days===p.days,'period.days mismatch');
 fail(aware(p.start_inclusive)&&aware(p.end_exclusive),'period must have aware bounds');
 fail(Date.parse(p.end_exclusive)-Date.parse(p.start_inclusive)===days*86400000,'period boundary mismatch');
 const offset=p.timezone==='UTC'?'+00:00':p.timezone==='Asia/Shanghai'?'+08:00':null;
 fail(offset,'unsupported report timezone');
 fail(Date.parse(p.start_inclusive)===Date.parse(p.start_date+'T00:00:00'+offset),'period start date mismatch');
 fail(Date.parse(p.end_exclusive)===Date.parse(p.end_date+'T00:00:00'+offset)+86400000,'period end date mismatch');
 fail(p.comparison && aware(p.comparison.start_inclusive)&&aware(p.comparison.end_exclusive),'comparison bounds required');
 fail(Date.parse(p.comparison.end_exclusive)===Date.parse(p.start_inclusive),'comparison overlaps or has gap');
 fail(Date.parse(p.comparison.end_exclusive)-Date.parse(p.comparison.start_inclusive)===days*86400000,'comparison length mismatch');
 fail(Array.isArray(data.cards),'cards required');assert.deepEqual(data.cards.map(c=>c.key),keys,'five section order must follow template');
 fail(typeof data.intro==='string'&&data.intro.trim(),'intro required');
 const warnings=[];
 for(const c of data.cards){
  fail(c.source_label&&c.subtitle,'source_label and subtitle required: '+c.key);
  fail(c.summaries?.length===3&&c.summaries.every(s=>typeof s==='string'&&s.trim()),'three nonempty summaries required: '+c.key);
  fail(Array.isArray(c.chart_notes)&&c.chart_notes.length>=3&&c.chart_notes.every(s=>typeof s==='string'&&s.trim()),'chart_notes required: '+c.key);
  fail(Array.isArray(c.sources)&&c.sources.length>0,'sources required: '+c.key);
  const ids=new Set();for(const s of c.sources){fail(s.id&&s.label&&/^https?:\/\//.test(s.url),'source id/label/url required');fail(!ids.has(s.id),'duplicate source id');ids.add(s.id);fail(aware(s.retrieved_at),'source retrieval timestamp required');}
  const o=c.observation;
  fail(o&&['exact_period','rolling_window','snapshot','snapshot_delta','source_date_buckets'].includes(o.kind),'observation kind required: '+c.key);
  fail(typeof o.exact_report_period==='boolean'&&o.timezone&&o.calculation,'observation scope/timezone/calculation required');
  fail(o.comparison&&['not_computed','source_reported','recomputed'].includes(o.comparison.mode),'comparison mode required');
  if(o.comparison.mode!=='not_computed'){
   const b=o.comparison;fail(aware(b.start)&&aware(b.end)&&b.calculation,'comparison bounds/formula required');
   fail(aware(o.start)&&aware(o.end),'compared observation needs aware bounds');
   fail(Date.parse(b.end)===Date.parse(o.start),'comparison must immediately precede actual source window');
   fail(Date.parse(b.end)-Date.parse(b.start)===Date.parse(o.end)-Date.parse(o.start),'comparison must be same length');
  }
  if(o.exact_report_period){fail(o.kind==='exact_period'||o.kind==='rolling_window','snapshot or unspecified day buckets cannot claim exact period');fail(Date.parse(o.start)===Date.parse(p.start_inclusive)&&Date.parse(o.end)===Date.parse(p.end_exclusive),'actual source window does not match report: '+c.key);}
  else warnings.push(c.key+': actual observation is not the exact report period; ensure chart_notes explain it');
  if(o.kind==='snapshot')fail(aware(o.as_of),'snapshot as_of timestamp required');
  if(o.kind==='source_date_buckets'){
   fail(Array.isArray(o.date_labels)&&o.date_labels.length===days&&o.date_labels.every(isoDate),'source date bucket count must match stated period length');
   for(let j=1;j<o.date_labels.length;j++)fail(Date.parse(o.date_labels[j])-Date.parse(o.date_labels[j-1])===86400000,'source date buckets must be distinct and consecutive');
   if(o.date_labels[0]!==p.start_date||o.date_labels.at(-1)!==p.end_date)warnings.push(c.key+': source date labels differ from target dates; disclose the exact labels');
  }
  if(o.kind==='snapshot_delta'){
   fail(aware(o.start)&&aware(o.end)&&Date.parse(o.end)>Date.parse(o.start),'snapshot endpoints required');
   fail(o.timestamp_role&&o.repository_observation_time_known!==undefined,'distinguish commit from observation timestamps');
  }
  for(const side of ['global','china']){
   const rows=c[side];fail(Array.isArray(rows)&&rows.length<=10,'max 10 rows per side');
   let prev=null,missing=false;const entities=new Set();let nextRank=1;
   for(const r of rows){
    fail(r.entity_id&&r.name,'row entity_id/name required');fail(!entities.has(r.entity_id),'duplicate entity within same side');entities.add(r.entity_id);
    fail(typeof r.a==='string'&&typeof r.b==='string','display values a/b required');
    fail(!/…|\.\.\./.test(r.a)&&!/…|\.\.\./.test(r.b),'do not ellipsize numeric display');
    fail(Array.isArray(r.evidence_ids)&&r.evidence_ids.length>0&&r.evidence_ids.every(id=>ids.has(id)),'row evidence_id does not resolve');
    if(r.sort_value==null){fail(c.key==='releases'&&r.rank==null,'unknown metric rows must be unranked releases');missing=true;continue;}
    fail(!missing,'known metric must precede missing metric');fail(integer(r.sort_value),'sort_value must be nonnegative exact integer');
    const v=BigInt(r.sort_value);fail(prev===null||v<=prev,'ranking not descending: '+c.key+'/'+side);prev=v;
    fail(r.rank===nextRank++,'rank must be independent sequential order: '+c.key+'/'+side);
   }
  }
 }
 for(const side of ['global','china']){
  const a=data.cards[0][side],b=data.cards[2][side];
  assert.deepEqual(b.map(r=>[r.entity_id,r.rank]),a.map(r=>[r.entity_id,r.rank]),'capability order must match actual usage ranking');
 }
 return {status:'PASS',period:p,sections:keys,rows:data.cards.map(c=>({key:c.key,global:c.global.length,china:c.china.length})),warnings};
}
module.exports={validate};
if(require.main===module){try{const fs=require('node:fs');console.log(JSON.stringify(validate(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))),null,2));}catch(e){console.error(e.message);process.exit(1);}}
