import sys,re,struct
sys.path.insert(0,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools')
import h397,gdb,strdb
names=set(m.group().decode() for m in re.finditer(rb'[\x20-\x7e]{1,}',gdb.D[gdb.POOL:gdb.PE]))
H={h397.h(n):n for n in names}
ru=strdb.load('/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/ext/hotchunk__database_string_ruru_string.strdb')
def tok(buf,p,end,raw=False):
    res=[]
    while p<end:
        t=buf[p]
        if t in (0,4,0x0a,7,8):
            v=struct.unpack_from('<I',buf,p+1)[0]
            if t==0: s=H.get(v,'#%08x'%v)
            elif t==0x0a: s='f%.4g'%struct.unpack_from('<f',buf,p+1)[0]
            elif t==8: s='T"%s"'%ru.get(v,'?%08x'%v)
            elif t==7: s='u%08x'%v
            else: s='i%d'%struct.unpack_from('<i',buf,p+1)[0]
            res.append((p,s)); p+=5
        elif t in (5,9): res.append((p,'Q%s'%buf[p+1:p+9].hex())); p+=9
        elif t in (0x0c,2,0x0f): res.append((p,'b%x:%d'%(t,buf[p+1]))); p+=2
        else: res.append((p,'?%02x'%t)); p+=1
    return res
