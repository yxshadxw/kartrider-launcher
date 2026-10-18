"""Build native Korean bitmap font resources from fonts already shipped in gui_font.rho."""
import struct
from PIL import Image

def font_tree():
    import xml.etree.ElementTree as ET
    root=ET.Element('Fonts')
    def bitmap(name,file): ET.SubElement(root,'BitmapFont',name=name,headerFile=file,dataFile=file)
    def bold(name,base): ET.SubElement(root,'BoldFilterFont',name=name,baseFontName=base)
    def outline(name,base): ET.SubElement(root,'OutlineFilterFont',name=name,baseFontName=base,outlineThickness='1')
    bitmap('default','nanumgothic_9')
    bold('bold','default'); outline('outline','default'); bold('bigbold','default'); bold('gulim14','default')
    bitmap('medium16','meiryo_8'); outline('default16','medium16')
    for size,member in ((14,'meiryo_7'),(16,'meiryo_8'),(20,'meiryo_9'),(24,'meiryo_10b')):
        base='medium16' if size==16 else f'kr_base{size}'
        if size!=16: bitmap(base,member)
        bold(f'bold{size}',base); outline(f'outline{size}',f'bold{size}')
    outline('scalex2','bold24')
    return root

def scale_bitmap(header,pixels,baseline):
    ranges,height,old_baseline,bpp=struct.unpack_from('<HIII',header)
    if bpp!=8: raise ValueError('Expected shipped alpha8 bitmap font')
    ratio=baseline/old_baseline; new_height=round(height*ratio)
    output=bytearray(); result=bytearray(struct.pack('<HIII',ranges,new_height,baseline,8)); pos=14
    for _ in range(ranges):
        first,last=struct.unpack_from('<HH',header,pos); pos+=4
        result.extend(struct.pack('<HH',first,last))
        for _cp in range(first,last+1):
            width,offset=struct.unpack_from('<BI',header,pos); pos+=5
            new_width=round(width*ratio)
            result.extend(struct.pack('<BI',new_width,len(output)))
            if width and new_width:
                glyph=Image.frombytes('L',(width,height),pixels[offset:offset+width*height])
                output.extend(glyph.resize((new_width,new_height),Image.Resampling.BILINEAR).tobytes())
    if pos!=len(header)-4 or struct.unpack_from('<I',header,pos)[0]!=len(pixels):
        raise ValueError('Invalid bitmap font header or payload length')
    result.extend(struct.pack('<I',len(output)))
    return bytes(result),bytes(output)

def native_font_payloads(rho):
    members={e['path']:e for e in rho.entries}
    header=rho.content(members['nanumgothic_10.bmh'])
    pixels=rho.content(members['nanumgothic_10.bmx'])
    replacements={}
    for baseline,member in ((14,'meiryo_7'),(16,'meiryo_8'),(20,'meiryo_9'),(24,'meiryo_10b')):
        if member+'.bmh' not in members or member+'.bmx' not in members:
            raise ValueError(f'Missing shipped bitmap font resources: {member}')
        replacements[member+'.bmh'],replacements[member+'.bmx']=scale_bitmap(header,pixels,baseline)
    return replacements
