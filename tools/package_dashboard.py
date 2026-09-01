#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, hashlib, io, json, os, re, shutil, sys, urllib.parse, zipfile
from pathlib import Path

from bs4 import BeautifulSoup
import requests
from PIL import Image, ImageDraw, ImageFont

CONCEPTS = [
    ("harbor", "website-01", "Website Design 1 — Harbor Response"),
    ("estate", "website-02", "Website Design 2 — Waterfront Care"),
    ("command", "website-03", "Website Design 3 — Command Deck"),
]
REMOTE_RE = re.compile(r"https?://[^\s\"'()<>|]+")
IMG_EXTS = {'.jpg','.jpeg','.png','.webp','.gif','.avif','.svg'}
FONT_REPLACEMENTS = {
    "'DM Sans'": "Arial, Helvetica, sans-serif",
    "'Manrope'": "Arial, Helvetica, sans-serif",
    "'Barlow Condensed'": "'Arial Narrow', Arial, sans-serif",
    "'Playfair Display'": "Georgia, 'Times New Roman', serif",
    "'Space Mono'": "'Courier New', monospace",
}

def log(*a):
    print(*a, flush=True)

def make_fallback(path: Path, label: str, size=(1600,1000)):
    path.parent.mkdir(parents=True, exist_ok=True)
    im=Image.new('RGB',size,(9,28,39))
    d=ImageDraw.Draw(im)
    for y in range(0,size[1],100): d.line((0,y,size[0],y), fill=(24,62,77), width=1)
    for x in range(0,size[0],100): d.line((x,0,x,size[1]), fill=(24,62,77), width=1)
    d.rectangle((70,70,size[0]-70,size[1]-70), outline=(255,141,58), width=4)
    d.rectangle((105,size[1]-260,size[0]-105,size[1]-105), fill=(10,35,48))
    d.text((125,size[1]-225), "TONY'S DOCKSIDE", fill=(255,255,255))
    d.text((125,size[1]-185), label[:90], fill=(102,200,235))
    im.save(path, quality=88)

def normalize_url(u: str) -> str:
    return u.replace('&amp;','&')

def is_asset_url(u: str) -> bool:
    if u == 'http://www.w3.org/2000/svg':
        return False
    p=urllib.parse.urlparse(normalize_url(u))
    ext=Path(p.path).suffix.lower()
    if 'fonts.googleapis.com' in p.netloc or 'fonts.gstatic.com' in p.netloc:
        return False
    return ext in IMG_EXTS or any(h in p.netloc for h in [
        'images.unsplash.com','images.squarespace-cdn.com','photos.zillowstatic.com','mymarcorental.com',
        'luxuryofnaples.com','media.vrbo.com','supabase.co','blob.core.windows.net','boatguys.com','powerandmotoryacht.com',
        'boatrepairmiamifl.com','bestmarinesurveyor.com','wixstatic.com'
    ])

