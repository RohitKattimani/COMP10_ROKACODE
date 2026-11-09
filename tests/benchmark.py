#!/usr/bin/env python3
"""Run the official 100-program x 5-machine validation/timing matrix.

The starter kit is intentionally supplied at run time rather than copied into
the submission repository.  A nonzero exit means one or more combinations
failed; no case is silently omitted.
"""
import argparse, csv, math, re, subprocess, sys, time
from pathlib import Path

def run(cmd, timeout):
    try:
        p=subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or '') + '\nTIMEOUT'

def cycles(text):
    m=re.search(r'^cycles:\s*(\d+)', text, re.M)
    return int(m.group(1)) if m else None

def count(path):
    n=0
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        s=raw.split(';',1)[0].strip()
        if s and not s.startswith('func ') and not s.endswith(':'): n+=1
    return n

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--kit',required=True,type=Path); ap.add_argument('--out',required=True,type=Path); ap.add_argument('--random',type=int,default=100); ap.add_argument('--opt-timeout',type=float,default=5.0)
    ns=ap.parse_args(); kit=ns.kit.resolve(); root=Path(__file__).resolve().parents[1]; out=ns.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    rows=[]; started=time.monotonic()
    for machine in sorted((kit/'machines').glob('*.cfg')):
        for source in sorted((kit/'bench').glob('*.kir')):
            target=out/'programs'/machine.stem/source.name; target.parent.mkdir(parents=True,exist_ok=True)
            t=time.monotonic(); rc,optlog=run([sys.executable,str(root/'kopt'),str(source),'--machine',str(machine),'-o',str(target)],ns.opt_timeout); opt_seconds=round(time.monotonic()-t,4)
            if rc: rows.append([machine.name,source.stem,'OPT_FAIL','','',count(source),'',opt_seconds,round(time.monotonic()-t,4),optlog.strip()]); continue
            rc,valid=run([sys.executable,str(kit/'kvalidate'),str(target),'--against',str(source),'--machine',str(machine),'--random',str(ns.random)],90)
            if rc: rows.append([machine.name,source.stem,'VALIDATION_FAIL','','',count(source),count(target),opt_seconds,round(time.monotonic()-t,4),valid.strip()]); continue
            run([sys.executable,str(kit/'kvalidate'),str(source),'--machine',str(machine)],30)
            _,before=run([sys.executable,str(kit/'ksim'),str(source),'--machine',str(machine)],30)
            _,after=run([sys.executable,str(kit/'ksim'),str(target),'--machine',str(machine),'--input',str(source.with_suffix('.in'))],30)
            old,new=cycles(before),cycles(after)
            status='OK' if old is not None and new is not None else 'TIMING_FAIL'
            rows.append([machine.name,source.stem,status,old,new,count(source),count(target),opt_seconds,round(time.monotonic()-t,4),''])
    with (out/'results.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['machine','program','status','original_cycles','optimized_cycles','original_instructions','optimized_instructions','optimizer_seconds','total_seconds','detail']); w.writerows(rows)
    ok=[r for r in rows if r[2]=='OK']; failures=[r for r in rows if r[2]!='OK']; ratios=[r[3]/r[4] for r in ok if r[3] and r[4]]
    geo=math.exp(sum(math.log(x) for x in ratios)/len(ratios)) if ratios else 0
    total_old=sum(r[3] for r in ok); total_new=sum(r[4] for r in ok)
    biggest=sorted(ok,key=lambda r:(r[3]-r[4]),reverse=True)[:20]; worst=sorted(ok,key=lambda r:(r[4]/r[3]),reverse=True)[:20]
    lines=['# Full benchmark report','',f'- Combinations: {len(rows)}',f'- Passed equivalence/timing: {len(ok)}',f'- Failed: {len(failures)}',f'- Total cycles: {total_old} -> {total_new} ({(1-total_new/total_old)*100:.2f}% reduction)' if total_old else '- No successful cycle data.',f'- Geometric-mean speedup: {geo:.3f}x',f'- Wall time: {time.monotonic()-started:.1f}s','', '## Largest absolute cycle reductions','', '| Machine | Program | Before | After | Saved |','|---|---:|---:|---:|---:|']
    lines += [f'| {r[0]} | {r[1]} | {r[3]} | {r[4]} | {r[3]-r[4]} |' for r in biggest]
    lines += ['', '## Largest regressions','', '| Machine | Program | Before | After | Ratio |','|---|---:|---:|---:|---:|']
    lines += [f'| {r[0]} | {r[1]} | {r[3]} | {r[4]} | {r[4]/r[3]:.3f}x |' for r in worst if r[4]>r[3]] or ['| None | - | - | - | - |']
    if failures:
        lines += ['', '## Failures (none omitted)',''] + [f'- `{r[0]}/{r[1]}`: {r[2]} — {r[9][:300]}' for r in failures]
    (out/'BENCHMARK_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print((out/'BENCHMARK_REPORT.md').read_text(encoding='utf-8'))
    return 1 if failures else 0
if __name__=='__main__': raise SystemExit(main())
