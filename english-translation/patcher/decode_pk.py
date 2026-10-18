"""Read-only aaa.pk decoder reconstructed from the launcher; validates size/hash."""
from pathlib import Path
import collections,hashlib,json,struct,sys,zlib
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parent

class Reader:
    def __init__(self,b): self.b=b; self.p=0
    def read(self,n):
        if n<0 or self.p+n>len(self.b):raise ValueError('Out of bounds')
        r=self.b[self.p:self.p+n]; self.p+=n; return r
    def u32(self):return struct.unpack('<I',self.read(4))[0]
    def text(self):return self.read(self.u32()*2).decode('utf-16le')
    def node(self,depth=0):
        if depth>64:raise ValueError('Depth limit')
        e=ET.Element(self.text());e.text=self.text()
        count=self.u32()
        if count>1000:raise ValueError('Attribute limit')
        for _ in range(count):
            k=self.text();v=self.text();e.set(k,v)
        count=self.u32()
        if count>100000:raise ValueError('Node count limit')
        for _ in range(count):e.append(self.node(depth+1))
        return e

def decode(src):
    b=src.read_bytes();r=Reader(b);total=r.u32()
    if total!=len(b)-4:raise ValueError('Container length mismatch')
    magic,flags=r.read(2);checksum=r.u32()
    if magic!=83 or flags!=1:raise ValueError('Only compressed, unencrypted KRData supported')
    length=r.u32()
    if length>32*1024*1024:raise ValueError('Output size limit')
    d=zlib.decompressobj();payload=d.decompress(r.read(len(b)-r.p),length+1)
    if not d.eof or d.unused_data or len(payload)!=length:raise ValueError('Zlib/length mismatch')
    if zlib.adler32(payload,0)!=checksum:raise ValueError('Adler32 mismatch')
    r=Reader(payload);root=r.node()
    if r.p!=len(payload):raise ValueError('Trailing binary XML data')
    ET.indent(root); ET.ElementTree(root).write(BASE/'aaa-index.xml',encoding='utf-8',xml_declaration=True)
    rows=[]
    def walk(e,path):
        name=e.get('name','');path=path+[name] if name else path
        if e.tag=='RhoFolder':
            filename=e.get('fileName','')
            rows.append(dict(logical_path='/'.join(path),**e.attrib,exists=(src.parent/filename).is_file()))
        for c in e:walk(c,path)
    walk(root,[])
    report=dict(source=str(src),sha256=hashlib.sha256(b).hexdigest(),container_length=total,
        decoded_length=length,checksum=hex(checksum),checksum_verified=True,binary_xml_consumed=r.p,
        root=root.tag,tags=dict(collections.Counter(e.tag for e in root.iter())),
        rho_mappings=rows,missing_archives=[x for x in rows if not x['exists']])
    (BASE/'aaa-index-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['rho_mappings','missing_archives']},ensure_ascii=True))
    print('mappings',len(rows),'missing',len(report['missing_archives']))
    return report

if __name__=='__main__':decode(Path(sys.argv[1]))
