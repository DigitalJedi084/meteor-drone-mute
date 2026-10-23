"""Assemble background-sound variants into patched meteorb ROM sets.

Usage: python build_variants.py <original meteorb.zip> <variants-dir>
For each <name>.asm in variants-dir writes <variants-dir>/<name>/meteorb.zip.
Only bytes inside the drone block $50B7-$5152 of U2 change; one unused byte there balances the
boot checksum (all 8 KB must sum to 0 mod 256 or the MPU halts at $5F84).
"""
import glob, os, sys, zipfile
sys.path.insert(0, os.path.dirname(__file__))
from asm6800 import assemble

FILES = ['cpu_u1.716', 'cpu_u2b.716', 'cpu_u5b.716', 'cpu_u6b.716']
U2 = 0x5000
LO, HI = 0x50B7, 0x5152
ORIG_U2_SHA1 = '754bb6a7c3c6024b642dba4bc148ed110ab14295'

def build(src_zip, asm_path, out_zip):
    import hashlib
    src = zipfile.ZipFile(src_zip)
    roms = {n: bytearray(src.read(n)) for n in FILES}
    if hashlib.sha1(roms['cpu_u2b.716']).hexdigest() != ORIG_U2_SHA1:
        sys.exit('source cpu_u2b.716 is not the original meteorb U2')
    code, syms = assemble(open(asm_path).read())
    for a in code:
        if not LO <= a <= HI: sys.exit('%s: byte at $%04X is outside $%04X-$%04X' % (asm_path, a, LO, HI))
    assert syms['start'] == 0x50B7 and syms['restore'] == 0x50CC and syms['step'] == 0x50ED and code[0x50EC] == 0x19
    u2 = roms['cpu_u2b.716']
    for a, b in code.items(): u2[a - U2] = b
    free = [a for a in range(HI, LO - 1, -1) if a not in code]
    fix = free[0]
    u2[fix - U2] = 0
    total = sum(sum(r) for r in roms.values()) & 0xFF
    u2[fix - U2] = (-total) & 0xFF
    assert sum(sum(r) for r in roms.values()) & 0xFF == 0
    os.makedirs(os.path.dirname(out_zip), exist_ok=True)
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in FILES: z.writestr(n, bytes(roms[n]))
    print('%-16s %3d code bytes, end $%04X, checksum byte at $%04X = $%02X -> %s'
          % (os.path.basename(asm_path)[:-4], len(code), max(code), fix, u2[fix - U2], out_zip))

if __name__ == '__main__':
    for asm in sorted(glob.glob(os.path.join(sys.argv[2], '*.asm'))):
        name = os.path.basename(asm)[:-4]
        build(sys.argv[1], asm, os.path.join(sys.argv[2], name, 'meteorb.zip'))