def choose_ext(url: str, content_type: str|None) -> str:
    ct=(content_type or '').split(';')[0].strip().lower()
    m={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','image/gif':'.gif','image/svg+xml':'.svg','image/avif':'.avif'}
    if ct in m: return m[ct]
    ext=Path(urllib.parse.urlparse(url).path).suffix.lower()
    if ext in IMG_EXTS: return '.jpg' if ext=='.jpeg' else ext
    return '.jpg'

def fetch_asset(url: str, asset_dir: Path, idx: int, session: requests.Session) -> tuple[str,bool]:
    u=normalize_url(url)
    stem=f"media-{idx:02d}-{hashlib.sha1(u.encode()).hexdigest()[:10]}"
    try:
        r=session.get(u,timeout=25,allow_redirects=True,headers={'Referer':urllib.parse.urlunparse((*urllib.parse.urlparse(u)[:2],'','','',''))})
        r.raise_for_status()
        ct=r.headers.get('content-type','')
        ext=choose_ext(u,ct)
        path=asset_dir/(stem+ext)
        path.write_bytes(r.content)
        if ext != '.svg':
            try:
                with Image.open(path) as im: im.verify()
            except Exception:
                path.unlink(missing_ok=True)
                path=asset_dir/(stem+'.jpg')
                make_fallback(path, urllib.parse.urlparse(u).netloc)
                return f"assets/{path.name}", False
        return f"assets/{path.name}", True
    except Exception as e:
        path=asset_dir/(stem+'.jpg')
        make_fallback(path, urllib.parse.urlparse(u).netloc)
        log('  fallback:',u,'->',e)
        return f"assets/{path.name}", False

def strip_switching_and_prepare(source: str, concept_id: str, title: str) -> BeautifulSoup:
    soup=BeautifulSoup(source,'html.parser')
    soup.html['data-concept']=concept_id
    if soup.title: soup.title.string=f"Tony's Dockside — {title.split('—',1)[-1].strip()}"
    for sel in ['#themeSideToggle','#themeSidePanel','#logos']:
        for n in soup.select(sel): n.decompose()
    for main in soup.select('main.concept'):
        if main.get('id') != concept_id:
            main.decompose()
        else:
            cls=[x for x in main.get('class',[]) if x!='active'] + ['active']
            main['class']=cls
    styles=soup.find_all('style')
    for idx in sorted([2,3,4,5], reverse=True):
        if idx < len(styles): styles[idx].decompose()
    for sid in ['logo-gallery-v16-js','theme-side-tab-v22-js']:
        n=soup.find('script',id=sid)
        if n: n.decompose()
    scripts=soup.find_all('script')
    for sc in scripts:
        txt=sc.string if sc.string is not None else sc.get_text()
        if 'const buttons=[...document.querySelectorAll(\'[data-show]\')]' in txt:
            txt=re.sub(
                r"const buttons=\[\.\.\.document\.querySelectorAll\('\[data-show\]'\)\], concepts=\[\.\.\.document\.querySelectorAll\('\.concept'\)\];.*?show\(initialConcept\);",
                f"document.documentElement.dataset.concept='{concept_id}';",
                txt,
                flags=re.S,
            )
            sc.string=txt
    for st in soup.find_all('style'):
        txt=st.string if st.string is not None else st.get_text()
        txt=re.sub(r"@import\s+url\(['\"]?https://fonts\.googleapis\.com/[^;]+;",'',txt,flags=re.I)
        for old,new in FONT_REPLACEMENTS.items(): txt=txt.replace(old,new)
        txt += "\n.progress{top:0!important}\n"
        st.string=txt
    prog=soup.new_tag('div',id='progress')
    prog['class']=['progress']
    soup.body.insert(0,prog)
    marker=soup.new_tag('meta')
    marker['name']='see-it-first-dashboard-design'
    marker['content']=concept_id
    soup.head.append(marker)
    return soup

def localize_assets(soup: BeautifulSoup, target: Path) -> dict:
    asset_dir=target/'assets'; asset_dir.mkdir(parents=True,exist_ok=True)
    html=str(soup)
    urls=[]
    for u in REMOTE_RE.findall(html):
        u=u.rstrip('.,;')
        if is_asset_url(u) and u not in urls: urls.append(u)
    session=requests.Session(); session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; SeeItFirstCreative-Packager/1.0)'})
    mapping={}; ok=0; fall=0
    for i,u in enumerate(urls,1):
        rel,success=fetch_asset(u,asset_dir,i,session)
        mapping[u]=rel
        if success: ok+=1
        else: fall+=1
    html=str(soup)
    for u,rel in mapping.items():
        html=html.replace(u,rel).replace(u.replace('&','&amp;'),rel)
    target.joinpath('index.html').write_text('<!DOCTYPE html>\n'+html,encoding='utf-8')
    return {'downloaded':ok,'fallbacks':fall,'assets':len(mapping)}

def extract_logo_boards(source: str, root: Path, count=4):
    soup=BeautifulSoup(source,'html.parser')
    buttons=soup.select('#logos .logo-thumb')
    out=root/'logo-boards'; out.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,b in enumerate(buttons[:count],1):
        uri=b.get('data-main','')
        m=re.match(r'data:image/([^;]+);base64,(.+)',uri,re.S)
        if not m: raise RuntimeError(f'Logo board {i} data-main missing')
        ext='jpg' if m.group(1).lower() in ('jpeg','jpg') else m.group(1).lower()
        data=base64.b64decode(m.group(2))
        outp=out/f'logo-board-{i:02d}.jpg'
        if ext=='jpg': outp.write_bytes(data)
        else:
            with Image.open(io.BytesIO(data)).convert('RGB') as im: im.save(outp,quality=95)
        with Image.open(outp) as im:
            results.append({'file':outp.name,'size':outp.stat().st_size,'width':im.width,'height':im.height})
    return results

