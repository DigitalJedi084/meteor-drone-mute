"""Run a patched meteorb ROM's background-sound code in the 6800 emulator and render what PinMAME's
SB-300 model would play.

Usage: python simulate.py <meteorb.zip> <out.wav> [seconds]

The game itself isn't emulated. The harness reproduces only what touches the background sound:
  - bytecode op $55 calls $50B7 at game start
  - the 120 Hz IRQ counts down $48 (score hold) and, every 4th tick, $5D; $5D hitting 0 runs $50ED
  - scoring sets $48 = $FF (bursts of scoring, then quiet stretches)
  - sound effects: $6D set non-zero, an effect tone plays, then the STOP opcode resets the
    timers and calls $50CC (game in progress)
"""
import os, sys, wave, zipfile
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from emu6800 import CPU
from sb300_preview import VOLTAB, Q1WAVE, NOISE, LEVEL, SR, CLK

class Board:
    """SB-300 as PinMAME models it (src/wpc/stsnd.c), driven by CPU writes."""
    def __init__(self):
        self.ax = [0] * 8; self.cr1 = self.cr2 = self.cr3 = 0; self.reset = 0
        self.lat = [0, 0, 0]; self.c0 = 0; self.volnr = 0; self.dir = 0; self.vol = 0
        self.q3acc = 0.0; self.p1 = self.p2 = 0.0; self.pn = 0; self.out = []; self.log = []
        self.t1_used = False

    def write(self, addr, v):
        if 0xA0 <= addr <= 0xA7:
            n = addr - 0xA0; self.ax[n] = v
            if n in (3, 5, 7): self.lat[(n - 3) // 2] = self.ax[n - 1] * 256 + v
            if n == 1:
                self.cr2 = v
                if not v & 0x80: self.volnr = 0
            if n == 0:
                if self.cr2 & 1:
                    self.cr1 = v; self.reset = v & 1; self.t1_used |= bool(v & 0x80)
                else:
                    self.cr3 = v
        elif addr == 0xC0:
            self.c0 = v; self.dir = v & 1; self.volnr = 1; self.q3acc = 0.0; self.vol = self.setvol()
        else:
            return
        self.log.append((addr, v))

    def setvol(self):
        if self.volnr == 0: return 0
        return VOLTAB[self.volnr] if self.dir else VOLTAB[17 - self.volnr]

    def nextvol(self):
        if 0 < self.volnr <= 16: self.volnr += 1
        if self.volnr > 16:
            if not self.c0 & 4:
                if not self.dir: self.volnr = 0
            else:
                self.volnr = 1
                if self.c0 & 2: self.dir ^= 1
        self.vol = self.setvol()

    def render(self, secs):
        n = int(round(secs * SR)); buf = np.zeros(n); blk = 48
        for s in range(0, n, blk):
            m = min(blk, n - s); t = np.arange(m)
            if self.cr3 & 0x80 and not self.reset and self.lat[2]:
                self.q3acc += m / SR; step = 2 * (self.lat[2] + 1) / CLK
                while self.q3acc >= step: self.q3acc -= step; self.nextvol()
            if self.cr1 & 0x80 and not self.reset and self.lat[0]:
                f = CLK / (2 * (self.lat[0] + 1)); ph = self.p1 + t * f / SR
                buf[s:s + m] += 0.7 * LEVEL * Q1WAVE[((ph % 1) * 16).astype(int)]; self.p1 = (self.p1 + m * f / SR) % 1
            v = self.vol / 100.0
            if self.cr2 & 0x80 and not self.reset and self.lat[1] and v:
                f = CLK / (2 * (self.lat[1] + 1)); ph = self.p2 + t * f / SR
                buf[s:s + m] += v * LEVEL * np.where(ph % 1 < 0.5, 1.0, -1.0); self.p2 = (self.p2 + m * f / SR) % 1
            if self.c0 & 8 and v:
                tab = NOISE[(self.c0 >> 4) & 15]
                buf[s:s + m] += v * LEVEL * 1.6 * tab[(self.pn + t) % len(tab)]; self.pn = (self.pn + m) % len(tab)
        self.out.append(buf)

def run(zip_path, secs=90, wav=None):
    z = zipfile.ZipFile(zip_path); mem = bytearray(0x10000)
    for name, base in (('cpu_u1.716', 0x1000), ('cpu_u5b.716', 0x1800), ('cpu_u2b.716', 0x5000), ('cpu_u6b.716', 0x5800)):
        mem[base:base + 0x800] = z.read(name)
    board = Board(); cpu = CPU(mem, on_write=board.write)
    mem[0x1F] = 0x80                      # game in progress
    cpu.call(0x50B7)                      # ball start (bytecode op $55)
    tick = 1 / 120; t = 0.0; k = 0; effect_until = None; steps = 0
    rng = np.random.default_rng(7)
    next_score = 0.5; next_effect = 6.0
    while t < secs:
        # scoring: busy for 20 s, quiet for 8 s, repeat
        if t >= next_score:
            if (t % 28) < 20: mem[0x48] = 0xFF
            next_score = t + rng.uniform(0.6, 1.8)
        # sound effects: an occasional 0.6 s blip that takes the board
        if effect_until is None and t >= next_effect:
            mem[0x6D] = 0x58; mem[0x6E] = 0xEF
            for a, v in ((0xA4, 0x02), (0xA5, 0x8E), (0xA1, 0x00), (0xA0, 0x00), (0xA1, 0x01),
                         (0xA0, 0x12), (0xA1, 0x93), (0xC0, 0x01)):
                board.write(a, v)
            effect_until = t + 0.6; next_effect = t + rng.uniform(5, 11)
        if effect_until is not None and t >= effect_until:
            for a, v in ((0xA1, 0), (0xA0, 0), (0xA1, 1), (0xA0, 1), (0xC0, 0)): board.write(a, v)   # STOP
            mem[0x6D] = mem[0x6E] = 0
            cpu.call(0x50CC)              # STOP -> $50B2 -> $50CC (game in progress)
            effect_until = None
        # 120 Hz timer service ($5D94)
        if mem[0x48]: mem[0x48] -= 1
        k += 1
        if k % 4 == 0 and mem[0x5D]:
            mem[0x5D] -= 1
            if mem[0x5D] == 0:
                cpu.call(0x50ED); steps += 1
        board.render(tick); t += tick
    a = np.concatenate(board.out)
    if wav:
        a2 = a / max(1e-9, np.abs(a).max()) * 0.8
        with wave.open(wav, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((a2 * 32767).astype('<i2').tobytes())
    return a, mem, steps, board

if __name__ == '__main__':
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 90
    a, mem, steps, board = run(sys.argv[1], secs, sys.argv[2])
    print('%s: %d steps, $02F7=%d, harsh T1 channel used: %s' % (sys.argv[2], steps, mem[0x02F7], board.t1_used))
