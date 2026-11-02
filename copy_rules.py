"""Optional product descriptions belong to an explicitly confirmed product."""
from copy import deepcopy

COPY_POLICY='confirmed-store-product-v2'

def copy_notes(facts):
    product=next((f for f in facts if f.get('kind')=='product' and f.get('confirmed') is True),None)
    if product and product['value'].strip() in ('咖啡','饮品','饮料','面包','蛋糕','商品','产品'):
        return ['目前只确认了商品大类“'+product['value']+'”。想突出具体产品，请填写菜单上的具体名称并重新确认画面；系统不会猜测品种。']
    return []

def detail_matches(detail,facts):
    product=next((f for f in facts if isinstance(f,dict) and f.get('kind')=='product' and f.get('confirmed') is True),None)
    ref=detail.get('product_ref')
    return bool(product and isinstance(ref,dict) and ref.get('id')==product['id'] and ref.get('value')==product['value'])

def recover_details(raw):
    """An imported stale description becomes editable, never silently reused."""
    project=deepcopy(raw)
    if not isinstance(project,dict) or not isinstance(project.get('facts'),list):return project
    changed=False
    for fact in project['facts']:
        if isinstance(fact,dict) and fact.get('kind')=='product_detail' and fact.get('confirmed') is True:
            if not detail_matches(fact,project['facts']):fact['confirmed']=False;changed=True
    if changed:
        message='商品名称或确认状态已变化，商品特点已保留但取消确认，请按当前商品重新核对。'
        project['warnings']=list(dict.fromkeys(project.get('warnings',[])+[message]))
    return project
