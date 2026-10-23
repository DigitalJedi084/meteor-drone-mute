"""Small Motorola 6800 CPU emulator for unit-testing patched ROM routines.

Covers the instruction set used by the game's drone code and the patches (not WAI/SWI/RTI timing,
no interrupts). I/O writes are reported through an `on_write(addr, value)` hook.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dis6800 import OPS, SIZE

C, V, Z, N, I, H = 1, 2, 4, 8, 16, 32

class CPU:
    def __init__(self, mem, on_write=None, on_read=None):
        self.m = mem              # bytearray(0x10000)
        self.a = self.b = 0; self.x = 0; self.sp = 0x01FF; self.pc = 0; self.cc = 0xC0
        self.on_write = on_write; self.on_read = on_read; self.cycles = 0

    # memory ------------------------------------------------------------
    def rd(self, a):
        a &= 0x7FFF                  # MP-200: A15 not decoded
        if self.on_read:
            v = self.on_read(a)
            if v is not None: return v
        return self.m[a]
    def wr(self, a, v):
        a &= 0x7FFF; v &= 0xFF
        if self.on_write: self.on_write(a, v)
        if a < 0x1000: self.m[a] = v  # RAM/IO only; ROM is read-only
    def rd16(self, a): return (self.rd(a) << 8) | self.rd(a + 1)
    def wr16(self, a, v): self.wr(a, v >> 8); self.wr(a + 1, v)
    def push(self, v): self.wr(self.sp, v); self.sp = (self.sp - 1) & 0xFFFF
    def pull(self): self.sp = (self.sp + 1) & 0xFFFF; return self.rd(self.sp)

    # flags -------------------------------------------------------------
    def f(self, flag, cond):
        self.cc = (self.cc | flag) if cond else (self.cc & ~flag)
    def nz8(self, r): self.f(N, r & 0x80); self.f(Z, (r & 0xFF) == 0)
    def nz16(self, r): self.f(N, r & 0x8000); self.f(Z, (r & 0xFFFF) == 0)

    def add(self, a, b, c=0):
        r = a + b + c
        self.f(H, ((a & 0xF) + (b & 0xF) + c) & 0x10)
        self.f(C, r & 0x100); self.f(V, (~(a ^ b) & (a ^ r)) & 0x80); self.nz8(r)
        return r & 0xFF
    def sub(self, a, b, c=0):
        r = a - b - c
        self.f(C, r & 0x100); self.f(V, ((a ^ b) & (a ^ r)) & 0x80); self.nz8(r)
        return r & 0xFF

    # execution ---------------------------------------------------------
    def call(self, addr, max_steps=200000):
        """JSR addr and run until it returns."""
        self.sp = 0x01FF
        self.push(0xFF); self.push(0xFF)          # sentinel return $FFFF
        self.pc = addr
        for _ in range(max_steps):
            if self.pc == 0xFFFF: return
            self.step()
        raise RuntimeError('routine at $%04X did not return' % addr)

    def step(self):
        op = self.rd(self.pc)
        if op not in OPS: raise RuntimeError('illegal opcode %02X at %04X' % (op, self.pc))
        mn, mode = OPS[op]; n = SIZE[mode]; pc0 = self.pc
        self.pc = (self.pc + n) & 0xFFFF; self.cycles += 4
        ea = None; val = None
        if mode == 'imm8': val = self.rd(pc0 + 1)
        elif mode == 'imm16': val = self.rd16(pc0 + 1)
        elif mode == 'dir': ea = self.rd(pc0 + 1)
        elif mode == 'ext': ea = self.rd16(pc0 + 1)
        elif mode == 'idx': ea = (self.x + self.rd(pc0 + 1)) & 0xFFFF
        elif mode == 'rel':
            off = self.rd(pc0 + 1); off = off - 256 if off > 127 else off
            ea = (self.pc + off) & 0xFFFF
        wide = mn in ('LDX', 'LDS', 'CPX', 'STX', 'STS')
        def operand():
            if val is not None: return val
            return self.rd16(ea) if wide else self.rd(ea)
        cc = self.cc

        if mode == 'rel':
            c, v, z, nn = cc & C, cc & V, cc & Z, cc & N
            take = {'BRA': True, 'BSR': True, 'BHI': not (c or z), 'BLS': bool(c or z), 'BCC': not c, 'BCS': bool(c),
                    'BNE': not z, 'BEQ': bool(z), 'BVC': not v, 'BVS': bool(v), 'BPL': not nn, 'BMI': bool(nn),
                    'BGE': bool(nn) == bool(v), 'BLT': bool(nn) != bool(v),
                    'BGT': (not z) and bool(nn) == bool(v), 'BLE': bool(z) or bool(nn) != bool(v)}[mn]
            if mn == 'BSR': self.push(self.pc & 0xFF); self.push(self.pc >> 8)
            if take: self.pc = ea
            return
        r = mn[-1] if mn[-1] in 'AB' and mn not in ('TAB', 'TBA', 'SBA', 'CBA', 'ABA', 'DAA') and len(mn) == 4 else None
        base = mn[:-1] if r else mn
        get = lambda: self.a if r == 'A' else self.b
        def put(v):
            if r == 'A': self.a = v & 0xFF
            else: self.b = v & 0xFF

        if base in ('LDA',): v = operand(); put(v); self.nz8(v); self.f(V, 0)
        elif base == 'STA': self.wr(ea, get()); self.nz8(get()); self.f(V, 0)
        elif base == 'ADD': put(self.add(get(), operand()))
        elif base == 'ADC': put(self.add(get(), operand(), cc & C))
        elif base == 'SUB': put(self.sub(get(), operand()))
        elif base == 'SBC': put(self.sub(get(), operand(), cc & C))
        elif base == 'CMP': self.sub(get(), operand())
        elif base == 'AND': v = get() & operand(); put(v); self.nz8(v); self.f(V, 0)
        elif base == 'BIT': v = get() & operand(); self.nz8(v); self.f(V, 0)
        elif base == 'ORA': v = get() | operand(); put(v); self.nz8(v); self.f(V, 0)
        elif base == 'EOR': v = get() ^ operand(); put(v); self.nz8(v); self.f(V, 0)
        elif base == 'PSH': self.push(get())
        elif base == 'PUL': put(self.pull())
        elif mn in ('NEG', 'COM', 'LSR', 'ROR', 'ASR', 'ASL', 'ROL', 'DEC', 'INC', 'TST', 'CLR') or \
                (r and base in ('NEG', 'COM', 'LSR', 'ROR', 'ASR', 'ASL', 'ROL', 'DEC', 'INC', 'TST', 'CLR')):
            v = get() if r else self.rd(ea)
            if base == 'NEG': v = self.sub(0, v)
            elif base == 'COM': v = (~v) & 0xFF; self.nz8(v); self.f(V, 0); self.f(C, 1)
            elif base == 'LSR': self.f(C, v & 1); v >>= 1; self.nz8(v); self.f(V, (self.cc & N) != (self.cc & C))
            elif base == 'ROR': c0 = cc & C; self.f(C, v & 1); v = (v >> 1) | (0x80 if c0 else 0); self.nz8(v)
            elif base == 'ASR': self.f(C, v & 1); v = (v >> 1) | (v & 0x80); self.nz8(v)
            elif base == 'ASL': self.f(C, v & 0x80); v = (v << 1) & 0xFF; self.nz8(v)
            elif base == 'ROL': c0 = cc & C; self.f(C, v & 0x80); v = ((v << 1) | (1 if c0 else 0)) & 0xFF; self.nz8(v)
            elif base == 'DEC': self.f(V, v == 0x80); v = (v - 1) & 0xFF; self.nz8(v)
            elif base == 'INC': self.f(V, v == 0x7F); v = (v + 1) & 0xFF; self.nz8(v)
            elif base == 'TST': self.nz8(v); self.f(V, 0); self.f(C, 0)
            elif base == 'CLR': v = 0; self.cc = (self.cc & ~(N | V | C)) | Z
            if base != 'TST':
                if r: put(v)
                else: self.wr(ea, v)
        elif mn == 'LDX': self.x = operand(); self.nz16(self.x); self.f(V, 0)
        elif mn == 'LDS': self.sp = operand(); self.nz16(self.sp); self.f(V, 0)
        elif mn == 'STX': self.wr16(ea, self.x); self.nz16(self.x); self.f(V, 0)
        elif mn == 'STS': self.wr16(ea, self.sp); self.nz16(self.sp); self.f(V, 0)
        elif mn == 'CPX':
            v = operand(); r16 = (self.x - v) & 0xFFFF; self.nz16(r16)
            self.f(V, ((self.x ^ v) & (self.x ^ r16)) & 0x8000)
        elif mn == 'INX': self.x = (self.x + 1) & 0xFFFF; self.f(Z, self.x == 0)
        elif mn == 'DEX': self.x = (self.x - 1) & 0xFFFF; self.f(Z, self.x == 0)
        elif mn == 'INS': self.sp = (self.sp + 1) & 0xFFFF
        elif mn == 'DES': self.sp = (self.sp - 1) & 0xFFFF
        elif mn == 'TSX': self.x = (self.sp + 1) & 0xFFFF
        elif mn == 'TXS': self.sp = (self.x - 1) & 0xFFFF
        elif mn == 'TAB': self.b = self.a; self.nz8(self.b); self.f(V, 0)
        elif mn == 'TBA': self.a = self.b; self.nz8(self.a); self.f(V, 0)
        elif mn == 'ABA': self.a = self.add(self.a, self.b)
        elif mn == 'SBA': self.a = self.sub(self.a, self.b)
        elif mn == 'CBA': self.sub(self.a, self.b)
        elif mn == 'TAP': self.cc = self.a | 0xC0
        elif mn == 'TPA': self.a = self.cc | 0xC0
        elif mn == 'CLC': self.f(C, 0)
        elif mn == 'SEC': self.f(C, 1)
        elif mn == 'CLV': self.f(V, 0)
        elif mn == 'SEV': self.f(V, 1)
        elif mn == 'CLI': self.f(I, 0)
        elif mn == 'SEI': self.f(I, 1)
        elif mn == 'NOP': pass
        elif mn == 'JMP': self.pc = ea
        elif mn == 'JSR': self.push(self.pc & 0xFF); self.push(self.pc >> 8); self.pc = ea
        elif mn == 'RTS': hi = self.pull(); lo = self.pull(); self.pc = (hi << 8) | lo
        else: raise RuntimeError('unimplemented %s at %04X' % (mn, pc0))
