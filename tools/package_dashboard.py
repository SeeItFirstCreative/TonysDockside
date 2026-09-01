#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, hashlib, io, json, re, shutil, urllib.parse, zipfile
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from PIL import Image, ImageDraw

CONCEPTS=[('harbor','website-01','Website Design 1 — Harbor Response'),('estate','website-02','Website Design 2 — Waterfront Care'),('command','website-03','Website Design 3 — Command Deck')]
REMOTE_RE=re.compile(r"https?://[^\s\"'()<>|]+")
CSS_URL_RE=re.compile(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)",re.I)
IMG_EXTS={'.jpg','.jpeg','.png','.webp','.gif','.avif','.svg'}
FONT_REPLACEMENTS={"'DM Sans'":"Arial, Helvetica, sans-serif","'Manrope'":"Arial, Helvetica, sans-serif","'Barlow Condensed'":"'Arial Narrow', Arial, sans-serif","'Playfair Display'":"Georgia, 'Times New Roman', serif","'Space Mono'":"'Courier New', monospace"}

def log(*a): print(*a,flush=True)
def make_fallback(path,label,size=(1600,1000)):
 path.parent.mkdir(parents=True,exist_ok=True); im=Image.new('RGB',size,(9,28,39)); d=ImageDraw.Draw(im)
 for y in range(0,size[1],100): d.line((0,y,size[0],y),fill=(24,62,77),width=1)
 for x in range(0,size[0],100): d.line((x,0,x,size[1]),fill=(24,62,77),width=1)
 d.rectangle((70,70,size[0]-70,size[1]-70),outline=(255,141,58),width=4); d.rectangle((105,size[1]-260,size[0]-105,size[1]-105),fill=(10,35,48)); d.text((125,size[1]-225),"TONY'S DOCKSIDE",fill='white'); d.text((125,size[1]-185),label[:90],fill=(102,200,235)); im.save(path,quality=88)
def norm(u): return u.replace('&amp;','&')
def is_asset(u):
 if u=='http://www.w3.org/2000/svg': return False
 p=urllib.parse.urlparse(norm(u)); ext=Path(p.path).suffix.lower()
 if 'fonts.googleapis.com' in p.netloc or 'fonts.gstatic.com' in p.netloc:return False
 return ext in IMG_EXTS or any(h in p.netloc for h in ['images.unsplash.com','images.squarespace-cdn.com','photos.zillowstatic.com','mymarcorental.com','luxuryofnaples.com','media.vrbo.com','supabase.co','blob.core.windows.net','boatguys.com','powerandmotoryacht.com','boatrepairmiamifl.com','bestmarinesurveyor.com','wixstatic.com'])
