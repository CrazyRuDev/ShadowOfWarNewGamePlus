import struct,sowpe,sys
e=sowpe.d
def xrefs(target):
    out=[]
    for nm,va,vs,ro,rs in sowpe.secs:
        if nm not in ('.arch','.text'): continue
        seg=e[ro:ro+rs]
        import re
        for m in re.finditer(rb'[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]',seg):
            i=m.start(); disp=struct.unpack_from('<i',seg,i+3)[0]
            ins=sowpe.BASE+va+i
            if ins+7+disp==target: out.append(ins)
    return out
if __name__=='__main__':
    for t in sys.argv[1:]: print(t,[hex(x) for x in xrefs(int(t,16))])
