import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),opts={};
for(let i=0;i<args.length;i++){if(!['--md','--out','--module-dir','--target'].includes(args[i])||!args[i+1])throw Error('Usage: prepare-feishu.mjs --md report.md --out issue-dir --module-dir node_modules [--target url]');opts[args[i]]=args[++i];}
if(!opts['--md'])throw Error('--md required');
const input=path.resolve(opts['--md']),root=path.resolve(opts['--out']||path.dirname(input));
const moduleDir=opts['--module-dir']||process.env.MODEL_HEAT_NODE_MODULES;
const {marked}=await import(moduleDir?pathToFileURL(path.join(path.resolve(moduleDir),'marked/lib/marked.esm.js')).href:'marked');
const out=path.join(root,'feishu');fs.mkdirSync(out,{recursive:true});
const source=fs.readFileSync(input,'utf8');
const title=source.split('\n')[0].replace(/^# /,'');
let body=source.replace(/^# [^\n]+\n\n/,'').replace(/\n研究分工：[^\n]+\n?$/,'\n');
// Local companion files are bundled with MD; do not put a broken local link into Feishu.
body=body.replace(/\n\[模型精确ID与来源映射\]\(<[^>]+>\)\n?/,'\n模型精确ID与来源映射随Markdown配图包附带。\n');
body=body.replace('本期按参考样式制作5张配图，正文表格保留完整模型名及来源链接。','本期配有5张图，正文表格保留完整模型名及来源链接。');
body=body.replace(/\*\*([^\n]+?)\*\*/g,'<strong>$1</strong>');
let html=marked.parse(body,{gfm:true});
html=html.replace(/<img src="([^"]+)"([^>]*)>/g,(_,src,attrs)=>{
 const local=path.resolve(path.dirname(input),decodeURIComponent(src));
 if(!fs.existsSync(local)||!local.toLowerCase().endsWith('.png'))throw Error('Feishu requires existing local PNG: '+local);
 return `<img src="data:image/png;base64,${fs.readFileSync(local).toString('base64')}" width="980"${attrs}>`;
});
html=html.replaceAll('<h2>','<h2 style="color:#2f64e8;font-size:24px">')
 .replaceAll('<h3>','<h3 style="color:#3973ff;font-size:18px">')
 .replaceAll('<table>','<table style="width:100%;border-collapse:collapse;font-size:13px">')
 .replace(/<th([^>]*)>/g,'<th$1 style="background:#ebf2ff;border:1px solid #dfe4ec;padding:8px">')
 .replace(/<td([^>]*)>/g,'<td$1 style="border:1px solid #dfe4ec;padding:8px">')
 .replaceAll('<a href=','<a style="color:#3973ff" href=');
const heads=[...html.matchAll(/<h2\b[^>]*>(.*?)<\/h2>/gs)].map(m=>({index:m.index,title:m[1]}));
if(heads.length!==5||!heads[0].title.includes('OpenRouter'))throw Error('Invalid section order');
const wrap=s=>'<html><body><div style="font-family:Arial,Microsoft YaHei,sans-serif;font-size:14px;line-height:1.7;color:#252b34">'+s+'<p><br></p></div></body></html>';
const parts=heads.map((h,i)=>html.slice(i===0?0:h.index,heads[i+1]?.index||html.length));
parts.forEach((p,i)=>fs.writeFileSync(path.join(out,`part-${i+1}.html`),wrap(p)));
fs.writeFileSync(path.join(out,'full.html'),wrap(html));
fs.writeFileSync(path.join(out,'title.txt'),title);
fs.writeFileSync(path.join(out,'body.txt'),body);
const manifest={target:opts['--target']||null,title,sections:heads.map(h=>h.title),images:(html.match(/<img /g)||[]).length,tables:(html.match(/<table /g)||[]).length,parts:parts.map((p,i)=>({part:i+1,bytes:Buffer.byteLength(wrap(p))}))};
if(manifest.images!==5)throw Error('Expected five images');
manifest.warnings=manifest.parts.filter(p=>p.bytes>400000).map(p=>'Part '+p.part+' exceeds 400KB: inspect image size or split at block boundaries before pasting');
fs.writeFileSync(path.join(out,'preflight.json'),JSON.stringify(manifest,null,2));
console.log(JSON.stringify(manifest));
