"""Decode Meteor sound scripts (interpreter at $5E7B in U2/U6)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dis6800 import Mem

REG = {0xA0:'CR1/3', 0xA1:'CR2', 0xA2:'T1', 0xA4:'T2', 0xA6:'T3', 0xC0:'SNDCTL'}

def decode(mem, pc, maxn=80):
    seen = set()
    for _ in range(maxn):
        if pc in seen: break
        seen.add(pc)
        c = mem[pc]
        if c & 0x80:
            v = mem.w(pc+1); r = REG.get(c, '$%02X' % c)
            extra = ''
            if c in (0xA2, 0xA4, 0xA6): extra = '  (~%.1f Hz)' % (894886/(2*(v+1)))
            print('  %04X  %-10s %s = $%04X%s' % (pc, 'WRITE', r, v, extra)); pc += 3
        elif c == 0: print('  %04X  WAIT       %d ticks' % (pc, mem[pc+1])); pc += 2
        elif c == 1: print('  %04X  END' % pc); break
        elif c == 2: print('  %04X  LOOPCNT    %d' % (pc, mem[pc+1])); pc += 2
        elif c == 3: print('  %04X  LOOP       -> $%04X' % (pc, mem.w(pc+1))); pc += 3
        elif c == 4: print('  %04X  JUMP       -> $%04X' % (pc, mem.w(pc+1))); pc = mem.w(pc+1)
        elif c == 5: print('  %04X  SNDCTL     $%02X' % (pc, mem[pc+1])); pc += 2
        elif c == 6: print('  %04X  SWEEP T1+T2 by %+d' % (pc, (mem.w(pc+1) ^ 0x8000) - 0x8000)); pc += 3
        elif c == 7: print('  %04X  SWEEP T1 %+d, T2 %+d' % (pc, (mem.w(pc+1) ^ 0x8000) - 0x8000, (mem.w(pc+3) ^ 0x8000) - 0x8000)); pc += 5
        elif c == 8: print('  %04X  STOP  (-> resume background drone if game in play)' % pc); break
        else: print('  %04X  CTRL       $%02X' % (pc, c)); pc += 1

if __name__ == '__main__':
    mem = Mem(sys.argv[1])
    for a in sys.argv[2:]:
        print('script $%s:' % a.upper()); decode(mem, int(a, 16))
