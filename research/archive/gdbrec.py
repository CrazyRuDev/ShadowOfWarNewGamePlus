import struct,sys,pickle,os
sys.path.insert(0,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools')
import gdb,gdbcats
D=gdb.D
def isname(v): return 0<v<gdb.PSIZE and D[gdb.POOL+v-1]==0 and 0x20<D[gdb.POOL+v]<0x7f
CACHE='/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/gdbrec.pkl'
def load():
    if os.path.exists(CACHE): return pickle.load(open(CACHE,'rb'))
    C=gdbcats.cats()
    for n,c in enumerate(C):
        start=c['off']+24; end=C[n+1]['off'] if n+1<len(C) else len(D)
        recs=[]
        for p in range(start,end-12,4):
            v,t,f=struct.unpack_from('<III',D,p)
            if (f>>24)==8 and (f&0xff0000)==0 and isname(v): recs.append((p,gdb.pstr(v)))
        c['recs']=recs
    pickle.dump(C,open(CACHE,'wb')); return C
