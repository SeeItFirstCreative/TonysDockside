#!/usr/bin/env python3
import json,time,hashlib
from pathlib import Path
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
ROOT=Path('dashboard-output/extracted-test/client-project').resolve(); OUT=Path('dashboard-output/browser-test-all'); OUT.mkdir(parents=True,exist_ok=True)
SITES=[('website-01','harbor'),('website-02','estate'),('website-03','command'),('website-04','mechanical')]
opts=Options(); [opts.add_argument(x) for x in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--allow-file-access-from-files','--window-size=1440,1000']]; opts.set_capability('goog:loggingPrefs',{'browser':'ALL'})
d=webdriver.Chrome(options=opts); reports=[]; pixels=[]
try:
 for folder,expected in SITES:
  idx=ROOT/'websites'/folder/'index.html'; d.get(idx.as_uri()); time.sleep(1.2)
  concept=d.execute_script('return document.documentElement.dataset.concept||""'); active=d.execute_script('return document.querySelector("main.concept.active")?.id||""'); h1=d.execute_script('return document.querySelector("main.concept.active h1")?.innerText.trim()||""')
  broken=d.execute_script('return Array.from(document.images).filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.getAttribute("src"))'); resources=d.execute_script('return performance.getEntriesByType("resource").map(e=>e.name).filter(x=>x.startsWith("http://")||x.startsWith("https://"))'); logs=[x['message'] for x in d.get_log('browser') if x.get('level')=='SEVERE' and 'favicon.ico' not in x.get('message','')]
  shot=OUT/f'{folder}.png'; d.save_screenshot(str(shot)); im=Image.open(shot).convert('L').resize((64,44)); pixels.append(list(im.getdata())); reports.append({'path':str(idx.relative_to(ROOT)),'concept':concept,'active':active,'h1':h1,'broken_images':broken,'remote_resources':resources,'browser_errors':logs,'html_sha256':hashlib.sha256(idx.read_bytes()).hexdigest()})
finally:d.quit()
for i,r in enumerate(reports): r['visual_MAD_to_others']=[round(sum(abs(a-b) for a,b in zip(pixels[i],pixels[j]))/len(pixels[i]),2) for j in range(len(reports)) if j!=i]
errors=[]
for r,(folder,expected) in zip(reports,SITES):
 if r['concept']!=expected or r['active']!=expected:errors.append(f'{folder}: wrong concept')
 if r['broken_images']:errors.append(f'{folder}: broken images')
 if r['remote_resources']:errors.append(f'{folder}: remote resources')
 if r['browser_errors']:errors.append(f'{folder}: browser errors {r["browser_errors"]}')
if len({r['html_sha256'] for r in reports})!=4:errors.append('website HTML files not distinct')
if not all(min(r['visual_MAD_to_others'])>5 for r in reports):errors.append('websites not visually distinct')
logos=[]
for p in sorted((ROOT/'logo-boards').glob('logo-board-*.jpg')):
 with Image.open(p) as im: im.verify()
 with Image.open(p) as im: logos.append({'file':p.name,'width':im.width,'height':im.height,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
if len(logos)!=6 or len({x['sha256'] for x in logos})!=6:errors.append('logo-board validation failed')
out={'websites':reports,'logo_boards':logos,'errors':errors}; (OUT/'BROWSER_VALIDATION.json').write_text(json.dumps(out,indent=2)); print(json.dumps(out,indent=2));
if errors:raise SystemExit(2)
print('ALL_VARIATIONS_BROWSER_VALIDATION_PASS')
