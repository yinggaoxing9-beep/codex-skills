#!/usr/bin/env python3
"""Export archived articles to portable Markdown, static HTML, images and ZIP."""
import argparse
from datetime import datetime, timezone, timedelta
import html
import json
from pathlib import Path
import re
import shutil
import sqlite3
import zipfile
import archive as a

CSS='body{max-width:880px;margin:36px auto;padding:0 20px;font:17px/1.8 system-ui,sans-serif;color:#263238;background:#fafafa}a{color:#176f80}h1{line-height:1.4}img{display:block;max-width:100%;height:auto;margin:24px auto}.text{white-space:pre-wrap;overflow-wrap:anywhere}.meta{color:#607d8b;font-size:14px}li{margin:12px 0}'


def page(title,body):
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+html.escape(title)+'</title><style>'+CSS+'</style><body>'+body+'</body></html>'


def export(root, output):
    root=Path(root).resolve()
    output=a.safe_root(output)
    if output.exists() or output.with_suffix('.zip').exists():
        raise a.Problem('output_exists', '使用新的导出目录；不覆盖已有交付物')
    output.mkdir(parents=True)
    (output/'articles').mkdir()
    (output/'media').mkdir()
    db=sqlite3.connect((root/'archive.sqlite').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try:
        report=json.loads((root/'report.json').read_text(encoding='utf8'))
        rows=db.execute('SELECT * FROM articles').fetchall()
        rows=sorted(rows,key=lambda r:(int(json.loads(r['content']).get('published_at') or 0) if r['content'] else 0,r['id']))
        entries=[]
        images=set()
        unresolved=[]
        for row in rows:
            item=json.loads(row['payload'])
            if row['status']!='ok' or not row['content']:
                unresolved.append({'title':item['title'],'status':row['status'],'url':item['link']})
                continue
            c=json.loads(row['content'])
            if not all((root/c[k]).is_file() for k in ('html_path','markdown_path')):
                raise a.Problem('cache_missing')
            title=c.get('title') or item['title']
            date=datetime.fromtimestamp(int(c.get('published_at') or item.get('create_time') or 0),timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
            stem=date+'_'+re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title)[:60]+'_'+row['id'][:6]
            md=c['text']
            image_html={}
            for asset in c['assets']:
                position=asset['position']
                source=root/asset.get('path','__missing__')
                if asset['status']=='ok' and source.is_file() and a.digest(source.read_bytes())==asset.get('sha256'):
                    name=source.name
                    if name not in images:
                        shutil.copyfile(source,output/'media'/name)
                        images.add(name)
                    link='../media/'+name
                    image_html[position]='<img src="'+html.escape(link,quote=True)+'" alt="图片 '+str(position)+'">'
                else:
                    link=asset['url']
                    image_html[position]='<p>图片 '+str(position)+' 未下载：<a href="'+html.escape(link,quote=True)+'">原图链接</a></p>'
                md=md.replace('ASSET_'+str(position)+')',link+')')
            source_url=a.request_url(item['link'])
            meta=date+' · '+str(c.get('author') or '')
            (output/'articles'/(stem+'.md')).write_text('# '+title+'\n\n'+meta+'\n\n原文：'+source_url+'\n\n'+md+'\n',encoding='utf8')
            body='<p><a href="../index.html">返回目录</a></p><h1>'+html.escape(title)+'</h1><p class="meta">'+html.escape(meta)+' · <a href="'+html.escape(source_url,quote=True)+'">原文</a></p>'
            start=0
            for match in re.finditer(r'!\[image (\d+)\]\(ASSET_\d+\)',c['text']):
                body+='<div class="text">'+html.escape(c['text'][start:match.start()])+'</div>'+image_html.get(int(match[1]),'')
                start=match.end()
            body+='<div class="text">'+html.escape(c['text'][start:])+'</div>'
            (output/'articles'/(stem+'.html')).write_text(page(title,body),encoding='utf8')
            entries.append({'title':title,'date':date,'html':'articles/'+stem+'.html','markdown':'articles/'+stem+'.md','url':source_url,'retrieval':c.get('source_kind') or 'http','images':len(c['assets'])})
        title=(report.get('identity') or {}).get('nickname') or '公众号归档'
        summary='已发现 '+str(report['discovered'])+' 篇，已保存 '+str(len(entries))+' 篇；账号全历史总数未知。图片缺失 '+str(report['media_missing'])+' 个。'
        body='<h1>'+html.escape(title)+'</h1><p>'+summary+'</p><p>可离线阅读正文和已下载图片。公开合集可能未收录该账号的全部历史文章。</p><ol>'
        body+=''.join('<li>'+x['date']+' <a href="'+html.escape(x['html'],quote=True)+'">'+html.escape(x['title'])+'</a></li>' for x in entries)+'</ol>'
        if unresolved:
            body+='<h2>未保存正文</h2><ul>'+''.join('<li>'+html.escape(x['title'])+'：'+html.escape(x['status'])+'</li>' for x in unresolved)+'</ul>'
        (output/'index.html').write_text(page(title,body),encoding='utf8')
        (output/'README.md').write_text('# '+title+'\n\n'+summary+'\n\n双击 index.html 打开离线目录；articles/ 内含 HTML 与 Markdown；media/ 是本地图片。\n原始网页和采集版本仍保存在源归档目录。\n',encoding='utf8')
        for name in ('catalog.jsonl','catalog.csv','missing.json','report.json','report.md'):
            shutil.copyfile(root/name,output/name)
        manifest={'title':title,'body_success':len(entries),'unique_images':len(images),'image_positions':sum(x['images'] for x in entries),'missing':unresolved,'articles':entries}
        (output/'manifest.json').write_text(a.dumps(manifest),encoding='utf8')
        zip_path=output.with_suffix('.zip')
        with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for file in sorted(output.rglob('*')):
                if file.is_file():z.write(file,str(file.relative_to(output.parent)))
        return {'path':str(output),'index':str(output/'index.html'),'zip':str(zip_path),'body_success':len(entries),'unique_images':len(images),'image_positions':manifest['image_positions'],'zip_bytes':zip_path.stat().st_size}
    finally:db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    print(a.dumps(export(args.archive,args.output)))
