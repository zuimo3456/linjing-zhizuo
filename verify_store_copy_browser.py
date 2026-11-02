"""Real, isolated Edge browser flow, without touching the user's browser profile."""
import asyncio,hashlib,json,time
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence/copy-2026-11-02'
URL='http://127.0.0.1:4191'
async def main():
    saved=ROOT/'data/saved-project.json';before=(hashlib.sha256(saved.read_bytes()).hexdigest(),saved.stat().st_mtime_ns)
    async with async_playwright() as runtime:
        browser=await runtime.chromium.launch(channel='msedge',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
        context=await browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=await context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        await page.goto(URL);await page.locator('#facts input[data-value]').first.wait_for()
        async def imported(name):
            async with page.expect_response(lambda response:response.url.endswith('/api/reconcile')):
                await page.locator('#projectFile').set_input_files(str(OUT/name))
            await page.wait_for_function('!document.querySelector("#projectFile").disabled')
        await imported('coconut-project.json')
        product=page.get_by_role('textbox',name='具体商品名称',exact=True)
        detail=page.get_by_role('textbox',name='商品特点（可选）',exact=True)
        product_confirm=product.locator('..').locator('input[type=checkbox]')
        detail_confirm=detail.locator('..').locator('input[type=checkbox]')
        assert await product.input_value()=='生椰拿铁' and await detail.input_value()=='使用椰乳'
        assert await detail_confirm.is_checked()
        await product.fill('燕麦拿铁')
        assert not await product_confirm.is_checked() and not await detail_confirm.is_checked()
        assert not any(await page.locator('[data-product-confirm]').evaluate_all('(items)=>items.map(i=>i.checked)'))
        await detail_confirm.click();assert not await detail_confirm.is_checked()
        assert '请先填写并确认具体商品名称' in await page.locator('#status').inner_text()
        await product_confirm.check();await detail.fill('使用燕麦奶');await detail_confirm.check()
        async with page.expect_download() as download_info:await page.locator('#exportProjectBtn').click()
        download=await download_info.value;await download.save_as(OUT/'ui-renamed-export.json')
        exported=json.loads((OUT/'ui-renamed-export.json').read_text(encoding='utf8'))
        current=next(f for f in exported['facts'] if f['kind']=='product_detail')
        assert current['confirmed'] and current['product_ref']['value']=='燕麦拿铁' and current['value']=='使用燕麦奶'
        await page.screenshot(path=str(OUT/'ui-renamed-details.png'))
        await imported('stale-renamed-project.json')
        assert await product.input_value()=='燕麦拿铁' and not await detail_confirm.is_checked()
        assert '商品特点已保留但取消确认' in await page.locator('#projectWarnings').inner_text()
        await detail.fill('使用燕麦奶');await detail_confirm.check()
        assert '商品特点已保留但取消确认' not in await page.locator('#projectWarnings').inner_text()
        await imported('coconut-project.json')
        await page.locator('#planBtn').click()
        await page.wait_for_function('!document.querySelector("#renderBtn").disabled',timeout=240000)
        plan_text=await page.locator('#plan').inner_text()
        assert '生椰拿铁' in plan_text and '使用椰乳' in plan_text and '燕麦拿铁' not in plan_text
        await page.locator('#renderBtn').click()
        await page.locator('#result').wait_for(state='visible',timeout=240000)
        video=page.locator('#preview');video_url=await video.get_attribute('src')
        await video.evaluate('(v)=>v.play()')
        started=await video.evaluate('(v)=>({time:v.currentTime,paused:v.paused})')
        await page.wait_for_function('document.querySelector("#preview").ended',timeout=45000)
        ended=await video.evaluate('(v)=>({time:v.currentTime,duration:v.duration,ended:v.ended,readyState:v.readyState,error:v.error?.code??null})')
        assert ended['ended'] and ended['error'] is None and ended['readyState']>=3 and 15<=ended['duration']<=30
        assert not errors,errors
        await page.screenshot(path=str(OUT/'ui-final-copy-preview.png'),full_page=True)
        response=await context.request.get(URL+video_url.replace('result.mp4','report.json'));report=await response.json()
        (OUT/'browser-checks.json').write_text(json.dumps({'date':'2026-11-02','browser':'Playwright 1.64.1 / installed Edge, isolated temporary context',
           'rename_revokes_traits_and_shot_binding':True,'traits_require_confirmed_product':True,'actual_json_download_verified':True,
           'reimport_stale_details_revoked':True,'warning_clears_after_reconfirmation':True,'specific_copy_in_plan':True,
           'ui_generated_video':video_url,'playback_start':started,'playback_end':ended,'page_errors':errors,
           'voice':report['voice'],'human_listening':'pending'},ensure_ascii=False,indent=2),encoding='utf8')
        await browser.close()
    assert before==(hashlib.sha256(saved.read_bytes()).hexdigest(),saved.stat().st_mtime_ns)
    print('BROWSER PASS',video_url,ended,flush=True)
if __name__=='__main__':asyncio.run(main())
