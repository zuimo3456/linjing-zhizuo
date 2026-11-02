"""Simulated menus: specific names, literal traits and product-change safety."""
import copy,hashlib,json,shutil,time,urllib.request,urllib.error
from pathlib import Path
from planner import caption_for
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence/copy-2026-11-02';OUT.mkdir(parents=True,exist_ok=True)
DELIVERY=ROOT/'交付/具体商品文案';DELIVERY.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:4191'
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def api(path,value=None):
    req=urllib.request.Request(URL+path,data=None if value is None else json.dumps(value,ensure_ascii=False).encode(),
                              headers={'Content-Type':'application/json','Origin':URL})
    try:
        with urllib.request.urlopen(req,timeout=900) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
def main():
    saved=ROOT/'data/saved-project.json';before=(hashlib.sha256(saved.read_bytes()).hexdigest(),saved.stat().st_mtime_ns)
    base=json.loads((ROOT/'data/demo-project.json').read_text(encoding='utf8'))
    choices=[('coconut','梧桐咖啡','生椰拿铁','使用椰乳'),('oat','巷口咖啡','燕麦拿铁','使用燕麦奶'),
             ('bakery','小麦面包房','原味可颂','当日烘焙')]
    cases=[]
    for key,shop,product,detail in choices:
        p=copy.deepcopy(base);p.pop('saved_edit',None);p['goal']='visit';p['name']=shop+' · 虚构菜单文案测试';p['synthetic']=True
        for fact in p['facts']:
            if fact['kind']=='shop':fact['value']=shop
            if fact['kind']=='product':fact['value']=product
            fact['source']='程序构造的模拟事实，不对应真实门店菜单'
        f=next(f for f in p['facts'] if f['kind']=='product')
        p['facts'].append({'id':'details','kind':'product_detail','value':detail,'confirmed':True,
                          'source':'程序构造的模拟特点','product_ref':{'id':f['id'],'value':f['value']}})
        if key=='bakery':p['shots']=[]  # Coffee illustrations are not bakery evidence.
        for i,shot in enumerate(p['shots']):
            if 'product' in shot['tags']:
                shot['product_binding']=None
                code,result=api('/api/confirm-shot',{'project':p,'shot_id':shot['id'],'mode':'product','checked':True})
                assert code==200,result;p['shots'][i]=result['shot']
        save(key+'-project.json',p)
        captions={role:caption_for(role,p['facts'],p['goal'])[0] for role in ('storefront','product','process','interior')}
        assert all(shop in t for t in captions.values()) and product in captions['product'] and detail in captions['product']
        code,plan=api('/api/plan',{'project':p});assert code==200,plan
        assert plan['copy_policy']=='confirmed-store-product-v2'
        if key!='bakery':assert plan['renderable'],plan
        else:assert not plan['renderable']  # No bakery visuals supplied.
        save(key+'-plan.json',plan);cases.append({'case':key,'captions':captions,'renderable':plan['renderable']})
        print(key,json.dumps(captions,ensure_ascii=False),flush=True)
        if key=='coconut':
            code,pending=api('/api/render',{'project':p,'plan':plan});assert code==202,pending
            for _ in range(300):
                code,item=api('/api/jobs/'+pending['job_id'])
                if item['status']=='done':rendered=item['result'];break
                assert item['status']!='error',item;time.sleep(1)
            else:raise TimeoutError('render')
            assert rendered['metrics']['voice']['speaker']=='Vivian'
            save('render.json',rendered);folder=ROOT/'data'/rendered['video'].split('/')[2]
            shutil.copyfile(folder/'result.mp4',DELIVERY/'生椰拿铁-模拟文案样片.mp4')
            shutil.copyfile(folder/'report.json',DELIVERY/'运行报告.json')
            stale=copy.deepcopy(p);next(f for f in stale['facts'] if f['kind']=='product')['value']='燕麦拿铁'
            code,blocked=api('/api/plan',{'project':stale});assert code==400 and '商品特点' in blocked['error'],blocked
            code,recovered=api('/api/reconcile',{'project':stale});assert code==200,recovered
            assert not next(f for f in recovered['facts'] if f['kind']=='product_detail')['confirmed']
            assert '商品特点' in ' '.join(recovered['warnings'])
            save('stale-renamed-project.json',stale);save('stale-recovery.json',recovered)
            tampered=copy.deepcopy(plan);next(s for s in tampered['segments'] if s['role']=='product')['text']+='全城第一。'
            code,blocked=api('/api/validate',{'project':p,'plan':tampered});assert code==400 and '文案' in blocked['error'],blocked
    assert before==(hashlib.sha256(saved.read_bytes()).hexdigest(),saved.stat().st_mtime_ns)
    save('results.json',{'date':'2026-11-02','scope':'Fictional menus, illustrated technical fixtures; not merchant claims or recognition accuracy',
                         'cases':cases,'stale_details_rejected':True,'stale_import_recovered':True,'invented_claim_rejected':True,
                         'primary_saved_project_unchanged':True,'video':rendered['video'],'human_listening':'pending'})
    print('DONE',rendered['video'],flush=True)
if __name__=='__main__':main()
