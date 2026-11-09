#!/usr/bin/env python3
"""Adversarial, reproducible compliance checks for the Kiln optimizer.

No starter-kit files are copied: pass --kit to use the official tools.  The
cases deliberately exercise structural matching rather than benchmark names.
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(args, timeout=60):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError('command failed:\n' + ' '.join(map(str,args)) + '\n' + p.stdout)
    return p.stdout

def square_program(name, mask=63, fused=True, redundant=False, bound_expr=False):
    # Blocks intentionally appear in a non-execution layout after `pre`.
    # KIR starts at the first block, so only pre remains first.
    r = ('v41','v87','v122','v9')
    n, acc, iv, tmp = r
    m = 'v77' if bound_expr else str(mask)
    setup = (f'  const v77, {mask}\n' if bound_expr else '')
    copies = f'  mov v200, {n}\n  mov {n}, v200\n' if redundant else ''
    body = (f'  mac {acc}, {iv}, {iv}, {acc}\n' if fused else
            f'  mul {tmp}, {iv}, {iv}\n  add {acc}, {acc}, {tmp}\n')
    return f'''func {name}({n})
pre:
{setup}  and {n}, {n}, {m}
{copies}  const {acc}, 0
  mov {iv}, {acc}
  jmp head_x
done_z:
  ret {acc}
body_y:
{body}  add {iv}, {iv}, 1
  jmp head_x
head_x:
  lt {tmp}, {iv}, {n}
  br {tmp}, body_y, done_z
'''

def reject_program(kind):
    if kind == 'cube':
        return square_program('not_square').replace('mac v87, v122, v122, v87', 'mul v9, v122, v122\n  mac v87, v9, v122, v87')
    if kind == 'wide_bound': return square_program('wide_bound', mask=127)
    if kind == 'one_start': return square_program('one_start').replace('const v87, 0\n  mov v122, v87', 'const v87, 0\n  const v122, 1')
    if kind == 'nonzero_acc': return square_program('nonzero_acc').replace('const v87, 0', 'const v87, 1')
    raise ValueError(kind)

def machine(path, **changes):
    cfg = {
        'issue_width': 1, 'mem_ports': 1, 'registers': 4, 'reg_spill_penalty': 9,
        'taken_branch_penalty': 7, 'icache_size': 8, 'icache_penalty': 5,
        'lat_alu': 2, 'lat_mul': 7, 'lat_div': 23, 'lat_load': 11,
        'lat_mac': 8, 'lat_addsh': 3, 'fused_mac': 0, 'fused_addsh': 0,
    }
    cfg.update(changes)
    path.write_text('\n'.join(f'{k} = {v}' for k,v in cfg.items())+'\n', encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--kit',required=True,type=Path); ns=ap.parse_args()
    kit=ns.kit.resolve(); kopt=ROOT/'kopt'; validated=0
    with tempfile.TemporaryDirectory() as td:
        d=Path(td); default=kit/'machines'/'machine_default.cfg'
        equivalents=[
            ('renamed_reordered_fused', square_program('renamed_reordered_fused')),
            ('unfused_square_loop', square_program('unfused_square_loop', fused=False)),
            ('redundant_copies', square_program('redundant_copies', redundant=True)),
            ('constant_mask_register', square_program('constant_mask_register', bound_expr=True)),
            ('different_valid_bound', square_program('different_valid_bound', mask=31)),
        ]
        for name,text in equivalents:
            src=d/(name+'.kir'); out=d/(name+'.out.kir'); src.write_text(text,encoding='utf-8')
            run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(out)])
            run([sys.executable,str(kit/'kvalidate'),str(out),'--against',str(src),'--machine',str(default),'--random','1000'])
            if 'div ' not in out.read_text(encoding='utf-8'):
                raise RuntimeError(name+' was not recognized as a bounded square-sum idiom')
            validated += 1
        for kind in ('cube','wide_bound','one_start','nonzero_acc'):
            src=d/(kind+'.kir'); out=d/(kind+'.out.kir'); src.write_text(reject_program(kind),encoding='utf-8')
            run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(out)])
            run([sys.executable,str(kit/'kvalidate'),str(out),'--against',str(src),'--machine',str(default),'--random','1000'])
            if 'div ' in out.read_text(encoding='utf-8'):
                raise RuntimeError(kind+' incorrectly triggered closed-form replacement')
            validated += 1
        # Unseen machines exercise disabled fusion individually and together.
        for name, changes in [('no_mac',{'fused_addsh':1}), ('no_addsh',{'fused_mac':1}), ('none',{})]:
            cfg=d/(name+'.cfg'); machine(cfg,**changes)
            # Input must itself be valid for the target: use the unfused
            # equivalent when MAC is unavailable.
            src=d/('unfused_square_loop.kir' if not changes.get('fused_mac',0) else 'renamed_reordered_fused.kir'); out=d/(name+'.kir')
            run([sys.executable,str(kopt),str(src),'--machine',str(cfg),'-o',str(out)])
            run([sys.executable,str(kit/'kvalidate'),str(out),'--against',str(src),'--machine',str(cfg),'--random','300'])
            text=out.read_text(encoding='utf-8')
            if not changes.get('fused_mac',0) and '\n  mac ' in text: raise RuntimeError('mac emitted on '+name)
            if not changes.get('fused_addsh',0) and '\n  addsh ' in text: raise RuntimeError('addsh emitted on '+name)
            validated += 1
        # Wrong profiles must not affect output bytes.
        src=d/'renamed_reordered_fused.kir'; bad=d/'wrong.prof'; bad.write_text('edge body_y done_z 999999\n',encoding='utf-8')
        a=d/'profile-a.kir'; b=d/'profile-b.kir'
        run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(a)])
        run([sys.executable,str(kopt),str(src),'--machine',str(default),'--profile',str(bad),'-o',str(b)])
        if a.read_bytes()!=b.read_bytes(): raise RuntimeError('incorrect profile changed output')
        print(f'PASS: {validated} adversarial equivalence/machine cases; wrong-profile determinism verified.')
if __name__=='__main__': main()
