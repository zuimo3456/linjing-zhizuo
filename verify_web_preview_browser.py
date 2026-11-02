"""Verify the real static preview locally or at its deployed URL, with no API mocks."""
import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'evidence/pages-2026-11-02'


async def main(url):
    OUT.mkdir(parents=True, exist_ok=True)
    errors, api_requests, asset_errors = [], [], []
    checks = []
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch(channel='msedge', headless=True)
        context = await browser.new_context(viewport={'width':1440,'height':1000}, accept_downloads=True, reduced_motion='reduce')
        page = await context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: api_requests.append(request.url) if '/api/' in request.url else None)
        page.on('response', lambda response: asset_errors.append({'url':response.url,'status':response.status}) if response.status>=400 and response.url.split('?')[0].endswith(('.js','.css')) else None)
        response = await page.goto(url)
        assert response.status == 200
        await page.evaluate('linjingStudio.ready')
        assert await page.evaluate('onlinePreview') is True
        assert await page.locator('#onlinePreviewNotice').is_visible()
        assert not await page.locator('#status').is_visible()
        checks.append('真实静态托管与预览提示正常，无后端初始化错误')

        await page.locator('[data-restaurant-category="hotpot"]').click()
        await page.locator('[data-restaurant-intent="offer"]').click()
        await page.locator('#briefShop').fill('示例火锅店')
        await page.locator('#briefSubject').fill('双人火锅套餐')
        assert await page.locator('#startBriefBtn').is_enabled()
        await page.screenshot(path=str(OUT/'online-home-desktop.png'), full_page=True, animations='disabled')
        await page.locator('#startBriefBtn').click()
        assert '双人火锅套餐' in await page.locator('#guideTitle').inner_text()
        assert await page.locator('.shoot-task').count() == 4
        await page.reload()
        await page.locator('#shooting').wait_for(state='visible')
        assert '双人火锅套餐' in await page.locator('#guideTitle').inner_text()
        await page.locator('#openRestaurantEditorBtn').click()
        await page.locator('#workspace').wait_for(state='visible')
        assert await page.locator('#goal').input_value() == 'promo'
        for selector in ['#videoFiles','#saveBtn','#planBtn','#renderBtn','#localAnalyzeBtn','#demoBtn','#projectFile','#labelsFile','#contextBtn']:
            assert await page.locator(selector).is_disabled(), selector
        assert await page.locator('#exportProjectBtn').is_enabled()
        checks.append('筛选、清单、刷新和工作台接线有效，后端功能明确停用')

        async with page.expect_download() as info:
            await page.locator('#exportProjectBtn').click()
        await (await info.value).save_as(OUT/'online-draft.json')
        draft = json.loads((OUT/'online-draft.json').read_text(encoding='utf8'))
        assert draft['preview_only'] is True and draft['shots'] == []
        assert draft['creative_brief']['product'] == '双人火锅套餐'
        assert all(not fact['confirmed'] for fact in draft['facts'])
        checks.append('页面草稿实际下载，无虚构素材或自动确认')

        await page.locator('#homeTab').click()
        await page.locator('[data-restaurant-intent="signature"]').click()
        await page.locator('#briefSubject').fill('鲜切牛肉')
        await page.locator('#startBriefBtn').click()
        await page.locator('#openRestaurantEditorBtn').click()
        await page.locator('#projectReplaceDialog').wait_for(state='visible')
        async with page.expect_download() as info:
            await page.locator('#backupStartBtn').click()
        await (await info.value).save_as(OUT/'online-previous-draft.json')
        await page.locator('#workspace').wait_for(state='visible')
        assert await page.locator('#goal').input_value() == 'attract'
        await page.locator('#researchTab').click()
        assert '在线预览不读取' in await page.locator('#benchmark').inner_text()
        checks.append('切换创作可备份草稿，研究页不调用不存在的API')

        await page.locator('#homeTab').click()
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.screenshot(path=str(OUT/'online-home-mobile.png'), full_page=True, animations='disabled')
        await page.locator('#startBriefBtn').click()
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.screenshot(path=str(OUT/'online-guide-mobile.png'), full_page=True, animations='disabled')
        checks.append('手机首页与拍摄清单无横向溢出')
        assert not errors, errors
        assert not api_requests, api_requests
        assert not asset_errors, asset_errors
        await browser.close()
    suffix = 'deployed' if url.startswith('https:') else 'local'
    (OUT/('browser-'+suffix+'.json')).write_text(json.dumps({'url':url,'checks':checks,'page_errors':errors,'api_requests':api_requests,'asset_errors':asset_errors},ensure_ascii=False,indent=2),encoding='utf8')
    print('PREVIEW BROWSER PASS', suffix, len(checks), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:4195/web-preview/')
    asyncio.run(main(parser.parse_args().url))
