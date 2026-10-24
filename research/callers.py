import re,struct,sowpe,sys
e=sowpe.d
def callers(target):
    out=[]
    for nm,va,vs,ro,rs in sowpe.secs:
        if nm not in ('.arch','.text'): continue
        seg=e[ro:ro+rs]
        for m in re.finditer(rb'[\xe8\xe9]',seg):
            i=m.start()
            if i+5>len(seg): break
            d=struct.unpack_from('<i',seg,i+1)[0]
            if sowpe.BASE+va+i+5+d==target: out.append(sowpe.BASE+va+i)
    return out
if __name__=='__main__':
    for t in sys.argv[1:]: c=callers(int(t,16)); print(t,len(c),[hex(x) for x in c[:50]])
