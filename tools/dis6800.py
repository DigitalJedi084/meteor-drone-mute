"""Minimal recursive-descent Motorola 6800 disassembler for Stern MP-200 ROMs."""
import sys, os

# opcode -> (mnemonic, mode)  modes: inh imm8 imm16 dir ext idx rel
OPS = {}
def op(code, mn, mode): OPS[code] = (mn, mode)

inh = {0x01:'NOP',0x06:'TAP',0x07:'TPA',0x08:'INX',0x09:'DEX',0x0A:'CLV',0x0B:'SEV',0x0C:'CLC',0x0D:'SEC',
       0x0E:'CLI',0x0F:'SEI',0x10:'SBA',0x11:'CBA',0x16:'TAB',0x17:'TBA',0x19:'DAA',0x1B:'ABA',
       0x30:'TSX',0x31:'INS',0x32:'PULA',0x33:'PULB',0x34:'DES',0x35:'TXS',0x36:'PSHA',0x37:'PSHB',
       0x39:'RTS',0x3B:'RTI',0x3E:'WAI',0x3F:'SWI'}
for k,v in inh.items(): op(k,v,'inh')
rel = {0x20:'BRA',0x22:'BHI',0x23:'BLS',0x24:'BCC',0x25:'BCS',0x26:'BNE',0x27:'BEQ',0x28:'BVC',0x29:'BVS',
       0x2A:'BPL',0x2B:'BMI',0x2C:'BGE',0x2D:'BLT',0x2E:'BGT',0x2F:'BLE',0x8D:'BSR'}
for k,v in rel.items(): op(k,v,'rel')
# single-operand group 0x40/0x50 inh (A/B), 0x60 idx, 0x70 ext
uni = {0x0:'NEG',0x3:'COM',0x4:'LSR',0x6:'ROR',0x7:'ASR',0x8:'ASL',0x9:'ROL',0xA:'DEC',0xC:'INC',0xD:'TST',0xE:'JMP',0xF:'CLR'}
for lo,mn in uni.items():
    if mn != 'JMP':
        op(0x40|lo, mn+'A','inh'); op(0x50|lo, mn+'B','inh')
    op(0x60|lo, mn,'idx'); op(0x70|lo, mn,'ext')
# two-operand groups
two = {0x0:'SUB',0x1:'CMP',0x2:'SBC',0x4:'AND',0x5:'BIT',0x6:'LDA',0x7:'STA',0x8:'EOR',0x9:'ADC',0xA:'ORA',0xB:'ADD'}
for lo,mn in two.items():
    for base,reg in ((0x80,'A'),(0xC0,'B')):
        for off,mode in ((0x00,'imm8'),(0x10,'dir'),(0x20,'idx'),(0x30,'ext')):
            if mn=='STA' and mode=='imm8': continue
            op(base|off|lo, mn+reg, mode)
for off,mode in ((0x00,'imm16'),(0x10,'dir'),(0x20,'idx'),(0x30,'ext')):
    op(0x8C|off,'CPX',mode); op(0x8E|off,'LDS',mode); op(0xCE|off,'LDX',mode)
    if mode!='imm16': op(0x8F|off,'STS',mode); op(0xCF|off,'STX',mode)
op(0xAD,'JSR','idx'); op(0xBD,'JSR','ext')
SIZE = {'inh':1,'rel':2,'imm8':2,'dir':2,'idx':2,'imm16':3,'ext':3}

class Mem:
    def __init__(self, romdir):
        self.m = {}
        for name, base in (('cpu_u1.716',0x1000),('cpu_u5b.716',0x1800),('cpu_u2b.716',0x5000),('cpu_u6b.716',0x5800)):
            data = open(os.path.join(romdir,name),'rb').read()
            for i,b in enumerate(data): self.m[base+i]=b
    def __contains__(self,a): return self.norm(a) in self.m
    def norm(self,a):
        a &= 0x7fff  # A15 not decoded
        return a
    def __getitem__(self,a): return self.m[self.norm(a)]
    def w(self,a): return (self[a]<<8)|self[a+1]

def decode(mem, pc):
    o = mem[pc]
    if o not in OPS: return None
    mn, mode = OPS[o]; n = SIZE[mode]
    b = [mem[pc+i] for i in range(n)]
    if mode=='inh': s=''
    elif mode=='imm8': s='#$%02X'%b[1]
    elif mode=='imm16': s='#$%04X'%((b[1]<<8)|b[2])
    elif mode=='dir': s='$%02X'%b[1]
    elif mode=='ext': s='$%04X'%((b[1]<<8)|b[2])
    elif mode=='idx': s='$%02X,X'%b[1]
    elif mode=='rel':
        t=(pc+2+(b[1]-256 if b[1]>127 else b[1]))&0xffff; s='$%04X'%t
    return mn, mode, n, b, s

def trace(mem, entries):
    code = {}; todo = list(entries); labels=set(entries)
    while todo:
        pc = todo.pop()
        while pc in mem and pc not in code:
            d = decode(mem, pc)
            if d is None: break
            mn,mode,n,b,s = d
            code[pc]=d
            if mode=='rel':
                t=int(s[1:],16); labels.add(t); todo.append(t)
                if mn=='BRA': break
            elif mn in ('JMP','JSR') and mode=='ext':
                t=(b[1]<<8)|b[2]; labels.add(t); todo.append(t)
                if mn=='JMP': break
            elif mn=='JMP' or mn in ('RTS','RTI'): break
            pc += n
    return code, labels

if __name__=='__main__':
    mem = Mem(sys.argv[1])
    vec = {name: mem.w(0x5ff8+2*i) for i,name in enumerate(('IRQ','SWI','NMI','RESET'))}
    extra = [int(x,16) for x in sys.argv[3:]]
    code, labels = trace(mem, list(vec.values())+extra)
    with open(sys.argv[2],'w') as f:
        f.write('; vectors: '+' '.join('%s=$%04X'%kv for kv in vec.items())+'\n')
        prev=None
        for a in sorted(mem.m):
            if a in code:
                mn,mode,n,b,s = code[a]
                lab = ('L%04X:'%a) if a in labels else ''
                f.write('%-7s %04X  %-9s %-5s %s\n'%(lab,a,' '.join('%02X'%x for x in b),mn,s))
            elif not any(a-k in code and code[a-k][2]>k for k in (1,2)):
                f.write('        %04X  %02X        .byte\n'%(a,mem.m[a]))
