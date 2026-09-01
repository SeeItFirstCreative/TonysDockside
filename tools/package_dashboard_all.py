#!/usr/bin/env python3
import hashlib
import package_dashboard as p
from bs4 import BeautifulSoup
p.CONCEPTS=[('harbor','website-01','Website Design 1 — Harbor Response'),('estate','website-02','Website Design 2 — Waterfront Care'),('command','website-03','Website Design 3 — Command Deck'),('mechanical','website-04','Website Design 4 — Mechanical')]
_orig_logos=p.logos
_orig_validate=p.validate
def all_logos(source,root,count=4): return _orig_logos(source,root,6)
p.logos=all_logos
def validate_all(root):
    rep=_orig_validate(root)
    rep['broken']=[e for e in rep['broken'] if e not in ('website HTML files are not all distinct','website hero signatures are not all distinct','logo boards are not all distinct') and not e.startswith('expected 4 logo boards')]
    hashes=[]; heroes=[]
    for concept,folder,title in p.CONCEPTS:
        idx=root/'websites'/folder/'index.html'; hashes.append(hashlib.sha256(idx.read_bytes()).hexdigest())
        s=BeautifulSoup(idx.read_text(encoding='utf-8'),'html.parser'); a=s.select_one('main.concept.active'); heroes.append(a.find('h1').get_text(' ',strip=True) if a and a.find('h1') else '')
    if len(set(hashes))!=len(p.CONCEPTS): rep['broken'].append('website HTML files are not all distinct')
    if len(set(heroes))!=len(p.CONCEPTS): rep['broken'].append('website hero signatures are not all distinct')
    logos=sorted((root/'logo-boards').glob('logo-board-*.jpg'))
    if len(logos)!=6: rep['broken'].append(f'expected 6 logo boards, got {len(logos)}')
    if len({hashlib.sha256(x.read_bytes()).hexdigest() for x in logos})!=6: rep['broken'].append('logo boards are not all distinct')
    return rep
p.validate=validate_all
p.main()
