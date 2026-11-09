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
    if kind == 'bound_overwrite':
        # Bounded enough for exhaustive official random validation, but no
        # longer proven <=63 after the overwrite.
        return square_program('bound_overwrite').replace('  const v87, 0', '  add v41, v41, 64\n  const v87, 0')
    if kind == 'acc_iv_alias':
        return '''func acc_iv_alias(v0)
pre:
  and v3, v0, 63
  const v2, 0
  jmp head
head:
  lt v1, v2, v3
  br v1, body, done
body:
  mac v2, v2, v2, v2
  add v2, v2, 1
  jmp head
done:
  ret v2
'''
    raise ValueError(kind)

def tiny(name, body, params='v0, v1'):
    return f'func {name}({params})\nentry:\n' + '\n'.join('  '+x for x in body) + '\n'

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
            print('equivalent:', name, flush=True)
            src=d/(name+'.kir'); out=d/(name+'.out.kir'); src.write_text(text,encoding='utf-8')
            run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(out)])
            run([sys.executable,str(kit/'kvalidate'),str(out),'--against',str(src),'--machine',str(default),'--random','1000'])
            if 'div ' not in out.read_text(encoding='utf-8'):
                raise RuntimeError(name+' was not recognized as a bounded square-sum idiom')
            validated += 1
        for kind in ('cube','wide_bound','one_start','nonzero_acc','bound_overwrite','acc_iv_alias'):
            print('reject:', kind, flush=True)
            src=d/(kind+'.kir'); out=d/(kind+'.out.kir'); src.write_text(reject_program(kind),encoding='utf-8')
            run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(out)])
            run([sys.executable,str(kit/'kvalidate'),str(out),'--against',str(src),'--machine',str(default),'--random','1000'])
            if 'div ' in out.read_text(encoding='utf-8'):
                raise RuntimeError(kind+' incorrectly triggered closed-form replacement')
            validated += 1
        # The audit's literal large-overwrite witness is intentionally not
        # run through thousands of 100k-iteration executions.  Check the
        # required compiler property directly: it must not trigger the
        # closed form after `and n, ..., 63; add n, n, 100000`.
        text=reject_program('bound_overwrite').replace('64', '100000', 1)
        src=d/'bound_overwrite_large.kir'; out=d/'bound_overwrite_large.out.kir'; src.write_text(text,encoding='utf-8')
        run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(out)])
        if 'div ' in out.read_text(encoding='utf-8'):
            raise RuntimeError('large bound overwrite incorrectly triggered closed-form replacement')
        # Folded arithmetic, wrapping, signed division/modulus, and equality
        # identities must agree with the official interpreter, not a local
        # expected-value oracle.
        fold_cases=[
            ('add', ['add v2, 5, 7','ret v2']), ('sub',['sub v2, 5, 7','ret v2']),
            ('mul_wrap',['mul v2, 4294967295, 2','ret v2']), ('and',['and v2, 240, 15','ret v2']),
            ('or',['or v2, 240, 15','ret v2']), ('xor',['xor v2, 240, 15','ret v2']),
            ('shl',['shl v2, 1, 33','ret v2']), ('shr',['shr v2, 2147483648, 31','ret v2']),
            ('lt_signed',['lt v2, -1, 1','ret v2']), ('eq_same',['eq v2, v0, v0','ret v2']),
            ('lt_same',['lt v2, v0, v0','ret v2']), ('select',['select v2, 0, 7, 9','ret v2']),
            ('div_signed',['div v2, -7, 2','ret v2']), ('mod_signed',['mod v2, -7, 2','ret v2']),
        ]
        for name,body in fold_cases:
            print('fold:', name, flush=True)
            src=d/(name+'.kir'); out=d/(name+'.out.kir'); src.write_text(tiny(name,body),encoding='utf-8')
            run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(out)])
            run([sys.executable,str(kit/'kvalidate'),str(out),'--against',str(src),'--machine',str(default),'--random','300'])
            validated += 1
        # Potentially trapping operations and volatile ordering must remain.
        effects=tiny('effects',[
            'vload v2, 0','vstore 1, v2','store 0, v2','div v3, v0, v1','load v4, v3','ret v4'])
        src=d/'effects.kir'; out=d/'effects.out.kir'; src.write_text(effects,encoding='utf-8')
        run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(out)])
        run([sys.executable,str(kit/'kvalidate'),str(out),'--against',str(src),'--machine',str(default),'--random','500'])
        validated += 1
        # LICM MAC-rewrite near-misses: both forms were previously unsafe.
        for tag, add in [('temp_twice','add v4, v5, v5'), ('acc_alias','add v4, v5, v4')]:
            print('licm:', tag, flush=True)
            prog=f'''func {tag}(v0)
pre:
  and v0, v0, 15
  const v4, 0
  const v2, 0
  jmp head
head:
  lt v1, v2, v0
  br v1, body, done
body:
  mac v5, 3, 3, v4
  {add}
  add v2, v2, 1
  jmp head
done:
  ret v4
'''
            src=d/(tag+'.kir'); out=d/(tag+'.out.kir'); src.write_text(prog,encoding='utf-8')
            run([sys.executable,str(kopt),str(src),'--machine',str(default),'-o',str(out)])
            run([sys.executable,str(kit/'kvalidate'),str(out),'--against',str(src),'--machine',str(default),'--random','500'])
            validated += 1
        # Unseen machines exercise disabled fusion individually and together.
        for name, changes in [('no_mac',{'fused_addsh':1}), ('no_addsh',{'fused_mac':1}), ('none',{})]:
            print('machine:', name, flush=True)
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