def ext_for(url,ct):
 ct=(ct or '').split(';')[0].strip().lower(); m={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','image/gif':'.gif','image/svg+xml':'.svg','image/avif':'.avif'}
 if ct in m:return m[ct]
 e=Path(urllib.parse.urlparse(url).path).suffix.lower(); return '.jpg' if e=='.jpeg' else (e if e in IMG_EXTS else '.jpg')
def fetch_asset(url,asset_dir,idx,s):
 u=norm(url); stem=f"media-{idx:02d}-{hashlib.sha1(u.encode()).hexdigest()[:10]}"
 try:
  r=s.get(u,timeout=25,allow_redirects=True,headers={'Referer':urllib.parse.urlunparse((*urllib.parse.urlparse(u)[:2],'','','',''))}); r.raise_for_status(); e=ext_for(u,r.headers.get('content-type')); p=asset_dir/(stem+e); p.write_bytes(r.content)
  if e!='.svg':
   try:
    with Image.open(p) as im: im.verify()
   except Exception: p.unlink(missing_ok=True); p=asset_dir/(stem+'.jpg'); make_fallback(p,urllib.parse.urlparse(u).netloc); return f'assets/{p.name}',False
  return f'assets/{p.name}',True
 except Exception as er:
  p=asset_dir/(stem+'.jpg'); make_fallback(p,urllib.parse.urlparse(u).netloc); log(' fallback:',u,'->',er); return f'assets/{p.name}',False
def prepare(source,cid,title):
 soup=BeautifulSoup(source,'html.parser'); soup.html['data-concept']=cid
 if soup.title:soup.title.string=f"Tony's Dockside — {title.split('—',1)[-1].strip()}"
 for sel in ['#themeSideToggle','#themeSidePanel','#logos']:
  for n in soup.select(sel):n.decompose()
 for m in soup.select('main.concept'):
  if m.get('id')!=cid:m.decompose()
  else:m['class']=[x for x in m.get('class',[]) if x!='active']+['active']
 styles=soup.find_all('style')
 for i in sorted([2,3,4,5],reverse=True):
  if i<len(styles):styles[i].decompose()
 for sid in ['logo-gallery-v16-js','theme-side-tab-v22-js']:
  n=soup.find('script',id=sid)
  if n:n.decompose()
 for sc in soup.find_all('script'):
  txt=sc.string if sc.string is not None else sc.get_text()
  if "const buttons=[...document.querySelectorAll('[data-show]')]" in txt:
   txt=re.sub(r"const buttons=\[\.\.\.document\.querySelectorAll\('\[data-show\]'\)\], concepts=\[\.\.\.document\.querySelectorAll\('\.concept'\)\];.*?show\(initialConcept\);",f"document.documentElement.dataset.concept='{cid}';",txt,flags=re.S); sc.string=txt
 for st in soup.find_all('style'):
  txt=st.string if st.string is not None else st.get_text(); txt=re.sub(r"@import\s+url\(['\"]?https://fonts\.googleapis\.com/[^;]+;",'',txt,flags=re.I)
  for a,b in FONT_REPLACEMENTS.items():txt=txt.replace(a,b)
  st.string=txt+'\n.progress{top:0!important}\n'
 prog=soup.new_tag('div',id='progress'); prog['class']=['progress']; soup.body.insert(0,prog); marker=soup.new_tag('meta'); marker['name']='see-it-first-dashboard-design'; marker['content']=cid; soup.head.append(marker); return soup
def localize(soup,target):
 ad=target/'assets'; ad.mkdir(parents=True,exist_ok=True); html=str(soup); urls=[]
 for u in REMOTE_RE.findall(html):
  u=u.rstrip('.,;')
  if is_asset(u) and u not in urls:urls.append(u)
 s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; SeeItFirstCreative-Packager/1.0)'}); mp={}; ok=fall=0
 for i,u in enumerate(urls,1):
  rel,good=fetch_asset(u,ad,i,s); mp[u]=rel; ok+=int(good); fall+=int(not good)
 for u,rel in mp.items():html=html.replace(u,rel).replace(u.replace('&','&amp;'),rel)
 target.joinpath('index.html').write_text('<!DOCTYPE html>\n'+html,encoding='utf-8'); return {'downloaded':ok,'fallbacks':fall,'assets':len(mp)}
def logos(source,root,count=4):
 soup=BeautifulSoup(source,'html.parser'); buttons=soup.select('#logos .logo-thumb'); out=root/'logo-boards'; out.mkdir(parents=True,exist_ok=True); res=[]
 for i,b in enumerate(buttons[:count],1):
  m=re.match(r'data:image/([^;]+);base64,(.+)',b.get('data-main',''),re.S)
  if not m:raise RuntimeError(f'Logo board {i} missing')
  data=base64.b64decode(m.group(2)); p=out/f'logo-board-{i:02d}.jpg'
  if m.group(1).lower() in ('jpeg','jpg'):p.write_bytes(data)
  else:
   with Image.open(io.BytesIO(data)).convert('RGB') as im:im.save(p,quality=95)
  with Image.open(p) as im:res.append({'file':p.name,'size':p.stat().st_size,'width':im.width,'height':im.height})
 return res
