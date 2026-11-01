const fs = require('fs');
const path = require('path');
const args=process.argv.slice(2),opts={};
for(let i=0;i<args.length;i++){const k=args[i];if(k==='--svg-only'){opts[k]=true;continue;}if(!['--data','--out','--module-dir'].includes(k)||!args[i+1])throw Error('Usage: render.cjs --data report-data.json --out issue-dir --module-dir node_modules [--svg-only]');opts[k]=args[++i];}
if(!opts['--data'])throw Error('--data is required');
const input=path.resolve(opts['--data']);
const root=path.resolve(opts['--out']||path.dirname(input));
const data=JSON.parse(fs.readFileSync(input,'utf8'));
const validation=require('./validate-data.cjs').validate(data);
const presentation=require('../assets/layout-contract.json');
for(const c of data.cards){Object.assign(c,{title:presentation[c.key].title,tag:presentation[c.key].tag,accent:presentation[c.key].accent});}
const moduleDir=opts['--module-dir']||process.env.MODEL_HEAT_NODE_MODULES;
const sharp=opts['--svg-only']?null:require(moduleDir?path.join(path.resolve(moduleDir),'sharp'):'sharp');
const periodLabel=data.period.start_date+'—'+data.period.end_date;
const W=1960, H=1490;
const outputPath=path.join(root,`模型热度周报_${data.period.start_date}_${data.period.end_date}.md`);
const shownSummaries=card=>card.summaries;
const plain=s=>String(s??'').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/\*\*/g,'').replace(/`/g,'');
const C={blue:'#3973ff',blueText:'#2e67dc',blueBg:'#e8f0ff',orange:'#c66b00',orangeBg:'#fff0df',ink:'#272c34',gray:'#8b95a3',line:'#e5e8ed',header:'#ebf2ff',purple:'#8550ee',green:'#22a238',red:'#f24848'};
const esc=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
function width(s,size=26){return [...String(s)].reduce((n,c)=>n+(/[\u2e80-\uffff]/u.test(c)?1:0.56)*size,0)}
function trim(s,max,size){s=String(s??'—');if(width(s,size)<=max)return s;while(s&&width(s+'…',size)>max)s=s.slice(0,-1);return s+'…'}
function wrap(s,max,size){const out=[];let part='';for(const ch of plain(s)){if(width(part+ch,size)>max){out.push(part);part=''}part+=ch;}if(part)out.push(part);return out;}
function text(x,y,s,{size=27,color=C.ink,bold=false,anchor='start'}={}){return `<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${bold?700:400}" text-anchor="${anchor}">${esc(s)}</text>`;}
function summaryText(s,y,accent){
 const parts=String(s).replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').split(/(\*\*.*?\*\*)/g);
 const lines=[[]];let used=0;
 for(const part of parts){const bold=part.startsWith('**'),value=bold?part.slice(2,-2):part,color=bold&&/^[+\d]/.test(value)?accent:C.ink;
   for(const ch of value){const cw=width(ch,27);if(used+cw>1815){lines.push([]);used=0;}const line=lines[lines.length-1],last=line[line.length-1];if(last&&last.bold===bold&&last.color===color)last.value+=ch;else line.push({value:ch,bold,color});used+=cw;}
 }
 if(lines.length>2)throw new Error('Summary exceeds two lines: '+plain(s));
 return lines.map((line,i)=>`<text x="82" y="${y+i*29}" font-size="27">`+line.map(x=>`<tspan fill="${x.color}" font-weight="${x.bold?700:400}">${esc(x.value)}</tspan>`).join('')+'</text>').join('');
}
function pill(x,y,s,china=false,mode='normal',max=170){
 s=String(s??'—');if(/^[—\s/]+$/.test(s)||/^(缺快照|未核验|条件未齐|未取得|未披露|待披露|无可比值|无同期值)$/.test(s))return text(x,y+9,s,{color:C.gray,size:24,anchor:'middle'});
 let col=china?C.orange:C.blueText,bg=china?C.orangeBg:C.blueBg;
 if(mode==='change' && s.includes('%') && /^(↑|\+)/.test(s)){col=C.green;bg='#e5f6e8'}
 if(mode==='change' && s.includes('%') && /^(↓|[-−–])/.test(s)){col=C.red;bg='#fde8e8'}
 let font=25;while(font>17&&width(s,font)+28>max)font--;
 if(width(s,font)+28>max)throw Error('Numeric value too wide; format units/precision before rendering: '+s);
 const w=Math.max(48,width(s,font)+28);
 return `<rect x="${x-w/2}" y="${y-25}" width="${w}" height="48" rx="17" fill="${bg}"/>`+text(x,y+9,s,{color:col,bold:true,size:font,anchor:'middle'});
}
function sideTable(card,rows,china){
 const x=china?1004:62, rx=x+492, a=x+630,b=x+802;
 const headers=presentation[card.key].headers.slice(china?4:0,china?8:4);
 let s=text(x,484,headers[0],{size:25,bold:true});
 s+=text(rx,484,headers[1],{size:25,bold:true,anchor:'middle'});
 s+=text(a,484,headers[2],{size:25,bold:true,anchor:'middle'});
 s+=text(b,484,headers[3],{size:25,bold:true,anchor:'middle'});
 for(let i=0;i<10;i++){
   const row=rows[i],y=566+i*92;
   if(row){const display=row.display_name||row.name; const size=width(display,26)>435?24:26;s+=text(x,y+9,trim(display,435,size),{size,color:['huggingface','community'].includes(card.key)?C.blue:C.ink});s+=pill(rx,y,row.rank??'—',china);s+=pill(a,y,row.a,china,'normal',148);s+=pill(b,y,row.b,china,'change',176);}
   else{s+=text(x,y+9,'—',{color:C.gray});s+=text(rx,y+9,'—',{color:C.gray,anchor:'middle'});s+=text(a,y+9,'—',{color:C.gray,anchor:'middle'});s+=text(b,y+9,'—',{color:C.gray,anchor:'middle'});}
 }
 return s;
}
function cardSvg(card,i){
 let s=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs><clipPath id="card"><rect x="1" y="1" width="1958" height="1488" rx="24"/></clipPath></defs><g font-family="Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif" clip-path="url(#card)"><rect width="1960" height="1490" fill="white"/><rect width="1960" height="168" fill="${C.header}"/>`;
 s+=text(46,72,'✦',{size:33,color:C.purple,bold:true});
 s+=text(80,72,`模型热度周报 ${i+1}/5 | ${card.title}`,{size:33,color:C.blue,bold:true});
 const tagX=Math.min(1150,68+width(`✦ 模型热度周报 ${i+1}/5 | ${card.title}`,33));
 s+=`<rect x="${tagX}" y="36" width="142" height="48" rx="20" fill="#d7e5ff"/>`+text(tagX+71,69,card.tag,{size:24,color:C.blue,bold:true,anchor:'middle'});
 const sourceLine=`${periodLabel} · ${card.source_label}`;
 if(width(sourceLine,26)>1868)throw Error('Shorten source_label: '+card.key);
 s+=text(46,127,sourceLine,{size:26,color:C.blue});
 s+=text(46,231,'本期简析',{size:28,color:card.accent||C.blue,bold:true});
 shownSummaries(card).forEach((line,j)=>{s+=text(60,288+j*61,'•',{color:C.blue,size:29});s+=summaryText(line,288+j*61,card.accent||C.blue);});
 s+=sideTable(card,card.global,false)+sideTable(card,card.china,true);
 s+=`<line x1="46" y1="514" x2="1914" y2="514" stroke="#d9dde3" stroke-width="4"/>`;
 for(let i=1;i<10;i++)s+=`<line x1="46" y1="${514+i*92}" x2="1914" y2="${514+i*92}" stroke="${C.line}" stroke-width="1.5"/>`;
 s+='</g><rect x="1" y="1" width="1958" height="1488" rx="24" fill="none" stroke="#dfe2e6" stroke-width="2"/></svg>';
 return s;
}
const cell=s=>String(s??'—').replace(/\|/g,'\\|').replace(/\n/g,' ');
const nameCell=r=>!r?'—':r.url?`[${cell(r.name)}](${r.url})`:cell(r.name);
(async()=>{
 fs.mkdirSync(path.join(root,'assets'),{recursive:true});
 const ext=sharp?'png':'svg';
 let md=`# 模型热度周报｜${periodLabel}\n\n${data.intro}\n\n${data.readme||''}\n\n`;
 for(let i=0;i<data.cards.length;i++){
   const card=data.cards[i],base=`${String(i+1).padStart(2,'0')}-${card.key}`,svg=cardSvg(card,i);
   fs.writeFileSync(path.join(root,'assets',base+'.svg'),svg);
   if(sharp)await sharp(Buffer.from(svg)).png().toFile(path.join(root,'assets',base+'.png'));
   md+=`## ${['一','二','三','四','五'][i]}、${card.title}（${card.tag}）\n\n**${card.subtitle}**\n\n`;
   md+=`![模型热度周报 ${i+1}/5 ${card.title}](<${path.join(root,'assets',base+'.'+ext).replaceAll('\\','/')}>)\n\n> **图表说明**\n>\n${card.chart_notes.map(n=>'> '+n.replace(/\n/g,'\n> ')).join('\n>\n')}\n\n### 本期简析\n\n`;
   shownSummaries(card).forEach(x=>md+=`- ${x}\n`);
   md+=`\n| ${presentation[card.key].headers.join(' | ')} |\n| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |\n`;
   for(let j=0;j<10;j++){
    const l=card.global[j],r=card.china[j];md+=`| ${nameCell(l)} | ${cell(l?.rank)} | ${cell(l?.a)} | ${cell(l?.b)} | ${nameCell(r)} | ${cell(r?.rank)} | ${cell(r?.a)} | ${cell(r?.b)} |\n`;
   }
   md+=`\n${card.notes||''}\n\n`;
   if(card.extraMarkdown) md+=card.extraMarkdown+'\n\n';
   card.sources.forEach(x=>md+=`- [${x.label}](${x.url})\n`);md+='\n';
 }
 const registryName='models-and-sources.json';
 const registry=data.cards.map(c=>({section:c.key,sources:c.sources.map(s=>({id:s.id,label:s.label,url:s.url,retrieved_at:s.retrieved_at})),models:[...new Map([...c.global,...c.china].map(r=>[r.entity_id,{entity_id:r.entity_id,name:r.name,url:r.url||null,evidence_ids:r.evidence_ids}])).values()]}));
 fs.writeFileSync(path.join(root,registryName),JSON.stringify(registry,null,2));
 md+=(data.outro||'')+'\n\n[模型精确ID与来源映射](<'+path.join(root,registryName).replaceAll('\\','/')+'>)\n';
 fs.writeFileSync(outputPath,md,'utf8');
 fs.writeFileSync(path.join(root,'report-preview.html'),'<html lang="zh-CN"><meta charset="UTF-8"><title>模型热度周报</title><body style="margin:0;background:#f0f2f5">'+data.cards.map((c,i)=>'<img style="display:block;width:100%;max-width:1960px;margin:16px auto" src="assets/'+String(i+1).padStart(2,'0')+'-'+c.key+'.'+ext+'">').join('')+'</body></html>');
 const portable=path.join(root,'portable');fs.mkdirSync(path.join(portable,'assets'),{recursive:true});
 for(const [i,c] of data.cards.entries()){const f=String(i+1).padStart(2,'0')+'-'+c.key+'.'+ext;fs.copyFileSync(path.join(root,'assets',f),path.join(portable,'assets',f));}
 fs.copyFileSync(path.join(root,registryName),path.join(portable,registryName));
 fs.writeFileSync(path.join(portable,path.basename(outputPath)),md.replaceAll('<'+path.join(root,'assets').replaceAll('\\','/')+'/', '<assets/').replaceAll('<'+path.join(root,registryName).replaceAll('\\','/')+'>','<'+registryName+'>'));
 fs.writeFileSync(path.join(root,'validation.json'),JSON.stringify(validation,null,2));
 console.log(JSON.stringify({cards:data.cards.length,markdown:outputPath,portable,png:!!sharp,warnings:validation.warnings}));
})().catch(e=>{console.error(e);process.exit(1)});