def validate(root: Path) -> dict:
    report={'websites':[],'logos':[],'broken':[],'external_asset_refs':[]}
    signatures=[]
    for concept,folder,title in CONCEPTS:
        idx=root/'websites'/folder/'index.html'
        if not idx.exists(): report['broken'].append(str(idx)); continue
        html=idx.read_text(encoding='utf-8')
        soup=BeautifulSoup(html,'html.parser')
        active=soup.select_one('main.concept.active')
        h1=active.find('h1').get_text(' ',strip=True) if active and active.find('h1') else ''
        signatures.append((concept,h1,hashlib.sha256(html.encode()).hexdigest()))
        banned=['themeSideToggle','themeSidePanel','data-show="','URLSearchParams(location.search)','localStorage']
        for b in banned:
            if b in html: report['broken'].append(f'{folder}: banned switch mechanism {b}')
        if not active or active.get('id')!=concept: report['broken'].append(f'{folder}: wrong active concept')
        for m in re.finditer(r'(?:src|href)=["\']([^"\']+)["\']|url\(["\']?([^"\')]+)|["\'](assets/[^"\']+)["\']',html):
            ref=next((g for g in m.groups() if g),None)
            if not ref or ref.startswith(('#','tel:','mailto:','javascript:','data:')): continue
            if ref.startswith(('http://','https://','//','file://')):
                report['external_asset_refs'].append(f'{folder}:{ref}')
                continue
            ref=ref.split('#',1)[0].split('?',1)[0]
            if ref and not (idx.parent/ref).exists(): report['broken'].append(f'{folder}:{ref}')
        for u in REMOTE_RE.findall(html):
            if is_asset_url(u): report['external_asset_refs'].append(f'{folder}:{u}')
        report['websites'].append({'path':str(idx.relative_to(root)),'concept':concept,'h1':h1,'bytes':idx.stat().st_size})
    if len({x[2] for x in signatures}) != 3: report['broken'].append('website HTML files are not all distinct')
    if len({x[1] for x in signatures}) != 3: report['broken'].append('website hero signatures are not all distinct')
    for p in sorted((root/'logo-boards').glob('logo-board-*.jpg')):
        try:
            with Image.open(p) as im:
                im.verify()
            with Image.open(p) as im:
                report['logos'].append({'file':p.name,'width':im.width,'height':im.height,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        except Exception as e: report['broken'].append(f'{p.name}:{e}')
    if len(report['logos'])!=4: report['broken'].append(f'expected 4 logo boards, got {len(report["logos"])}')
    if len({x['sha256'] for x in report['logos']})!=4: report['broken'].append('logo boards are not all distinct')
    return report

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('source'); ap.add_argument('output_dir'); ap.add_argument('--zip',default='Tonys-Dockside-Presentation-Dashboard.zip')
    args=ap.parse_args()
    src=Path(args.source); outbase=Path(args.output_dir); root=outbase/'client-project'
    if outbase.exists(): shutil.rmtree(outbase)
    root.mkdir(parents=True)
    source=src.read_text(encoding='utf-8')
    for concept,folder,title in CONCEPTS:
        target=root/'websites'/folder; target.mkdir(parents=True,exist_ok=True)
        soup=strip_switching_and_prepare(source,concept,title)
        stats=localize_assets(soup,target)
        log(folder,stats)
    logos=extract_logo_boards(source,root,4); log('logos',logos)
    report=validate(root)
    (outbase/'VALIDATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if report['broken'] or report['external_asset_refs']:
        print(json.dumps(report,indent=2))
        raise SystemExit('validation failed')
    zip_path=outbase/args.zip
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in root.rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(outbase))
    testdir=outbase/'extracted-test'
    if testdir.exists(): shutil.rmtree(testdir)
    testdir.mkdir()
    with zipfile.ZipFile(zip_path) as z: z.extractall(testdir)
    post=validate(testdir/'client-project')
    (outbase/'POST_EXTRACT_VALIDATION.json').write_text(json.dumps(post,indent=2),encoding='utf-8')
    if post['broken'] or post['external_asset_refs']: raise SystemExit('post-extract validation failed')
    print('ZIP',zip_path)
    print(json.dumps(post,indent=2))

if __name__=='__main__': main()
