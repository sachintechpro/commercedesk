"""Optional Playwright smoke test. Requires playwright and installed Chromium."""
import os, pathlib, subprocess, sys, tempfile, time, urllib.request
from playwright.sync_api import sync_playwright
root=pathlib.Path(__file__).resolve().parents[1]
temp=tempfile.TemporaryDirectory()
port='11328'
env={**os.environ,'PORT':port,'COMMERCE_DB_PATH':str(pathlib.Path(temp.name)/'test.sqlite3'),'ADMIN_PASSWORD':'BrowserTest!2026','SESSION_SECRET':'only-for-browser-test'}
server=subprocess.Popen([sys.executable,str(root/'server.py')],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
try:
 for _ in range(50):
  try:
   urllib.request.urlopen('http://localhost:'+port+'/health',timeout=.5);break
  except Exception:time.sleep(.1)
 else:raise RuntimeError('server startup failed')
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,**({'executable_path':os.environ['CHROMIUM_EXECUTABLE']} if os.environ.get('CHROMIUM_EXECUTABLE') else {}))
  page=browser.new_page(viewport={'width':1440,'height':900})
  errs=[];page.on('pageerror', lambda e: errs.append(str(e)))
  base='http://127.0.0.1:'+port
  page.goto(base+'/');page.get_by_text('Featured hardware and supplies').wait_for()
  assert page.locator('.product-card').count()>=6
  page.screenshot(path=str(root/'storefront-preview.png'),full_page=True)
  print('Home verified:',page.locator('.product-card').count(),'products')
  page.goto(base+'/product/stainless-steel-glass-door-hinge-gh-101');page.get_by_text('Related products').wait_for()
  page.get_by_role('button',name='Add to cart').click();assert page.locator('#cart-count').inner_text()=='1'
  page.goto(base+'/cart');page.get_by_text('Shopping cart').wait_for()
  page.get_by_role('link',name='Proceed to demo checkout').click();page.get_by_role('button',name='Place demo order').click()
  page.wait_for_url('**/confirmation');page.get_by_text('Ready for fulfillment').wait_for();print('Cart + checkout verified')
  page.goto(base+'/admin');page.locator('#admin-password').wait_for();page.locator('#admin-password').fill('BrowserTest!2026');page.get_by_role('button',name='Sign in to administration').click();page.wait_for_url('**/admin')
  page.get_by_text('Operations overview').wait_for();print('Admin login verified')
  page.goto(base+'/admin/products/GH-101');page.locator('#p-price').wait_for();page.locator('#p-price').fill('32.55');page.get_by_role('button',name='Save changes').click();page.wait_for_url('**/admin/products');page.goto(base+'/product/stainless-steel-glass-door-hinge-gh-101');page.get_by_text('$32.55').wait_for();print('Edit reflected on storefront')
  page.goto(base+'/admin/import');page.locator('#csv-file').set_input_files(str(root/'samples'/'products-create.csv'))
  files=[str(root/'samples'/'images'/f'{sku}.png') for sku in ('GH-205','GS-305','GT-505')]
  page.locator('#csv-images').set_input_files(files)
  page.get_by_role('button',name='Read CSV & validate').click();page.get_by_text('3 valid / 0 invalid').wait_for(timeout=20000)
  page.get_by_role('button',name='Publish validated batch').click();page.get_by_text('Batch imported successfully.').wait_for(timeout=20000)
  page.goto(base+'/shop');page.get_by_text('Satin Glass Hinge Kit').wait_for();print('CSV import + storefront verified')
  page.goto(base+'/admin/orders/DEMO-1002');page.get_by_text('Inventory shortage').wait_for();assert page.get_by_role('button',name='Generate sample shipping label').count()==0
  page.screenshot(path=str(root/'admin-preview.png'),full_page=True)
  print('Shortage label block verified')
  assert not errs, errs
  browser.close()
 print('All browser smoke tests passed')
finally:
 server.terminate()
 try:server.wait(timeout=3)
 except subprocess.TimeoutExpired:server.kill()
 temp.cleanup()
