"""Render preview WAVs of background-sound ideas through a model of PinMAME's SB-300 emulation.

Model (from PinMAME src/wpc/stsnd.c):
  Q1  6840 timer 1: fixed odd pulse wave, volume 70, freq = 1 MHz / (2*(latch+1))
  Q2  6840 timer 2: square wave, volume from the Q3 envelope
  NOISE           : filtered noise ($C0 hi nibble picks filter), volume from the Q3 envelope
  Q3  6840 timer 3: not heard; each full period steps a 16-step volume envelope
  $C0 write       : restarts envelope. bit0 = up, bit1 = alternate, bit2 = continuous, bit3 = noise on

Usage: python sb300_preview.py <out-dir>
"""
import os, sys, wave
import numpy as np

SR = 48000
CLK = 1_000_000
VOLTAB = [0, 0, 0, 0, 0, 10, 20, 20, 30, 30, 40, 40, 60, 60, 80, 90, 100, 100]
Q1WAVE = np.array([0x4000, 0x2000, 0x7fff, 0x1000, 0, 0, 0, 0,
                   -0x4000, -0x2000, -0x7fff, -0x1000, 0, 0, 0, 0]) / 32767.0
LEVEL = 0.30  # PinMAME mixing level per channel

def lat(freq):
    return int(round(CLK / (2 * freq) - 1))

def noise_table():
    rng = np.random.default_rng(1979)
    white = rng.uniform(-0.85, 0.85, 32000)
    brown = np.cumsum(rng.uniform(-0.25, 0.25, 32000)); brown = brown - np.convolve(brown, np.ones(801) / 801, 'same')
    base = np.clip(white + 0.15 * brown / (np.abs(brown).max() + 1e-9), -1, 1)
    tabs = [base]
    for j in range(1, 16):
        k = np.ones(4 * j + 1)
        t = np.convolve(np.concatenate([base[-2 * j:], base, base[:2 * j]]), k, 'valid')
        tabs.append(np.clip(t / ((j + 1) // 2), -1, 1))
    return tabs
NOISE = noise_table()

class SB300:
    """Holds register state; render(seconds) appends audio."""
    def __init__(self):
        self.q1 = None; self.q2 = None; self.q3 = None   # latches, None = output disabled
        self.c0 = 0; self.volnr = 0; self.dir = 0; self.q3acc = 0.0
        self.p1 = self.p2 = self.pn = 0.0; self.out = []

    def write_c0(self, v):
        self.c0 = v; self.dir = v & 1; self.volnr = 1; self.q3acc = 0.0

    def vol(self):
        if self.volnr == 0: return 0
        return VOLTAB[self.volnr] if self.dir else VOLTAB[17 - self.volnr]

    def nextvol(self):
        if 0 < self.volnr <= 16: self.volnr += 1
        if self.volnr > 16:
            if not (self.c0 & 4):
                if not self.dir: self.volnr = 0
            else:
                self.volnr = 1
                if self.c0 & 2: self.dir ^= 1

    def render(self, secs):
        n = int(secs * SR); buf = np.zeros(n)
        block = 48  # 1 ms blocks for envelope resolution
        for s in range(0, n, block):
            m = min(block, n - s); t = np.arange(m)
            if self.q3 is not None:
                self.q3acc += m / SR
                step = 2 * (self.q3 + 1) / CLK
                while self.q3acc >= step:
                    self.q3acc -= step; self.nextvol()
            v = self.vol() / 100.0
            if self.q1 is not None:
                f = CLK / (2 * (self.q1 + 1)); ph = self.p1 + t * f / SR
                buf[s:s + m] += 0.70 * LEVEL * Q1WAVE[((ph % 1) * 16).astype(int)]
                self.p1 = (self.p1 + m * f / SR) % 1
            if self.q2 is not None and v:
                f = CLK / (2 * (self.q2 + 1)); ph = self.p2 + t * f / SR
                buf[s:s + m] += v * LEVEL * np.where(ph % 1 < 0.5, 1.0, -1.0)
                self.p2 = (self.p2 + m * f / SR) % 1
            if self.c0 & 8 and v:
                tab = NOISE[((self.c0 >> 4) & 15)]
                idx = (int(self.pn) + t) % len(tab)
                buf[s:s + m] += v * LEVEL * 1.6 * tab[idx]
                self.pn = (self.pn + m) % len(tab)
        self.out.append(buf)

    def save(self, path):
        a = np.concatenate(self.out)
        a = a / max(1e-9, np.abs(a).max()) * 0.8
        with wave.open(path, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((a * 32767).astype('<i2').tobytes())

# ---- concepts. "game" = 0..1 progress through a game, compressed into the clip ----

def original(clip=45):
    """Stock Meteor: T1/T2 latches drop $100 per step; real game spaces steps 1-4 s apart."""
    sb = SB300(); sb.write_c0(0)
    t1, t2 = 0x3010, 0x3000
    while True:
        sb.q1, sb.q2 = t1, t2
        sb.render(0.45)
        if t1 >> 8 != 1: t1 -= 0x100
        t2 -= 0x100
        if t2 >> 8 == 0: break
    return sb

def solar_wind(clip=45):
    """Dark filtered noise swelling and fading like surf; swells get quicker as the game goes on."""
    sb = SB300(); sb.write_c0(0xFF)   # darkest filter, noise on, continuous, alternate, start up
    t = 0.0
    while t < clip:
        g = t / clip
        sb.q3 = int(0xFFFF - g * (0xFFFF - 0x7000))   # ~2.1 s -> ~0.9 s per half-swell
        sb.render(0.5); t += 0.5
    return sb

def breathing_bass(clip=45):
    """Soft square bass that swells in and out, one note per breath: Am - F - G - E. Breaths quicken."""
    notes = [110.0, 87.31, 98.0, 82.41]
    sb = SB300(); t = 0.0; i = 0
    while t < clip:
        g = t / clip
        period = 4.0 - 2.0 * g                     # one breath = 4 s early, 2 s late
        sb.q2 = lat(notes[i % 4]); sb.q3 = int(period * CLK / 64 - 1)
        sb.write_c0(0x07)                          # continuous, alternate, start rising
        sb.render(period); t += period; i += 1
    return sb

def heartbeat(clip=45):
    """Low 'lub-dub' thumps with quick decay; the pulse rises from ~50 to ~110 bpm."""
    sb = SB300(); sb.q3 = 5000; t = 0.0      # ~0.16 s decay
    while t < clip:
        g = t / clip
        beat = 60.0 / (50 + 60 * g)
        sb.q2 = lat(55.0); sb.write_c0(0x00); sb.render(0.22)
        sb.q2 = lat(49.0); sb.write_c0(0x00); sb.render(beat - 0.22)
        t += beat
    return sb

def invader_march(clip=45):
    """Four descending plucked bass notes looping; tempo creeps up the longer you play."""
    notes = [98.0, 87.31, 82.41, 73.42]
    sb = SB300(); sb.q3 = 9000; t = 0.0; i = 0    # ~0.29 s decay
    while t < clip:
        g = t / clip
        gap = 0.75 - 0.45 * g
        sb.q2 = lat(notes[i % 4]); sb.write_c0(0x00); sb.render(gap)
        t += gap; i += 1
    return sb

if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    for i, fn in enumerate((original, solar_wind, breathing_bass, heartbeat, invader_march)):
        p = os.path.join(out, '%d_%s.wav' % (i, fn.__name__))
        fn().save(p); print(p)
