#!/usr/bin/env python3
"""Generate timing stress programs; standard library only."""
import argparse, subprocess, sys, tempfile, time
from pathlib import Path

def optimize(root, src, machine, limit):
    out=src.with_suffix('.out.kir'); t=time.monotonic()
    try: p=subprocess.run([sys.executable,str(root/'kopt'),str(src),'--machine',str(machine),'-o',str(out)],timeout=limit)
    except subprocess.TimeoutExpired: raise RuntimeError(f'{src.name} exceeded {limit}s')
    if p.returncode: raise RuntimeError(f'{src.name} failed')
    elapsed=time.monotonic()-t
    if elapsed >= limit: raise RuntimeError(f'{src.name} exceeded {limit}s')
    print(f'{src.name}: {elapsed:.3f}s')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--machine',required=True); ap.add_argument('--instructions',type=int,default=100000); ap.add_argument('--live',type=int,default=1000); ns=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as d:
        src=Path(d)/'large.kir'
        lines=['func stress(v0)','entry:']
        # Each line is semantically useful, avoiding a misleading parser-only test.
        for _ in range(ns.instructions-1): lines.append('  add v0, v0, 1')
        lines.append('  ret v0'); src.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        optimize(root,src,ns.machine,30)
        # Simultaneously live values stress liveness, interference, and
        # coloring.  Each definition remains live until the final reduction.
        live=Path(d)/'live.kir'; lines=['func live_stress(v0)','entry:']
        for i in range(ns.live): lines.append(f'  add v{i+1}, v0, {i}')
        lines.append('  const v0, 0')
        for i in range(ns.live): lines.append(f'  add v0, v0, v{i+1}')
        lines.append('  ret v0'); live.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        optimize(root,live,ns.machine,5)
        return 0
if __name__=='__main__': raise SystemExit(main())
