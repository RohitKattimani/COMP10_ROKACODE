#!/usr/bin/env python3
"""Generate and optimize a 100k-instruction KIR program; standard library only."""
import argparse, subprocess, sys, tempfile, time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--machine',required=True); ap.add_argument('--instructions',type=int,default=100000); ns=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as d:
        src=Path(d)/'large.kir'; out=Path(d)/'out.kir'
        lines=['func stress(v0)','entry:']
        # Each line is semantically useful, avoiding a misleading parser-only test.
        for _ in range(ns.instructions-1): lines.append('  add v0, v0, 1')
        lines.append('  ret v0'); src.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        t=time.monotonic(); p=subprocess.run([sys.executable,str(root/'kopt'),str(src),'--machine',ns.machine,'-o',str(out)]); elapsed=time.monotonic()-t
        if p.returncode: return p.returncode
        print(f'{ns.instructions} instructions optimized in {elapsed:.3f}s')
        return 0 if elapsed < 30 else 1
if __name__=='__main__': raise SystemExit(main())
