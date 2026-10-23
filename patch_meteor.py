"""Patch Stern Meteor (PinMAME set 'meteorb') to silence the rising background drone.

Usage:  python patch_meteor.py <path-to-meteorb.zip> <output-dir>

Writes two ROM sets, each zipped as meteorb.zip:
  <out>/clean/meteorb.zip  - recommended: drone routine puts the 6840 timers in reset instead of
                             starting them, so it mirrors the game's own "stop sound" opcode.
                             The game-start sound is kept.
  <out>/forum/meteorb.zip  - the forum patch: drone routine becomes RTS, and the game-start
                             sound is removed (U1 byte swap).
Both keep the boot ROM checksum (sum of all 8 KB == 0 mod 256), or the MPU halts at $5F84.
"""
import os, sys, zipfile

FILES = ['cpu_u1.716', 'cpu_u2b.716', 'cpu_u5b.716', 'cpu_u6b.716']

# (file, offset, expected original byte, new byte, CPU address / reason)
CLEAN = [
    ('cpu_u2b.716', 0xDF, 0x92, 0x01, '$50DF  CR1 = $01: hold all 6840 timers in reset (was $92: T1 output on)'),
    ('cpu_u2b.716', 0xE0, 0x93, 0x01, '$50E0  CR2 = $01: T2 output off (was $93: T2 output on)'),
    ('cpu_u2b.716', 0xB9, 0x10, 0x33, '$50B9  drone T1 seed $3010 -> $3033 (inaudible now; balances checksum)'),
]
FORUM = [
    ('cpu_u2b.716', 0xCC, 0xFE, 0x39, '$50CC  RTS at top of drone (re)load routine'),
    ('cpu_u2b.716', 0xCD, 0x02, 0xC7, '$50CD  filler that balances checksum'),
    ('cpu_u1.716',  0xA6, 0x57, 0x2F, '$10A6  bytecode RETURN before "play sound $58EF" (game-start sound)'),
    ('cpu_u1.716',  0xA9, 0x2F, 0x57, '$10A9  (dead byte after the return; keeps checksum)'),
]

def build(src, patches, outzip):
    roms = {n: bytearray(src.read(n)) for n in FILES}
    for f, off, old, new, why in patches:
        if roms[f][off] != old:
            sys.exit('%s+%02X is %02X, expected %02X - not the meteorb set?' % (f, off, roms[f][off], old))
        roms[f][off] = new
        print('  %-12s +%03X  %02X -> %02X   %s' % (f, off, old, new, why))
    total = sum(sum(r) for r in roms.values()) & 0xFF
    if total:
        sys.exit('checksum would be %02X, game would halt at boot' % total)
    os.makedirs(os.path.dirname(outzip), exist_ok=True)
    with zipfile.ZipFile(outzip, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in FILES:
            z.writestr(n, bytes(roms[n]))
    print('  checksum OK ->', outzip)

if __name__ == '__main__':
    src = zipfile.ZipFile(sys.argv[1])
    print('clean patch:'); build(src, CLEAN, os.path.join(sys.argv[2], 'clean', 'meteorb.zip'))
    print('forum patch:'); build(src, FORUM, os.path.join(sys.argv[2], 'forum', 'meteorb.zip'))
