#!/usr/bin/env python3
from __future__ import annotations
import json, time, hashlib
from pathlib import Path
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

ROOT = Path('dashboard-output/extracted-test/client-project').resolve()
OUT = Path('dashboard-output/browser-test')
OUT.mkdir(parents=True, exist_ok=True)
SITES = [
    ('website-01','harbor','Boat problem? We come to it.'),
    ('website-02','estate','Premium care for the boat at home.'),
    ('website-03','command',"Know what's wrong. Know what happens next."),
]

opts=Options()
opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--disable-gpu')
opts.add_argument('--allow-file-access-from-files')
opts.add_argument('--window-size=1440,1000')
opts.set_capability('goog:loggingPrefs', {'browser':'ALL'})

driver=webdriver.Chrome(options=opts)
reports=[]
pixels=[]
try:
    for folder,expected,h1_expected in SITES:
        idx=ROOT/'websites'/folder/'index.html'
        driver.get(idx.as_uri())
        end=time.time()+15
        while time.time()<end:
            if driver.execute_script('return document.readyState')=='complete': break
            time.sleep(.15)
        time.sleep(.8)
        concept=driver.execute_script('return document.documentElement.dataset.concept || ""')
        active=driver.execute_script('return document.querySelector("main.concept.active")?.id || ""')
        title=driver.title
        h1=driver.execute_script('return document.querySelector("main.concept.active h1")?.innerText.trim() || ""')
        imgs=driver.execute_script('return document.images.length')
        broken=driver.execute_script('return Array.from(document.images).filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.getAttribute("src"))')
        missing=driver.execute_script('return Array.from(document.querySelectorAll("a[href^=\\\"#\\\"]")).map(a=>a.getAttribute("href")).filter(h=>h.length>1&&!document.getElementById(h.slice(1)))')
        resources=driver.execute_script('return performance.getEntriesByType("resource").map(e=>e.name)')
        remote=[r for r in resources if r.startswith(('http://','https://'))]
        reveal=driver.execute_script('return document.querySelectorAll(".reveal.in").length')
        if folder=='website-01':
            before=driver.execute_script('return document.getElementById("hr7RouteTitle")?.textContent || ""')
            driver.execute_script('document.querySelectorAll("[data-route-step]")[1]?.click()')
            time.sleep(.25)
            after=driver.execute_script('return document.getElementById("hr7RouteTitle")?.textContent || ""')
            interaction=bool(after and before!=after); detail=f'{before} -> {after}'
        elif folder=='website-02':
            dots=driver.execute_script('return document.querySelectorAll(".theme-review-dots button").length')
            before=driver.execute_script('return Array.from(document.querySelectorAll(".theme-review-slide")).findIndex(x=>x.classList.contains("active"))')
            driver.execute_script('document.querySelectorAll(".theme-review-dots button")[1]?.click()')
            time.sleep(.2)
            after=driver.execute_script('return Array.from(document.querySelectorAll(".theme-review-slide")).findIndex(x=>x.classList.contains("active"))')
            interaction=bool(dots>=2 and before!=after); detail=f'dots={dots}, active {before}->{after}'
        else:
            before=driver.execute_script('return document.getElementById("cd8Title")?.innerText || ""')
            driver.execute_script('document.querySelectorAll("[data-cd8]")[1]?.click()')
            time.sleep(.25)
            after=driver.execute_script('return document.getElementById("cd8Title")?.innerText || ""')
            interaction=bool(after and before!=after); detail=f'{before[:60]} -> {after[:60]}'
        logs=driver.get_log('browser')
        errors=[x['message'] for x in logs if x.get('level')=='SEVERE' and 'favicon.ico' not in x.get('message','')]
        shot=OUT/f'{folder}.png'; driver.save_screenshot(str(shot))
        im=Image.open(shot).convert('L').resize((64,44)); pixels.append(list(im.getdata()))
        reports.append({
            'path':str(idx.relative_to(ROOT)), 'expected_concept':expected,'concept':concept,'active':active,'title':title,'h1':h1,
            'images':imgs,'broken_images':broken,'remote_resources':remote,'missing_internal_anchors':missing,'reveal_in':reveal,
            'interaction':interaction,'interaction_detail':detail,'browser_errors':errors,'screenshot':shot.name,
            'html_sha256':hashlib.sha256(idx.read_bytes()).hexdigest(),
        })
finally:
    driver.quit()

for i,r in enumerate(reports):
    r['visual_MAD_to_others']=[round(sum(abs(a-b) for a,b in zip(pixels[i],pixels[j]))/len(pixels[i]),2) for j in range(3) if j!=i]

errors=[]
for r,(folder,expected,h1_expected) in zip(reports,SITES):
    if r['concept']!=expected or r['active']!=expected: errors.append(f'{folder}: wrong concept')
    if h1_expected not in r['h1']: errors.append(f'{folder}: unexpected H1 {r["h1"]!r}')
    if r['broken_images']: errors.append(f'{folder}: broken images {r["broken_images"]}')
    if r['remote_resources']: errors.append(f'{folder}: remote resources {r["remote_resources"]}')
    if r['missing_internal_anchors']: errors.append(f'{folder}: missing anchors {r["missing_internal_anchors"]}')
    if not r['interaction']: errors.append(f'{folder}: interaction failed {r["interaction_detail"]}')
    if r['browser_errors']: errors.append(f'{folder}: browser errors {r["browser_errors"]}')
if not all(min(r['visual_MAD_to_others'])>5 for r in reports): errors.append('websites did not meet visual-distinctness threshold')

logos=[]
for p in sorted((ROOT/'logo-boards').glob('logo-board-*.jpg')):
    with Image.open(p) as im: im.verify()
    with Image.open(p) as im:
        logos.append({'file':p.name,'width':im.width,'height':im.height,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
if len(logos)!=4 or len({x['sha256'] for x in logos})!=4: errors.append('logo-board validation failed')

out={'websites':reports,'logo_boards':logos,'errors':errors}
(OUT/'BROWSER_VALIDATION.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
if errors: raise SystemExit(2)
print('DIRECT_FILE_BROWSER_VALIDATION_PASS')
