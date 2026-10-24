import struct,bisect,sowpe
e=sowpe.d
pe=struct.unpack_from('<I',e,0x3c)[0]
opt=pe+24
# data directory 3 = exception
ddoff=opt+112
exc_rva,exc_size=struct.unpack_from('<II',e,ddoff+3*8)
off=sowpe.va2off(sowpe.BASE+exc_rva)
F=[]
for i in range(exc_size//12):
    b,en,u=struct.unpack_from('<III',e,off+12*i); F.append((b,en))
F.sort(); starts=[b for b,_ in F]
def func(va):
    r=va-sowpe.BASE; i=bisect.bisect_right(starts,r)-1
    b,en=F[i]
    return (sowpe.BASE+b,sowpe.BASE+en) if b<=r<en else None
