#!/usr/bin/env python3
"""Targeted semantic and complexity regressions for kopt.

Run with: python3 tests/regressions.py --kit /path/to/Oxygen-Debt-starter
Only Python's standard library and the official kit tools are required.
"""
import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run(command, timeout=30):
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)
    if proc.returncode:
        raise RuntimeError('command failed: ' + ' '.join(map(str, command)) + '\n' + proc.stdout)
    return proc.stdout


def validate(root, kit, machine, source, label, random=300, extra_inputs=()):
    output = source.with_suffix('.optimized.kir')
    run([sys.executable, str(root / 'kopt'), str(source), '--machine', str(machine), '-o', str(output)])
    command = [sys.executable, str(kit / 'kvalidate'), str(output), '--against', str(source),
               '--machine', str(machine), '--random', str(random)]
    for input_file in extra_inputs:
        command.extend(['--input', str(input_file)])
    result = run(command, timeout=60)
    if not result.startswith('OK '):
        raise RuntimeError(label + ' failed official validation:\n' + result)
    print('PASS semantic:', label, flush=True)
    return output


def write_machine(source, destination, **overrides):
    values = {}
    for raw in source.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = int(value.strip())
    values.update(overrides)
    destination.write_text(''.join(f'{key} = {value}\n' for key, value in values.items()), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kit', required=True, type=Path)
    parser.add_argument('--unique-definitions', type=int, default=30000)
    args = parser.parse_args()
    kit = args.kit.resolve()
    root = Path(__file__).resolve().parents[1]
    default = kit / 'machines' / 'machine_default.cfg'

    cases = {
        'loop_multiple_definitions': '''func loop_multiple_definitions(v0)
pre:
  const v1, 2
  const v2, 0
  jmp head
head:
  lt v3, v2, v1
  br v3, body, done
body:
  add v5, v0, 1
  store 0, v5
  add v5, v0, 2
  store 1, v5
  add v2, v2, 1
  jmp head
done:
  ret v0
''',
        'loop_use_before_definition': '''func loop_use_before_definition(v0)
pre:
  const v1, 2
  const v2, 0
  jmp head
head:
  lt v3, v2, v1
  br v3, body, done
body:
  add v8, v7, 1
  store 0, v8
  add v7, v0, 2
  add v2, v2, 1
  jmp head
done:
  ret v0
''',
        'entry_zero_vs_parameter': '''func entry_zero_vs_parameter(v0)
entry:
  add v2, v0, v1
  ret v2
''',
        'self_updating_cse': '''func self_updating_cse(v0)
entry:
  add v0, v0, 1
  add v1, v0, 1
  ret v1
''',
        'self_addressing_load': '''func self_addressing_load(v0)
entry:
  load v0, v0
  load v1, v0
  ret v1
''',
        'mac_temporary_live_after_loop': '''func mac_temporary_live_after_loop(v0)
pre:
  const v4, 0
  const v2, 0
  const v1, 2
  jmp head
head:
  lt v3, v2, v1
  br v3, body, done
body:
  mul v6, v0, v0
  mac v5, v6, v6, v4
  add v4, v5, 1
  add v2, v2, 1
  jmp head
done:
  ret v5
''',
        'mac_temporary_dead_after_use': '''func mac_temporary_dead_after_use(v0)
pre:
  const v4, 0
  const v2, 0
  const v1, 2
  jmp head
head:
  lt v3, v2, v1
  br v3, body, done
body:
  mul v6, v0, v0
  mac v5, v6, v6, v4
  add v4, v5, 1
  add v2, v2, 1
  jmp head
done:
  ret v4
''',
    }
    with tempfile.TemporaryDirectory(prefix='kopt-regressions-') as temp:
        directory = Path(temp)
        slow_licm_mac = directory / 'slow_licm_mac.cfg'
        write_machine(default, slow_licm_mac, lat_mac=8, lat_mul=3, lat_alu=1, fused_mac=1)
        for name, content in cases.items():
            source = directory / (name + '.kir')
            source.write_text(content, encoding='utf-8')
            machine = slow_licm_mac if name.startswith('mac_temporary_') else default
            if name == 'self_addressing_load':
                witness = directory / 'self_addressing_load.in'
                witness.write_text('args 5\nmem 5 10\nmem 10 77\n', encoding='utf-8')
                optimized = validate(root, kit, machine, source, name, extra_inputs=(witness,))
            else:
                optimized = validate(root, kit, machine, source, name)
            contains_mac = '\n  mac ' in optimized.read_text(encoding='utf-8')
            if name == 'mac_temporary_live_after_loop' and not contains_mac:
                raise RuntimeError('MAC temporary with a post-loop use was incorrectly removed')
            if name == 'mac_temporary_dead_after_use' and contains_mac:
                raise RuntimeError('safe MAC temporary pattern was not optimized')

        # Fusion must not increase the dependency-chain latency on a target
        # where the fused instruction exists but is deliberately much slower.
        slow_mac = directory / 'slow_mac.cfg'
        write_machine(default, slow_mac, lat_mul=1, lat_alu=1, lat_mac=10, fused_mac=1)
        fusion_source = directory / 'fusion_latency.kir'
        fusion_source.write_text('''func fusion_latency(v0, v1)
entry:
  mul v2, v0, v1
  add v3, v2, v0
  ret v3
''', encoding='utf-8')
        fusion_output = validate(root, kit, slow_mac, fusion_source, 'slow-fusion-cost-model', random=100)
        if '\n  mac ' in fusion_output.read_text(encoding='utf-8'):
            raise RuntimeError('slow MAC fusion was emitted despite its higher latency')
        print('PASS machine cost: slow fused MAC rejected', flush=True)

        slow_addsh = directory / 'slow_addsh.cfg'
        write_machine(default, slow_addsh, lat_alu=1, lat_addsh=10, fused_addsh=1)
        addsh_source = directory / 'addsh_latency.kir'
        addsh_source.write_text('''func addsh_latency(v0)
entry:
  shl v2, v0, 3
  add v3, v2, v0
  ret v3
''', encoding='utf-8')
        addsh_output = validate(root, kit, slow_addsh, addsh_source, 'slow-addsh-cost-model', random=100)
        if '\n  addsh ' in addsh_output.read_text(encoding='utf-8'):
            raise RuntimeError('slow addsh fusion was emitted despite its higher latency')
        print('PASS machine cost: slow fused addsh rejected', flush=True)

        # Positive controls ensure profitable fusion still occurs; the
        # negative tests above must not accidentally disable fusion entirely.
        fast_mac = directory / 'fast_mac.cfg'
        write_machine(default, fast_mac, lat_mul=3, lat_alu=1, lat_mac=2, fused_mac=1)
        fast_mac_source = directory / 'fast_mac.kir'
        fast_mac_source.write_text('''func fast_mac(v0, v1)
entry:
  mul v2, v0, v1
  add v3, v2, v0
  ret v3
''', encoding='utf-8')
        fast_mac_output = validate(root, kit, fast_mac, fast_mac_source, 'profitable-mac-fusion', random=100)
        if '\n  mac ' not in fast_mac_output.read_text(encoding='utf-8'):
            raise RuntimeError('profitable MAC fusion was not performed')

        fast_addsh = directory / 'fast_addsh.cfg'
        write_machine(default, fast_addsh, lat_alu=1, lat_addsh=1, fused_addsh=1)
        fast_addsh_source = directory / 'fast_addsh.kir'
        fast_addsh_source.write_text('''func fast_addsh(v0)
entry:
  shl v2, v0, 3
  add v3, v2, v0
  ret v3
''', encoding='utf-8')
        fast_addsh_output = validate(root, kit, fast_addsh, fast_addsh_source, 'profitable-addsh-fusion', random=100)
        if '\n  addsh ' not in fast_addsh_output.read_text(encoding='utf-8'):
            raise RuntimeError('profitable addsh fusion was not performed')

        # LICM may replace a repeated MAC with one preheader multiply plus
        # per-iteration adds only when the complete multiply+add chain is no
        # slower than the MAC. A cheap ALU alone is not sufficient evidence.
        slow_mul_mac = directory / 'slow_mul_mac.cfg'
        write_machine(default, slow_mul_mac, lat_alu=1, lat_mul=100, lat_mac=2, fused_mac=1)
        slow_mul_source = directory / 'slow_mul_mac_loop.kir'
        slow_mul_source.write_text('''func slow_mul_mac_loop(v0)
pre:
  const v1, 0
  const v2, 0
  const v3, 4
  jmp head
head:
  lt v4, v2, v3
  br v4, body, done
body:
  add v6, v0, 5
  store 0, v6
  mac v1, v0, v0, v1
  add v2, v2, 1
  jmp head
done:
  ret v1
''', encoding='utf-8')
        slow_mul_output = validate(root, kit, slow_mul_mac, slow_mul_source,
                                   'slow-loop-multiply-cost-model', random=100)
        if '\n  mac ' not in slow_mul_output.read_text(encoding='utf-8'):
            raise RuntimeError('LICM decomposed a MAC despite the slower multiply+add chain')
        print('PASS machine cost: slow loop MAC decomposition rejected', flush=True)

        # Distinct dead definitions exercise cache invalidation without a
        # large live set; the former full-dictionary scans were quadratic.
        count = max(1, args.unique_definitions)
        stress = directory / 'unique_definitions.kir'
        lines = ['func unique_definitions(v0)', 'entry:']
        lines.extend(f'  const v{i}, {i}' for i in range(1, count + 1))
        lines.append('  ret v0')
        stress.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        start = time.monotonic()
        run([sys.executable, str(root / 'kopt'), str(stress), '--machine', str(default),
             '-o', str(directory / 'unique_definitions.out.kir')], timeout=5)
        elapsed = time.monotonic() - start
        print(f'PASS scalability: {count:,} independent definitions in {elapsed:.3f}s', flush=True)
        if elapsed >= 5:
            raise RuntimeError('unique-definition scalability test exceeded 5 seconds')

    print('PASS: all targeted regressions.')


if __name__ == '__main__':
    main()
