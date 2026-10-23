"""Original illustrated fixtures; never merchant footage or experimental evidence."""
import json, uuid
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from media import DATA,FFMPEG,run,analyze

def create_demo(progress=lambda _:None):
    cache=DATA/'demo-project.json'
    if cache.exists(): return json.loads(cache.read_text(encoding='utf8'))
    fontpath='C:/Windows/Fonts/msyh.ttc'
    def font(n): return ImageFont.truetype(fontpath,n)
    shots=[]
    for i,(tag,title,subtitle) in enumerate([
        ('interior','慢一点，也很好','窗边的一张桌子'),
        ('product','一杯手冲','从一颗豆子开始'),
        ('storefront','街角咖啡','就在转角的地方'),
        ('process','认真做一杯','水、时间与耐心')]):
        progress(f'制作模拟镜头 {i+1}/4')
        mid=uuid.uuid4().hex; folder=DATA/mid; folder.mkdir(parents=True)
        image=Image.new('RGB',(720,1280),'#e8e0ce'); d=ImageDraw.Draw(image)
        d.rectangle((0,0,720,55),fill='#233c31'); d.text((30,15),'LOCALLENS / SYNTHETIC FIXTURE',font=font(18),fill='#f0e8d8')
        if tag=='product':
            d.ellipse((100,380,620,900),fill='#c9baa1'); d.ellipse((150,415,570,835),fill='#f8f2df')
            d.ellipse((185,450,535,800),fill='#523626'); d.ellipse((220,480,500,770),outline='#a8794c',width=6)
            d.arc((546,515,660,700),240,110,fill='#f8f2df',width=28)
            for x,y in [(105,345),(590,890),(83,927)]:d.ellipse((x,y,x+34,y+20),fill='#60402d')
        elif tag=='storefront':
            d.rectangle((90,365,630,950),fill='#273f33'); d.rectangle((125,510,340,920),fill='#b4c1b2')
            d.rectangle((370,510,595,920),fill='#bdc7b8'); d.rectangle((70,390,650,485),fill='#b85c3e')
            d.text((235,406),'街角咖啡',font=font(42),fill='#fff5e2')
            for x in range(80,650,60):d.polygon([(x,485),(x+30,510),(x+60,485)],fill='#ddc0a0')
            d.rectangle((0,950,720,1000),fill='#ad9e85'); d.ellipse((17,780,127,910),fill='#6b8051')
            d.rectangle((48,885,100,956),fill='#ba8060')
        elif tag=='interior':
            d.rectangle((60,310,660,760),fill='#264b3c'); d.rectangle((85,335,635,735),fill='#bfd1bd')
            d.line((360,335,360,735),fill='#345a45',width=15);d.line((85,535,635,535),fill='#345a45',width=15)
            d.ellipse((100,740,620,880),fill='#ac7047');d.rectangle((343,830,380,1040),fill='#684f38')
            d.ellipse((290,735,405,795),fill='#f9f2dd'); d.ellipse((308,740,386,777),fill='#63412e')
            d.polygon([(550,750),(480,510),(610,590)],fill='#597452');d.rectangle((510,725,600,805),fill='#c48b65')
        else:
            d.polygon([(180,550),(540,550),(430,820),(290,820)],fill='#c68c5e')
            d.line((180,550,540,550),fill='#f1cf9c',width=24)
            d.rectangle((275,820,445,920),fill='#f9f0d9');d.ellipse((240,800,480,850),fill='#f9f0d9')
            d.arc((390,325,630,555),190,330,fill='#425d4c',width=45)
            d.line((390,450,325,535),fill='#718a88',width=5)
        d.text((48,140),title,font=font(56),fill='#233c31');d.text((50,225),subtitle,font=font(27),fill='#82745f')
        d.text((48,1110),'模拟素材  /  不是真实商户拍摄',font=font(27),fill='#6b604d')
        d.text((48,1160),'仅检验操作、编排与渲染链路',font=font(24),fill='#82745f')
        png=folder/'illustration.png';image.save(png)
        run([FFMPEG,'-y','-v','error','-loop','1','-i',png,'-t','6','-r','25','-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p',folder/'source.mp4'])
        meta=analyze(folder/'source.mp4',mid,f'模拟镜头 {i+1} · {title}')
        (folder/'asset.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
        for shot in meta['shots']:
            shot.update(tags=[tag],confirmed=True,label_source='synthetic_ground_truth',quality=max(.6,shot['quality']))
            shots.append(shot)
    facts=[{'id':k,'kind':k,'value':v,'confirmed':True,'source':'程序构造的模拟事实，不对应真实商户'} for k,v in
           [('shop','街角咖啡'),('product','手冲咖啡'),('address','示例街道18号'),('offer','第二杯半价，限同款商品'),('validity','2026年10月23日至10月30日')]]
    p={'name':'街角咖啡 · 模拟案例','goal':'visit','synthetic':True,'facts':facts,'shots':shots}
    cache.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
    return p
