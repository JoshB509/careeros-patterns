from playwright.sync_api import sync_playwright
import glob, shutil
out='/tmp/claude-0/prev/'
with sync_playwright() as p:
    b=p.chromium.launch(args=['--disable-web-security','--allow-file-access-from-files'])
    plug=b.new_page(viewport={'width':260,'height':130}); perr=[]; plug.on('pageerror',lambda e:perr.append(str(e)))
    plug.goto('file:///E:/Videos/DaJoshiCut/panel/preview.html')
    app=b.new_page(viewport={'width':600,'height':780}); aerr=[]; app.on('pageerror',lambda e:aerr.append(str(e)))
    app.goto('http://127.0.0.1:47820/app/'); app.wait_for_timeout(500); app.screenshot(path=out+'a_connecting.png'); app.wait_for_timeout(3000)
    app.click('[data-go=clean]'); app.wait_for_timeout(5000)
    for f in glob.glob('/home/claude/e2e/Projects/*/'): shutil.copy('/home/claude/e2e/sample-5min-transcript.json', f+'transcript.json')
    app.click('#main'); app.wait_for_timeout(6000)
    app.click('#back'); app.wait_for_timeout(1500); app.screenshot(path=out+'a_home3.png')
    app.click('[data-go=flubs]'); app.wait_for_timeout(1500); app.screenshot(path=out+'a_flubs0.png')
    if app.locator('[data-w="60"]').count()==0:
        app.click('#main'); app.wait_for_timeout(6000)
    # highlight a range with the mouse
    a=app.locator('[data-w="60"]').bounding_box(); z=app.locator('[data-w="66"]').bounding_box()
    app.mouse.move(a['x']+2,a['y']+5); app.mouse.down(); app.mouse.move(z['x']+z['width']-2,z['y']+5,steps=8); app.mouse.up(); app.wait_for_timeout(400)
    app.screenshot(path=out+'a_flubs1.png')
    app.click('[data-act=cutSel]'); app.wait_for_timeout(300); print('flub foot',app.inner_text('#footInfo'))
    app.click('#main'); app.wait_for_timeout(7000); print('toast',app.inner_text('#toastMsg'))
    app.click('#back'); app.wait_for_timeout(1000); app.click('[data-go=anim]'); app.wait_for_timeout(1500)
    app.click('[data-act=plan]'); app.wait_for_timeout(20000); app.screenshot(path=out+'a_anim.png', full_page=True)
    app.click('#gear'); app.wait_for_timeout(500); app.screenshot(path=out+'a_settings.png')
    plug.screenshot(path=out+'p_panel.png')
    print('perr',perr,'aerr',aerr[:5]); b.close()
