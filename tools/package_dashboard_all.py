#!/usr/bin/env python3
import sys
import package_dashboard as p
p.CONCEPTS=[('harbor','website-01','Website Design 1 — Harbor Response'),('estate','website-02','Website Design 2 — Waterfront Care'),('command','website-03','Website Design 3 — Command Deck'),('mechanical','website-04','Website Design 4 — Mechanical')]
_orig=p.logos
def all_logos(source,root,count=4): return _orig(source,root,6)
p.logos=all_logos
p.main()
