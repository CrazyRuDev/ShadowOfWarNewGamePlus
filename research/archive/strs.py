import re,sys
d=open(sys.argv[1],'rb').read(); n=int(sys.argv[2]) if len(sys.argv)>2 else 6
for m in re.finditer(rb'[\x20-\x7e]{%d,}'%n,d): print(hex(m.start()),m.group().decode())
for m in re.finditer(rb'(?:[\x20-\x7e]\x00){%d,}'%n,d): print(hex(m.start()),'W',m.group().decode('utf-16-le'))
