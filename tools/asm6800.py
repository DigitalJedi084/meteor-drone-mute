"""Tiny two-pass Motorola 6800 assembler (enough for the Meteor background-sound patches).

Syntax per line:  [label:] MNEMONIC operand   ; comment
  operand: #imm, addr (direct if < $100 and a direct form exists; prefix '>' to force extended),
           n,X  (indexed), label/expr for branches.  Numbers: $hex, %bin, decimal, 'c'.
  Directives: ORG addr, FCB b,b,..., FDB w,w,..., EQU (label: EQU value)
Expressions: + - * / >> << & | with labels, and lo(x) / hi(x).
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from dis6800 import OPS, SIZE

REV = {}
for code, (mn, mode) in OPS.items():
    REV[(mn, mode)] = code
BRANCH = {mn for (mn, mode) in REV if mode == 'rel'}
WIDE = {'LDX', 'LDS', 'CPX'}

def num(tok, syms):
    expr = tok.strip()
    expr = re.sub(r'\$([0-9A-Fa-f]+)', lambda m: str(int(m.group(1), 16)), expr)
    expr = re.sub(r'%([01]+)', lambda m: str(int(m.group(1), 2)), expr)
    expr = re.sub(r"'(.)'", lambda m: str(ord(m.group(1))), expr)
    def sym(m):
        s = m.group(0)
        if s in ('lo', 'hi'): return s
        if s not in syms: raise KeyError(s)
        return str(syms[s])
    expr = re.sub(r'[A-Za-z_][A-Za-z0-9_]*', sym, expr)
    return int(eval(expr, {'lo': lambda v: v & 0xFF, 'hi': lambda v: (v >> 8) & 0xFF}))

def assemble(src):
    lines = []
    for raw in src.splitlines():
        line = raw.split(';')[0].rstrip()
        if not line.strip(): continue
        label = None
        m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$', line)
        if m: label, line = m.group(1), m.group(2)
        parts = line.split(None, 1)
        mn = parts[0].upper() if parts else ''
        arg = parts[1].strip() if len(parts) > 1 else ''
        lines.append((label, mn, arg, raw))

    def size_of(mn, arg, syms, final):
        if mn == 'FCB': return len(arg.split(','))
        if mn == 'FDB': return 2 * len(arg.split(','))
        if mn in ('ORG', 'EQU', ''): return 0
        return SIZE[mode_of(mn, arg, syms, final)]

    def mode_of(mn, arg, syms, final):
        if mn in BRANCH: return 'rel'
        if not arg: return 'inh'
        if arg.startswith('#'): return 'imm16' if mn in WIDE else 'imm8'
        if arg.upper().endswith(',X'): return 'idx'
        if arg.startswith('>'): return 'ext'
        try: v = num(arg, syms)
        except KeyError:
            if final: raise
            return 'ext'
        return 'dir' if v < 0x100 and (mn, 'dir') in REV else 'ext'

    syms = {}
    for final in (False, True):
        pc = 0; out = {}
        for label, mn, arg, raw in lines:
            if mn == 'EQU':
                syms[label] = num(arg, syms); continue
            if mn == 'ORG':
                pc = num(arg, syms)
            if label: syms[label] = pc
            if mn == 'ORG' or not mn: continue
            n = size_of(mn, arg, syms, final)
            if final:
                if mn == 'FCB':
                    bs = [num(a, syms) & 0xFF for a in arg.split(',')]
                elif mn == 'FDB':
                    bs = []
                    for a in arg.split(','):
                        v = num(a, syms); bs += [(v >> 8) & 0xFF, v & 0xFF]
                else:
                    mode = mode_of(mn, arg, syms, True)
                    if (mn, mode) not in REV: raise SyntaxError('bad mode %s %s: %s' % (mn, mode, raw))
                    bs = [REV[(mn, mode)]]
                    a = arg.lstrip('#>')
                    if mode == 'imm8' or mode == 'dir': bs.append(num(a, syms) & 0xFF)
                    elif mode in ('imm16', 'ext'):
                        v = num(a, syms) & 0xFFFF; bs += [v >> 8, v & 0xFF]
                    elif mode == 'idx': bs.append(num(a[:-2] or '0', syms) & 0xFF)
                    elif mode == 'rel':
                        off = num(a, syms) - (pc + 2)
                        if not -128 <= off <= 127: raise SyntaxError('branch out of range: ' + raw)
                        bs.append(off & 0xFF)
                for i, b in enumerate(bs):
                    if pc + i in out: raise SyntaxError('$%04X assembled twice (ORG overlap): %s' % (pc + i, raw))
                    out[pc + i] = b
            pc += n
    return out, syms

if __name__ == '__main__':
    out, syms = assemble(open(sys.argv[1]).read())
    lo, hi = min(out), max(out)
    print('$%04X-$%04X (%d bytes)' % (lo, hi, len(out)))
