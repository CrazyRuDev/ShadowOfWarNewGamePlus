import struct,sys
sys.path.insert(0,'/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/tools')
import savetok
H=savetok.H; ru=savetok.ru
SZ={0:4,4:4,0x0a:4,7:4,8:4,5:8,9:8,0x0c:1,2:1,0x0e:12,0x03:2,0x06:4,0x01:1,0x0b:8,0x0d:8}
def tok(B,p,end):
    out=[]
    while p<end:
        t=B[p]
        if t==0x0f:
            L=B[p+1]; out.append((p,'S"%s"'%B[p+2:p+2+L].decode('latin1'))); p+=2+L; continue
        if t==0x10:
            L=struct.unpack_from('<I',B,p+1)[0]; out.append((p,'BLOB%d'%L)); p+=5; continue
        n=SZ.get(t)
        if n is None: out.append((p,'?%02x'%t)); p+=1; continue
        raw=B[p+1:p+1+n]
        if t==0: v=struct.unpack('<I',raw)[0]; s=H.get(v,'#%08x'%v)
        elif t==4: s='i%d'%struct.unpack('<i',raw)[0]
        elif t==0x0a: s='f%.4g'%struct.unpack('<f',raw)[0]
        elif t==0x0c: s='bc%d'%raw[0]
        elif t==2: s='b%d'%raw[0]
        elif t==3: s='h%d'%struct.unpack('<h',raw)[0]
        elif t==8: s='T%d'%struct.unpack('<I',raw)[0]
        else: s='%02x:%s'%(t,raw.hex())
        out.append((p,s)); p+=1+n
    return out
