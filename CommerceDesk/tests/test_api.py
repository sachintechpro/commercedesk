import base64
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import HTTPCookieProcessor,Request,build_opener
from urllib.error import HTTPError,URLError
ROOT=Path(__file__).resolve().parents[1]

class ApiJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1]
        cls.base='http://127.0.0.1:'+str(cls.port)
        env={**os.environ,'PORT':str(cls.port),'ADMIN_PASSWORD':'TestPassword!2026','SESSION_SECRET':'test-only-do-not-use-in-prod','COMMERCE_DB_PATH':str(Path(cls.temp.name)/'store.sqlite3')}
        cls.process=subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        cls.opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        for _ in range(80):
            try:
                cls.req('GET','/health');break
            except (URLError,ConnectionError):time.sleep(.1)
        else:raise RuntimeError('Test server failed to start')
    @classmethod
    def tearDownClass(cls):
        cls.process.terminate();cls.process.wait(timeout=3);cls.temp.cleanup()
    @classmethod
    def req(cls,method,path,data=None,csrf=None):
        blob=json.dumps(data).encode() if data is not None else None
        req=Request(cls.base+path,data=blob,method=method,headers={'Content-Type':'application/json','X-CSRF-Token':csrf or ''} if data is not None else {})
        try:
            resp=cls.opener.open(req)
            body=resp.read();type=resp.headers.get('Content-Type','')
            return resp.status,json.loads(body) if 'json' in type else body.decode(errors='ignore')
        except HTTPError as e:
            b=e.read();return e.code,json.loads(b) if b.startswith(b'{') else b.decode(errors='ignore')
    @classmethod
    def login(cls):
        code,result=cls.req('POST','/api/admin/login',{'username':'admin@commercedesk.demo','password':'TestPassword!2026'});assert code==200,result
        return result['csrf']
    def test_01_catalog_public(self):
        code,r=self.req('GET','/api/catalog');self.assertEqual(code,200);self.assertGreaterEqual(len(r['products']),10)
    def test_02_admin_protected(self):
        code,r=self.req('GET','/api/admin/dashboard');self.assertEqual(code,401)
    def test_03_login_rejects_wrong_password(self):
        code,r=self.req('POST','/api/admin/login',{'username':'admin@commercedesk.demo','password':'wrong'});self.assertEqual(code,401)
    def test_04_csrf(self):
        self.login();code,r=self.req('POST','/api/admin/products',{'sku':'AB-909'});self.assertEqual(code,403)
    def test_05_import_preview_atomic(self):
        csrf=self.login()
        bad=(ROOT/'samples/products-errors.csv').read_text();body={'csv_text':bad,'images':[]}
        code,r=self.req('POST','/api/admin/import/preview',body,csrf)
        self.assertEqual(code,200);self.assertFalse(r['review']['ready']);self.assertEqual(r['review']['total'],3)
        code,r=self.req('POST','/api/admin/import',body,csrf)
        self.assertEqual(code,422)
        code,catalog=self.req('GET','/api/catalog')
        self.assertFalse(any(x['sku']=='GS-999' for x in catalog['products']))
    def test_06_upload_product_with_matched_image(self):
        csrf=self.login();image=base64.b64encode((ROOT/'samples/images/GH-205.png').read_bytes()).decode()
        p={'sku':'GH-205','name':'New hinge test','category':'Glass Door Hardware','description':'A fictional new test item.','price':'25.75','stock':4,'status':'published','image':{'filename':'GH-205.png','content_b64':image}}
        code,r=self.req('POST','/api/admin/products',p,csrf);self.assertEqual(code,201,r)
        code,r=self.req('GET','/api/product/'+r['product']['slug']);self.assertEqual(code,200);self.assertEqual(r['product']['price_cents'],2575)
        code,img=self.req('GET','/api/images/GH-205');self.assertEqual(code,200)
    def test_07_update_product_reflected(self):
        csrf=self.login();code,r=self.req('PUT','/api/admin/products/GH-205',{'sku':'GH-205','price':'29.99'},csrf);self.assertEqual(code,200,r)
        code,r=self.req('GET','/api/product/'+r['product']['slug']);self.assertEqual(r['product']['price_cents'],2999)
    def test_08_csv_import_valid(self):
        csrf=self.login();csv=(ROOT/'samples/products-create.csv').read_text()
        # Already created GH-205 above, so import GS-305 and GT-505 only.
        lines=csv.splitlines();csv='\n'.join([lines[0]]+lines[2:])+'\n'
        images=[{'filename':sku+'.png','content_b64':base64.b64encode((ROOT/'samples/images'/f'{sku}.png').read_bytes()).decode()} for sku in ('GS-305','GT-505')]
        payload={'csv_text':csv,'images':images}
        code,r=self.req('POST','/api/admin/import/preview',payload,csrf);self.assertEqual(code,200,r);self.assertTrue(r['review']['ready'],r)
        code,r=self.req('POST','/api/admin/import',payload,csrf);self.assertEqual(code,200,r);self.assertEqual(r['result']['created'],2)
        code,r=self.req('GET','/api/catalog');self.assertTrue(any(x['sku']=='GS-305' for x in r['products']))
    def test_09_ready_order_and_label(self):
        csrf=self.login()
        code,r=self.req('POST','/api/orders',{'buyer':'Sample Client','city':'Fictional City, CA','items':[{'sku':'GH-101','qty':1}]})
        self.assertEqual(code,201,r);self.assertEqual(r['order']['status'],'ready');oid=r['order']['id']
        code,r=self.req('POST',f'/api/admin/orders/{oid}/label',{},csrf);self.assertEqual(code,200,r);self.assertEqual(r['order']['status'],'label_created')
        code,r=self.req('POST',f'/api/admin/orders/{oid}/dispatch',{},csrf);self.assertEqual(code,422)
        code,r=self.req('POST',f'/api/admin/orders/{oid}/verify',{'label_ref':'WRONG-LABEL'},csrf);self.assertEqual(code,422)
        code,r=self.req('POST',f'/api/admin/orders/{oid}/verify',{'label_ref':'SAMPLE-'+oid},csrf);self.assertEqual(code,200,r);self.assertTrue(r['order']['label_verified'])
        code,r=self.req('POST',f'/api/admin/orders/{oid}/dispatch',{},csrf);self.assertEqual(code,200,r);self.assertEqual(r['order']['status'],'shipped')
    def test_10_shortage_prevents_label_and_alert(self):
        csrf=self.login()
        code,r=self.req('POST','/api/orders',{'buyer':'Demo Shortage','city':'Fictional City, CA','items':[{'sku':'GT-403','qty':2}]})
        self.assertEqual(code,201,r);self.assertEqual(r['order']['status'],'hold');oid=r['order']['id']
        code,r=self.req('POST',f'/api/admin/orders/{oid}/label',{},csrf);self.assertEqual(code,422)
        code,r=self.req('GET','/api/admin/dashboard');self.assertTrue(any(a['order_id']==oid for a in r['alerts']))
        code,r=self.req('PUT','/api/admin/products/GT-403',{'sku':'GT-403','stock':'5'},csrf);self.assertEqual(code,200,r)
        code,r=self.req('POST',f'/api/admin/orders/{oid}/recheck',{},csrf);self.assertEqual(code,200,r);self.assertEqual(r['order']['status'],'ready')
        code,r=self.req('POST',f'/api/admin/orders/{oid}/label',{},csrf);self.assertEqual(code,200,r)
    def test_11_website_routes_seo(self):
        code,r=self.req('GET','/shop');self.assertEqual(code,200);self.assertIn('CommerceDesk',r)
        code,r=self.req('GET','/sitemap.xml');self.assertEqual(code,200);self.assertIn('/product/',r)
        code,r=self.req('GET','/robots.txt');self.assertEqual(code,200);self.assertIn('Disallow: /admin',r)

    def test_12_draft_hidden_until_published(self):
        csrf=self.login()
        image=base64.b64encode((ROOT/'samples/images/GS-305.png').read_bytes()).decode()
        p={'sku':'GS-305','name':'Draft seal','category':'Seals & Gaskets','description':'Unpublished draft product.','price':'8.99','stock':'6','status':'draft','image':{'filename':'GS-305.png','content_b64':image}}
        # GS-305 was already created in test_08; use a unique SKU and matching filename created for it.
        p['sku']='GS-306';p['image']['filename']='GS-306.png'
        code,r=self.req('POST','/api/admin/products',p,csrf);self.assertEqual(code,201,r)
        code,r=self.req('GET','/api/product/'+r['product']['slug']);self.assertEqual(code,404)
        code,r=self.req('POST','/api/admin/logout',{});self.assertEqual(code,200)
        code,r=self.req('GET','/api/images/GS-306');self.assertEqual(code,404)
        csrf=self.login()
        code,r=self.req('PUT','/api/admin/products/GS-306',{'sku':'GS-306','status':'published'},csrf);self.assertEqual(code,200,r)
        code,r=self.req('GET','/api/product/'+r['product']['slug']);self.assertEqual(code,200)
    def test_13_image_mismatch_rejected(self):
        csrf=self.login()
        image=base64.b64encode((ROOT/'samples/images/GH-205.png').read_bytes()).decode()
        p={'sku':'AB-888','name':'Bad image','category':'Glass Door Hardware','description':'Should not publish.','price':'10.00','stock':'1','status':'published','image':{'filename':'AB-999.png','content_b64':image}}
        code,r=self.req('POST','/api/admin/products',p,csrf);self.assertEqual(code,422)
        self.assertIn('image',r['errors'])
    def test_14_order_all_or_nothing(self):
        csrf=self.login()
        code,before=self.req('GET','/api/admin/dashboard')
        original=next(p['stock'] for p in before['products'] if p['sku']=='GH-102')
        code,r=self.req('POST','/api/orders',{'buyer':'Demo Shortage','city':'Fictional City, CA','items':[{'sku':'GH-102','qty':1},{'sku':'GT-403','qty':20}]})
        self.assertEqual(code,201,r);self.assertEqual(r['order']['status'],'hold')
        code,after=self.req('GET','/api/admin/dashboard')
        self.assertEqual(next(p['stock'] for p in after['products'] if p['sku']=='GH-102'),original)
    def test_15_reset_restore(self):
        csrf=self.login()
        code,r=self.req('POST','/api/admin/reset',{'confirmation':'WRONG'},csrf);self.assertEqual(code,422)
        code,r=self.req('POST','/api/admin/reset',{'confirmation':'RESET DEMO'},csrf);self.assertEqual(code,200,r)
        code,r=self.req('GET','/api/admin/dashboard');self.assertEqual(code,200)
        self.assertEqual(len(r['products']),10);self.assertEqual(len(r['orders']),2)

if __name__=='__main__':unittest.main()
