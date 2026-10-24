import struct,sys,array
sys.path.insert(0,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools'); import gdb
D=gdb.D
def cats():
    out=[]
    for al in range(4):
        a=array.array('I'); seg=D[gdb.PE+al:]; a.frombytes(seg[:len(seg)//4*4])
        for k in range(len(a)-5):
            p=a[k+2]
            if 0<p<gdb.PSIZE and D[gdb.POOL+p-1]==0:
                s=gdb.pstr(p)
                if s and s.endswith('gdb.category06') and a[k+3]==0:
                    out.append(dict(off=gdb.PE+al+4*k,name=gdb.pstr(a[k]),type=gdb.pstr(a[k+1]),path=s,count=a[k+4],hash=a[k+5]))
    out.sort(key=lambda c:c['off']); return out
