import struct
class MD:
    def __init__(s,path):
        d=s.d=open(path,'rb').read()
        sig,ver,n,dirrva=struct.unpack_from('<4sIII',d,0)
        s.streams={}
        for i in range(n):
            t,size,rva=struct.unpack_from('<III',d,dirrva+12*i); s.streams[t]=(size,rva)
        # memory ranges
        s.mem=[]
        if 9 in s.streams:
            size,rva=s.streams[9]; cnt,base=struct.unpack_from('<QQ',d,rva); p=rva+16; off=base
            for i in range(cnt):
                st,sz=struct.unpack_from('<QQ',d,p); s.mem.append((st,sz,off)); off+=sz; p+=16
        if 5 in s.streams:
            size,rva=s.streams[5]; cnt=struct.unpack_from('<I',d,rva)[0]; p=rva+4
            for i in range(cnt):
                st,sz,r=struct.unpack_from('<QII',d,p); s.mem.append((st,sz,r)); p+=16
        # modules
        s.mods=[]
        size,rva=s.streams[4]; cnt=struct.unpack_from('<I',d,rva)[0]; p=rva+4
        for i in range(cnt):
            base,sz=struct.unpack_from('<QI',d,p); namerva=struct.unpack_from('<I',d,p+20)[0]
            L=struct.unpack_from('<I',d,namerva)[0]; name=d[namerva+4:namerva+4+L].decode('utf-16-le')
            s.mods.append((base,sz,name)); p+=108
    def read(s,addr,n):
        for st,sz,off in s.mem:
            if st<=addr and addr+n<=st+sz: return s.d[off+addr-st:off+addr-st+n]
        return None
    def exception(s):
        size,rva=s.streams[6]; tid=struct.unpack_from('<I',s.d,rva)[0]
        code,flags,rec,addr=struct.unpack_from('<IIQQ',s.d,rva+8)
        ctxsize,ctxrva=struct.unpack_from('<II',s.d,rva+8+152)
        return tid,code,addr,s.d[ctxrva:ctxrva+ctxsize]
