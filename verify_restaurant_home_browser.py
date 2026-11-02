"""Exercise the restaurant entry with real Edge and real local APIs; never save a project."""
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'evidence/home-2026-11-02'
URL = 'http://127.0.0.1:4193'


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    saved = ROOT / 'data/saved-project.json'
    saved_before = (hashlib.sha256(saved.read_bytes()).hexdigest(), saved.stat().st_mtime_ns)
    checks = []
    page_errors = []
    writes = []

    def passed(name):
        checks.append(name)
        print('PASS', name, flush=True)

    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch(channel='msedge', headless=True)
        context = await browser.new_context(viewport={'width':1440, 'height':1050}, timezone_id='Asia/Shanghai', accept_downloads=True)
        page = await context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' else None)
        await page.clock.install(time=datetime(2026, 11, 2, 1, 0, tzinfo=timezone.utc))
        await page.goto(URL)
        await page.evaluate('linjingStudio.ready')
        assert await page.locator('#home').is_visible()
        assert not await page.locator('#workspace').is_visible()
        assert await page.locator('#startBriefBtn').is_disabled()
        assert await page.locator('#timeGreeting').inner_text() == '早上好，'
        await page.clock.set_fixed_time(datetime(2026, 11, 2, 4, 0, tzinfo=timezone.utc))
        await page.get_by_role('button', name='开始创作', exact=True).click()
        assert await page.locator('#timeGreeting').inner_text() == '中午好，'
        await page.clock.set_fixed_time(datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc))
        await page.get_by_role('button', name='开始创作', exact=True).click()
        assert await page.locator('#timeGreeting').inner_text() == '晚上好，'
        passed('首页默认展示与早中晚问候')

        await page.locator('[data-restaurant-category="home"]').click()
        await page.locator('[data-restaurant-intent="signature"]').click()
        await page.locator('#briefShop').fill('梧桐家常菜')
        await page.locator('#briefSubject').fill('   ')
        assert await page.locator('#startBriefBtn').is_disabled()
        await page.locator('#briefSubject').fill('砂锅\u202e牛肉')
        assert await page.locator('#startBriefBtn').is_disabled()
        assert await page.locator('#briefInvalidText').is_visible()
        await page.locator('#briefSubject').fill('砂锅牛肉')
        assert await page.locator('#startBriefBtn').is_enabled()
        await page.screenshot(path=str(OUT/'home-desktop.png'), full_page=True, animations='disabled')
        passed('缺失信息、空白和不可见字符不能进入清单')

        await page.locator('#startBriefBtn').click()
        await page.locator('#shooting').wait_for(state='visible')
        assert page.url.endswith('#shoot/signature')
        assert '砂锅牛肉' in await page.locator('#guideTitle').inner_text()
        assert '翻炒、浇汁或出锅' in await page.locator('#guideChecklist').inner_text()
        assert await page.locator('.shoot-task').count() == 4
        await page.reload()
        await page.evaluate('linjingStudio.ready')
        assert await page.locator('#shooting').is_visible()
        assert '砂锅牛肉' in await page.locator('#guideTitle').inner_text()
        await page.screenshot(path=str(OUT/'guide-signature-desktop.png'), full_page=True, animations='disabled')
        await page.locator('#editBriefBtn').click()
        assert await page.locator('#briefSubject').input_value() == '砂锅牛肉'
        passed('清单路由、刷新与返回保留选择')

        # The six categories must each produce a task for the selected intent.
        for category in ['home','hotpot','barbecue','noodles','breakfast','snack']:
            for intent in ['signature','offer','restaurant']:
                await page.locator('[data-restaurant-category="'+category+'"]').click()
                await page.locator('[data-restaurant-intent="'+intent+'"]').click()
                await page.locator('#briefShop').fill('梧桐家常菜')
                await page.locator('#briefSubject').fill('双人家常菜套餐' if intent == 'offer' else '砂锅牛肉')
                await page.locator('#startBriefBtn').click()
                await page.locator('#shooting').wait_for(state='visible')
                assert page.url.endswith('#shoot/'+intent)
                assert await page.locator('.shoot-task').count() == 4
                guide = await page.locator('#guideChecklist').inner_text()
                assert ('制作镜头' in guide) == (intent == 'signature')
                assert ('套餐完整亮相' in guide) == (intent == 'offer')
                assert ('先认识这家店' in guide) == (intent == 'restaurant')
                await page.locator('#editBriefBtn').click()
        passed('六种饭店类型与三种目标共18组清单')

        await page.locator('[data-restaurant-intent="offer"]').click()
        assert await page.locator('#briefSubject').input_value() == ''
        assert await page.locator('#startBriefBtn').is_disabled()
        await page.locator('#briefSubject').fill('<img src=x onerror=alert(1)>套餐')
        await page.locator('#startBriefBtn').click()
        await page.locator('#shooting').wait_for(state='visible')
        assert await page.locator('#guideChecklist img').count() == 0
        assert '<img src=x' in await page.locator('#guideTitle').inner_text()
        await page.locator('#editBriefBtn').click()
        await page.locator('#briefSubject').fill('双人家常菜套餐')
        await page.locator('#startBriefBtn').click()
        await page.locator('#shooting').wait_for(state='visible')
        await page.screenshot(path=str(OUT/'guide-offer-desktop.png'), full_page=True, animations='disabled')
        passed('更换目标重新填写主角，文字安全显示')

        # An existing edit must remain intact when starting is cancelled.
        current = await page.evaluate('JSON.stringify(project)')
        has_content = await page.evaluate('linjingStudio.hasContent()')
        await page.locator('#openRestaurantEditorBtn').click()
        if has_content:
            await page.locator('#projectReplaceDialog').wait_for(state='visible')
            await page.locator('#cancelStartBtn').click()
            assert current == await page.evaluate('JSON.stringify(project)')
            await page.locator('#openRestaurantEditorBtn').click()
            async with page.expect_download() as info:
                await page.locator('#backupStartBtn').click()
            backup = await info.value
            await backup.save_as(OUT/'previous-project-backup.json')
            assert json.loads((OUT/'previous-project-backup.json').read_text(encoding='utf8'))['facts']
        await page.locator('#workspace').wait_for(state='visible')
        draft = await page.evaluate('project')
        assert draft['goal'] == 'promo'
        assert draft['creative_brief']['category'] == 'snack'
        assert draft['shots'] == [] and draft['synthetic'] is False
        assert next(f['value'] for f in draft['facts'] if f['kind']=='shop') == '梧桐家常菜'
        assert next(f['value'] for f in draft['facts'] if f['kind']=='product') == '双人家常菜套餐'
        assert all(not f['confirmed'] and not f['source'] for f in draft['facts'])
        assert await page.locator('#goal').input_value() == 'promo'
        assert await page.locator('#restaurantWorkspaceBrief').is_visible()
        passed('取消保留原项目，备份后新建，信息带入且全部待确认')

        async with page.expect_download() as info:
            await page.locator('#exportProjectBtn').click()
        exported = await info.value
        await exported.save_as(OUT/'restaurant-draft-export.json')
        packed = json.loads((OUT/'restaurant-draft-export.json').read_text(encoding='utf8'))
        assert packed['creative_brief'] == draft['creative_brief']
        async with page.expect_response(lambda response: response.url.endswith('/api/reconcile')):
            await page.locator('#projectFile').set_input_files(str(OUT/'restaurant-draft-export.json'))
        await page.wait_for_function('!document.querySelector("#projectFile").disabled')
        assert (await page.evaluate('project'))['creative_brief'] == draft['creative_brief']
        await page.locator('#planBtn').click()
        await page.wait_for_function('!document.querySelector("#planBtn").disabled')
        assert await page.locator('#renderBtn').is_disabled()
        assert '请确认' in await page.locator('#plan').inner_text()
        await page.screenshot(path=str(OUT/'workspace-handoff.png'), full_page=True, animations='disabled')
        passed('实际导出与导入保留选择，未确认事实不能生成视频')

        for target, goal in [('signature','attract'),('restaurant','visit')]:
            await page.locator('#homeTab').click()
            await page.locator('[data-restaurant-intent="'+target+'"]').click()
            await page.locator('#briefSubject').fill('砂锅牛肉')
            await page.locator('#startBriefBtn').click()
            await page.locator('#openRestaurantEditorBtn').click()
            await page.locator('#projectReplaceDialog').wait_for(state='visible')
            async with page.expect_download() as info:
                await page.locator('#backupStartBtn').click()
            await (await info.value).save_as(OUT/('before-'+target+'.json'))
            await page.locator('#workspace').wait_for(state='visible')
            assert await page.locator('#goal').input_value() == goal
            assert (await page.evaluate('project'))['creative_brief']['intent'] == target
            unchanged = await page.evaluate('JSON.stringify(project)')
            await page.locator('#homeTab').click()
            await page.locator('#startBriefBtn').click()
            await page.locator('#openRestaurantEditorBtn').click()
            await page.locator('#workspace').wait_for(state='visible')
            assert not await page.locator('#projectReplaceDialog').is_visible()
            assert unchanged == await page.evaluate('JSON.stringify(project)')
        passed('三种目标正确带入工作台，相同创作重复进入不清空内容')

        await page.locator('#researchTab').click()
        assert await page.locator('#research').is_visible()
        assert not await page.locator('#home').is_visible()
        await page.locator('#workTab').click()
        assert await page.locator('#workspace').is_visible()
        await page.locator('#homeTab').click()
        assert await page.locator('#home').is_visible()
        await page.go_back()
        await page.locator('#workspace').wait_for(state='visible')
        assert await page.locator('#workspace').is_visible()
        await page.goto(URL+'/#shoot/unknown')
        assert await page.locator('#home').is_visible()
        passed('首页、工作台、研究页导航与无效清单路由')

        await page.locator('[data-restaurant-category="home"]').click()
        await page.locator('[data-restaurant-intent="signature"]').click()
        await page.locator('#briefSubject').fill('砂锅牛肉')
        await page.set_viewport_size({'width':390, 'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.screenshot(path=str(OUT/'home-mobile.png'), full_page=True, animations='disabled')
        await page.locator('#startBriefBtn').click()
        await page.locator('#shooting').wait_for(state='visible')
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.screenshot(path=str(OUT/'guide-mobile.png'), full_page=True, animations='disabled')
        passed('390像素手机首页和拍摄清单没有横向溢出')

        assert not page_errors, page_errors
        assert not any(url.endswith('/api/save') or url.endswith('/api/render') for url in writes)
        await browser.close()

    assert saved_before == (hashlib.sha256(saved.read_bytes()).hexdigest(), saved.stat().st_mtime_ns)
    (OUT/'browser-checks.json').write_text(json.dumps({
        'date':'2026-11-02', 'url':URL, 'browser':'Installed Edge / isolated Playwright context',
        'checks':checks, 'page_errors':page_errors, 'post_requests':writes,
        'saved_project_unchanged':True, 'sample_videos':'Not recorded; UI labels this as pending',
        'automated_reference_comparison':'Not implemented by this frontend change',
        'merchant_acceptance':'pending'
    }, ensure_ascii=False, indent=2), encoding='utf8')
    print('BROWSER PASS', len(checks), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
