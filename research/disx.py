import sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from sowpe import d, va2off
cs = Cs(CS_ARCH_X86, CS_MODE_64)
def dis(va, n, mark=None):
    off = va2off(va)
    for ins in cs.disasm(d[off:off + n], va):
        print(('>> ' if ins.address == mark else '   ') + f"{ins.address:x}: {ins.mnemonic} {ins.op_str}")
if __name__ == '__main__':
    va = int(sys.argv[1], 16)
    dis(va - int(sys.argv[2], 16), int(sys.argv[2], 16) + int(sys.argv[3], 16), va)