def validate(root):
 rep={'websites':[],'logos':[],'broken':[],'external_asset_refs':[]}; sig=[]
 for concept,folder,title in CONCEPTS:
  idx=root/'websites'/folder/'index.html'
  if not idx.exists():rep['broken'].append(str(idx));continue
  html=idx.read_text(encoding='utf-8'); soup=BeautifulSoup(html,'html.parser'); active=soup.select_one('main.concept.active'); h1=active.find('h1').get_text(' ',strip=True) if active and active.find('h1') else ''; sig.append((concept,h1,hashlib.sha256(html.encode()).hexdigest()))
  for b in ['themeSideToggle','themeSidePanel','data-show="','URLSearchParams(location.search)','localStorage']:
   if b in html:rep['broken'].append(f'{folder}: banned switch mechanism {b}')
  if not active or active.get('id')!=concept:rep['broken'].append(f'{folder}: wrong active concept')
  refs=[]
  for tag in soup.find_all(True):
   for attr in ('src','href','poster'):
    if tag.has_attr(attr):refs.append(str(tag[attr]))
  for st in soup.find_all('style'):
   txt=st.string if st.string is not None else st.get_text(); refs += [m.group(2) for m in CSS_URL_RE.finditer(txt)]
  for tag in soup.find_all(style=True):refs += [m.group(2) for m in CSS_URL_RE.finditer(tag.get('style',''))]
  for ref in refs:
   ref=ref.strip()
   if not ref or ref.startswith(('#','tel:','mailto:','javascript:','data:')):continue
   if ref.startswith(('http://','https://','//','file://')):rep['external_asset_refs'].append(f'{folder}:{ref}');continue
   clean=ref.split('#',1)[0].split('?',1)[0]
   if clean and not (idx.parent/clean).exists():rep['broken'].append(f'{folder}:{clean}')
  for u in REMOTE_RE.findall(html):
   if is_asset(u):rep['external_asset_refs'].append(f'{folder}:{u}')
  rep['websites'].append({'path':str(idx.relative_to(root)),'concept':concept,'h1':h1,'bytes':idx.stat().st_size})
 if len({x[2] for x in sig})!=3:rep['broken'].append('website HTML files are not all distinct')
 if len({x[1] for x in sig})!=3:rep['broken'].append('website hero signatures are not all distinct')
 for p in sorted((root/'logo-boards').glob('logo-board-*.jpg')):
  try:
   with Image.open(p) as im:im.verify()
   with Image.open(p) as im:rep['logos'].append({'file':p.name,'width':im.width,'height':im.height,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
  except Exception as e:rep['broken'].append(f'{p.name}:{e}')
 if len(rep['logos'])!=4:rep['broken'].append(f'expected 4 logo boards, got {len(rep["logos"])}')
 if len({x['sha256'] for x in rep['logos']})!=4:rep['broken'].append('logo boards are not all distinct')
 return rep
def main():
 ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('output_dir');ap.add_argument('--zip',default='Tonys-Dockside-Presentation-Dashboard.zip');args=ap.parse_args();out=Path(args.output_dir);root=out/'client-project'
 if out.exists():shutil.rmtree(out)
 root.mkdir(parents=True);source=Path(args.source).read_text(encoding='utf-8')
 for c,f,t in CONCEPTS:
  target=root/'websites'/f;target.mkdir(parents=True,exist_ok=True);log(f,localize(prepare(source,c,t),target))
 log('logos',logos(source,root,4));rep=validate(root);(out/'VALIDATION.json').write_text(json.dumps(rep,indent=2),encoding='utf-8')
 if rep['broken'] or rep['external_asset_refs']:print(json.dumps(rep,indent=2));raise SystemExit('validation failed')
 zp=out/args.zip
 with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in root.rglob('*'):
   if p.is_file():z.write(p,p.relative_to(out))
 td=out/'extracted-test';td.mkdir()
 with zipfile.ZipFile(zp) as z:z.extractall(td)
 post=validate(td/'client-project');(out/'POST_EXTRACT_VALIDATION.json').write_text(json.dumps(post,indent=2),encoding='utf-8')
 if post['broken'] or post['external_asset_refs']:raise SystemExit('post-extract validation failed')
 print('ZIP',zp);print(json.dumps(post,indent=2))
if __name__=='__main__':main()
