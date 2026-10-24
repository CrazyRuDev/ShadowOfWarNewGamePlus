import struct
def load(path):
    d=open(path,'rb').read()
    magic,ver,hdr,cnt=struct.unpack_from('<4sIII',d,0)
    base=hdr+cnt*8; out={}
    for k in range(cnt):
        h,off=struct.unpack_from('<II',d,hdr+8*k)
        s=base+off*2; e=s
        while d[e:e+2]!=b'\0\0': e+=2
        out[h]=d[s:e].decode('utf-16-le')
    return out
