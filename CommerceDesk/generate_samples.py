"""Generate fictional product illustrations and demo CSV files. Used once; no runtime dependency."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import csv, math, random
P=Path(__file__).resolve().parent
S=P/'samples'/'images'; S.mkdir(parents=True,exist_ok=True)
NAMES={
 'GH-101':('Glass door hinge','hinge'), 'GH-102':('Square pull handle','handle'), 'GS-201':('Clear door bottom seal','seal'),
 'GC-301':('Glass mounting clamp','clamp'), 'GT-401':('Black aluminum channel','channel'), 'GA-501':('Glazing gasket','gasket'),
 'GT-402':('Glass suction lifter','suction'), 'GH-103':('Round glass door knob','knob'), 'GS-202':('Edge protection strip','edge'),
 'GT-403':('Measuring square','square'), 'GH-205':('Satin glass hinge kit','hinge'), 'GS-305':('Frameless panel seal','seal'),
 'GT-505':('Aluminum installation channel','channel')}
try: BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'; REG='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
except: BOLD=REG=None
F=lambda p,size:ImageFont.truetype(p,size) if p and Path(p).exists() else ImageFont.load_default()

for sku,(name,kind) in NAMES.items():
  scale=2; W=480; w=W*scale
  im=Image.new('RGB',(w,w),'#f6f8fb');d=ImageDraw.Draw(im)
  def rect(box,fill,outline=None,width=2,r=12):d.rounded_rectangle(tuple(int(v*scale) for v in box),radius=r*scale,fill=fill,outline=outline,width=width*scale)
  def line(pts,fill='#778da8',width=9):d.line([(int(x*scale),int(y*scale)) for x,y in pts],fill=fill,width=width*scale,joint='curve')
  def ellipse(box,fill,outline=None,width=2):d.ellipse(tuple(int(v*scale) for v in box),fill=fill,outline=outline,width=width*scale)
  # light technical grid gives authentic catalog product sheet texture
  for x in range(30,480,40):line([(x,20),(x,460)],'#edf1f6',1)
  for y in range(30,480,40):line([(20,y),(460,y)],'#edf1f6',1)
  rect((28,24,452,456),'#ffffff','#e4eaf1',2,20)
  line([(50,86),(430,86)],'#edf1f6',2)
  if kind=='hinge':
    rect((110,160,222,305),'#b5c4d0','#6c8192',4,13);rect((258,160,370,305),'#b8c8d5','#6c8192',4,13)
    for x in (150,328):
      ellipse((x-10,201,x+10,221),'#6c8296');ellipse((x-10,255,x+10,275),'#6c8296')
    rect((210,150,270,317),'#7f96aa','#5d778e',3,10)
    for y in (180,217,254,291):line([(216,y),(263,y)],'#cad6df',4)
  elif kind=='handle':
    line([(170,312),(170,190),(315,190),(315,312)],'#607b93',22)
    line([(175,313),(175,195),(314,195),(314,313)],'#c8d5df',12)
    ellipse((149,298,191,340),'#7d93a6');ellipse((295,298,337,340),'#7d93a6')
  elif kind=='seal':
    rect((85,253,395,291),'#c6e2e9','#8daebb',3,4);rect((85,254,395,266),'#e5f6f9',None,0,4)
    line([(103,297),(367,297)],'#8ebccc',7)
    for x in range(110,375,18):line([(x,299),(x+8,318)],'#b3d6de',3)
  elif kind=='clamp':
    rect((146,158,330,315),'#b1c2d1','#6e8799',4,19)
    rect((184,136,292,224),'#fafcfe','#829bad',3,5)
    line([(182,225),(290,225)],'#607d94',9)
    for x in (185,289):ellipse((x-9,257,x+9,275),'#6c8499')
  elif kind=='channel':
    # side section of a long U-channel with visible inner cutout
    d.polygon([(120*scale,198*scale),(157*scale,192*scale),(157*scale,280*scale),(322*scale,278*scale),(322*scale,192*scale),(358*scale,198*scale),(358*scale,320*scale),(120*scale,320*scale)],fill='#46586c' if 'GT-401'==sku else '#9dabb9')
    line([(157,194),(157,282),(322,282),(322,194)],'#c5d0da',6)
  elif kind=='gasket' or kind=='edge':
    for dx in (0,25,50):
      line([(90+dx,245),(355+dx,245)],'#657c91',12)
      line([(90+dx,267),(355+dx,267)],'#b0c3d0',8)
    line([(95,225),(359,225)],'#8fa8ba',5)
  elif kind=='suction':
    ellipse((123,177,234,288),'#303f4e','#7891a9',5);ellipse((250,177,361,288),'#303f4e','#7891a9',5)
    ellipse((145,201,210,267),'#627d94');ellipse((274,201,339,267),'#627d94')
    line([(181,209),(181,158),(304,158),(304,209)],'#354e62',13)
    rect((216,150,270,170),'#a7b8c6','#627b8f',2,8)
  elif kind=='knob':
    ellipse((148,159,329,335),'#a7bacb','#738b9f',5);ellipse((174,181,302,311),'#e1eaf1','#8a9eae',4)
    ellipse((225,229,258,263),'#6a849a')
  elif kind=='square':
    line([(137,150),(137,335),(347,335)],'#678099',21)
    for x in range(160,345,28):line([(x,323),(x,339)],'#e7eef3',3)
    for y in range(160,330,28):line([(126,y),(145,y)],'#e7eef3',3)
  # individual SKU and catalog label (part of source art, not filename-dependent)
  d.text((56*scale,45*scale),'COMMERCE  /  SAMPLE CATALOG',font=F(BOLD,11*scale),fill='#5176a1')
  d.text((55*scale,382*scale),name.upper()[:35],font=F(BOLD,16*scale),fill='#273a50')
  d.text((55*scale,408*scale),sku,font=F(REG,13*scale),fill='#78889a')
  im.resize((W,W),Image.Resampling.LANCZOS).save(S/(sku+'.png'),optimize=True)

fields=['action','sku','name','category','description','price','stock','status','featured','image_filename']
files={
'products-create.csv':[
 ['create','GH-205','Satin Glass Hinge Kit','Glass Door Hardware','Two-piece satin-finish hinge kit for frameless glass doors.','37.95','11','published','yes','GH-205.png'],
 ['create','GS-305','Frameless Panel Seal','Seals & Gaskets','Transparent silicone seal for a glass shower panel.','14.25','30','published','no','GS-305.png'],
 ['create','GT-505','Aluminum Installation Channel','Glazing Supplies','Anodized aluminum channel for fixed panel mounting.','26.50','18','published','no','GT-505.png']],
'products-update.csv':[
 ['update','GH-101','','','','28.50','','','',''],
 ['update','GC-301','','','','20.75','','','','']],
'products-errors.csv':[
 ['create','GH-101','Duplicate Existing Hinge','Glass Door Hardware','Should be blocked due to duplicate SKU.','19.50','10','published','no','GH-101.png'],
 ['create','GH-999','Broken Price Product','Glass Door Hardware','Should be blocked for invalid price.','-3.00','2','published','no','GH-999.png'],
 ['create','GS-999','Missing Category Product','','Should be blocked for missing category.','9.00','5','published','no','GS-999.png']]
}
for filename,rows in files.items():
  with (P/'samples'/filename).open('w',newline='',encoding='utf-8') as f:
    writer=csv.writer(f); writer.writerow(fields); writer.writerows(rows)
print('Created',len(NAMES),'SKU-named example images and',len(files),'CSV files')
