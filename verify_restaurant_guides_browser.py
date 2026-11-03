"""Check every researched restaurant guide and the no-kitchen handoff in a real browser."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parent


async def main(url,out):
    out.mkdir(parents=True,exist_ok=True)
    saved=ROOT/'data/saved-project.json'
    before=(hashlib.sha256(saved.read_bytes()).hexdigest(),saved.stat().st_mtime_ns)
    errors=[];writes=[];matrix=[];finished=[]
    async with async_playwright() as runtime:
        browser=await runtime.chromium.launch(channel='msedge',headless=True)
        context=await browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True,reduced_motion='reduce')
        page=await context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:writes.append(request.url) if request.method=='POST' else None)
        await page.goto(url);await page.evaluate('linjingStudio.ready')
        subjects={'signature':'本次主推菜','offer':'本次双人套餐','restaurant':'搭配展示菜'}
        categories=['home','hotpot','barbecue','noodles','breakfast','snack']
        role_map={'商品':'product','制作':'process','环境':'interior','门头':'storefront'}
        required_roles={'visit':{'storefront','product','interior'},'attract':{'product','process','interior'},'promo':{'product','storefront'}}
        for category in categories:
            for intent in subjects:
                await page.locator('#homeTab').click()
                await page.locator('[data-restaurant-category="'+category+'"]').click()
                await page.locator('[data-restaurant-intent="'+intent+'"]').click()
                await page.locator('#briefShop').fill('本次示例门店')
                await page.locator('#briefSubject').fill(subjects[intent])
                await page.locator('#startBriefBtn').click()
                await page.locator('#shooting').wait_for(state='visible')
                guide=await page.evaluate('restaurantGuideLibrary.build({category:'+json.dumps(category)+',intent:'+json.dumps(intent)+',product:'+json.dumps(subjects[intent])+',shop:"本次示例门店",capture_mode:"process"})')
                assert await page.locator('.shoot-task').count()==5
                assert await page.locator('.shoot-purpose').count()==5
                assert await page.locator('.shoot-camera').count()==5
                assert await page.locator('.shoot-more').count()==5
                assert len({task['id'] for task in guide['tasks']})==5
                assert all(task['copy'] and task['camera'] and task['check'] and task['alternative'] and task['avoid'] for task in guide['tasks'])
                actual_roles={role_map[task['role']] for task in guide['tasks'] if task['required']}
                assert required_roles[guide['backendGoal']] <= actual_roles
                assert '最优效果保证' in await page.locator('.guide-pending').inner_text()
                assert '自查' in await page.locator('.shoot-check').first.inner_text()
                assert await page.locator('#guideSources a').count()>=4
                assert ('制作镜头' in await page.locator('#guideChecklist').inner_text())==(intent=='signature')
                matrix.append({'category':category,'intent':intent,**guide})
                if category=='hotpot' and intent=='signature':
                    await page.screenshot(path=str(out/'hotpot-guide-desktop.png'),full_page=True,animations='disabled')
            print('PASS',category,'three promotion goals',flush=True)
        assert len({json.dumps(item['tasks'],ensure_ascii=False) for item in matrix})==18

        for category in categories:
            await page.locator('#homeTab').click()
            await page.locator('[data-restaurant-category="'+category+'"]').click()
            await page.locator('[data-restaurant-intent="signature"]').click()
            await page.locator('#briefSubject').fill('本次成品菜')
            await page.locator('#startBriefBtn').click()
            await page.locator('#captureMode').select_option('finished')
            assert '地址' in await page.locator('#guideCaptureNote').inner_text()
            assert '制作镜头' not in await page.locator('#guideChecklist').inner_text()
            assert await page.locator('[data-shot-key$=".location"][data-required="true"]').count()==1
            guide=await page.evaluate('restaurantGuideLibrary.build({category:'+json.dumps(category)+',intent:"signature",product:"本次成品菜",shop:"本次示例门店",capture_mode:"finished"})')
            assert guide['backendGoal']=='visit'
            assert {'product','interior','storefront'} <= {role_map[task['role']] for task in guide['tasks'] if task['required']}
            await page.reload();await page.evaluate('linjingStudio.ready')
            await page.locator('#shooting').wait_for(state='visible')
            assert await page.locator('#captureMode').input_value()=='finished'
            await page.locator('#openRestaurantEditorBtn').click()
            if await page.locator('#projectReplaceDialog').is_visible():
                async with page.expect_download() as info:await page.locator('#backupStartBtn').click()
                await (await info.value).save_as(out/('before-'+category+'.json'))
            await page.locator('#workspace').wait_for(state='visible')
            draft=await page.evaluate('project')
            assert draft['goal']=='visit' and draft['creative_brief']['capture_mode']=='finished'
            assert '成品路线' in await page.locator('#restaurantWorkspaceBrief').inner_text()
            assert draft['creative_brief']['guide_version']=='restaurant-shooting-v2-2026-11-03'
            assert all(not fact['confirmed'] and not fact['source'] for fact in draft['facts'])
            assert draft['shots']==[]
            finished.append({'category':category,'guide':guide,'workspace_goal':draft['goal'],'facts_unconfirmed':True})
            print('PASS',category,'no-kitchen handoff and refresh',flush=True)

        await page.locator('#homeTab').click()
        await page.locator('[data-restaurant-intent="offer"]').click()
        await page.locator('#briefSubject').fill('<img src=x onerror=alert(1)>套餐')
        await page.locator('#startBriefBtn').click()
        assert await page.locator('#guideChecklist img').count()==0
        await page.locator('#homeTab').click()
        await page.locator('#briefSubject').fill('双人小吃套餐')
        await page.locator('#startBriefBtn').click()
        await page.locator('.shoot-more').first.locator('summary').click()
        await page.locator('.guide-evidence summary').click()
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await page.screenshot(path=str(out/'offer-guide-mobile.png'),full_page=True,animations='disabled')
        assert not errors,errors
        assert not any(path.endswith('/api/save') or path.endswith('/api/render') for path in writes)
        await browser.close()
    assert before==(hashlib.sha256(saved.read_bytes()).hexdigest(),saved.stat().st_mtime_ns)
    result={'url':url,'matrix':matrix,'no_kitchen':finished,'page_errors':errors,'post_requests':writes,'saved_project_unchanged':True,'source_scope':'Platform guidance and partial observations, not optimality or merchant acceptance','automatic_sample_comparison':False}
    (out/'guide-matrix.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('GUIDE BROWSER PASS',len(matrix),'standard +',len(finished),'no-kitchen guides',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:4196')
    parser.add_argument('--out',default=str(ROOT/'evidence/restaurant-guides-2026-11-03'))
    args=parser.parse_args()
    asyncio.run(main(args.url,Path(args.out)))
