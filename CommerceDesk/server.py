"""CommerceDesk storefront + admin demo, with standard-library SQLite backend."""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import parse_qs, urlparse, quote
from xml.sax.saxutils import escape as xml_escape

from model import CATEGORIES, InputError, order_decision, product_fields, read_csv, sku_value, verify_image

ROOT=Path(__file__).resolve().parent
DB_PATH=Path(os.environ.get('COMMERCE_DB_PATH',str(ROOT/'data'/'commerce.sqlite3')))
IS_RENDER=bool(os.environ.get('RENDER'))
ADMIN_USERNAME=os.environ.get('ADMIN_USERNAME','admin@commercedesk.demo')
ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    if IS_RENDER:
        raise RuntimeError('Set ADMIN_PASSWORD in Render environment before launching CommerceDesk.')
    ADMIN_PASSWORD='DemoAdmin!2026'
SECRET=(os.environ.get('SESSION_SECRET') or secrets.token_hex(32)).encode()
MAX_BODY=12_000_000

SAMPLE_PRODUCTS=[
 ('GH-101','Stainless Steel Glass Door Hinge','Glass Door Hardware','Brushed stainless-steel hinge for frameless glass doors; includes matching mounting hardware.',2495,20,1),
 ('GH-102','Square Glass Door Pull Handle','Glass Door Hardware','Modern polished stainless-steel pull handle for frameless glass panels.',3250,14,1),
 ('GS-201','Clear Shower Door Bottom Seal','Seals & Gaskets','Flexible clear PVC sweep designed for frameless shower-door bottom edges.',1275,23,1),
 ('GC-301','Glass Mounting Clamp — Chrome','Glass Door Hardware','Square clamp for glass panel installations with corrosion-resistant finish.',1899,8,1),
 ('GT-401','Aluminum U-Channel — Black','Glazing Supplies','Matte black aluminum channel for supporting fixed glass panels.',2995,18,1),
 ('GA-501','Glazing Installation Gasket','Seals & Gaskets','Compressible glazing gasket for glass panels and framing applications.',950,31,0),
 ('GT-402','Professional Glass Suction Lifter','Installation Tools','Handheld vacuum suction lifter designed for smooth glass panels.',4590,5,1),
 ('GH-103','Round Glass Door Knob','Glass Door Hardware','Low-profile glass door knob with a brushed metal finish.',1595,10,0),
 ('GS-202','Transparent Edge Protection Strip','Seals & Gaskets','Clear push-on edge strip for decorative glazing and partition panels.',1095,12,0),
 ('GT-403','Precision Glass Measuring Square','Installation Tools','Durable layout square for glass installation measurements.',2275,0,0),
]


def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def connect():
    conn=sqlite3.connect(str(DB_PATH),timeout=15,isolation_level=None)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

@contextmanager
def db():
    connection=connect()
    try:
        yield connection
    finally:
        connection.close()

def insert_audit(conn, action, detail):
    conn.execute('INSERT INTO audit(time,action,detail) VALUES(?,?,?)',(now(),action,str(detail)[:400]))

def init_database():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=connect()
    conn.execute('PRAGMA journal_mode=WAL')
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS products(sku TEXT PRIMARY KEY,slug TEXT UNIQUE NOT NULL,name TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,price_cents INTEGER NOT NULL CHECK(price_cents>0),stock INTEGER NOT NULL CHECK(stock>=0),status TEXT NOT NULL CHECK(status IN ('draft','published')),featured INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS images(sku TEXT PRIMARY KEY REFERENCES products(sku) ON DELETE CASCADE,mime TEXT NOT NULL,data BLOB NOT NULL);
      CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,buyer TEXT NOT NULL,city TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,label_ref TEXT,label_verified INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS order_lines(order_id TEXT NOT NULL REFERENCES orders(id),sku TEXT NOT NULL,qty INTEGER NOT NULL,unit_cents INTEGER NOT NULL,PRIMARY KEY(order_id,sku));
      CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT,sku TEXT,message TEXT NOT NULL,created_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,time TEXT,action TEXT,detail TEXT);
    ''')
    if conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]==0:
        conn.execute('BEGIN IMMEDIATE')
        try:
            from model import slug_for
            for sku,name,cat,desc,price,stock,featured in SAMPLE_PRODUCTS:
                conn.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?)',(sku,slug_for(name,sku),name,cat,desc,price,stock,'published',featured,now()))
                img=ROOT/'samples'/'images'/f'{sku}.png'
                if img.exists():
                    conn.execute('INSERT INTO images VALUES(?,?,?)',(sku,'image/png',img.read_bytes()))
            # Seed a ready order (reserve 2 hinges) and one held order; no real customer data.
            conn.execute('UPDATE products SET stock=stock-2 WHERE sku="GH-101"')
            conn.execute('INSERT INTO orders(id,buyer,city,status,created_at,label_ref) VALUES(?,?,?,?,?,NULL)',('DEMO-1001','Taylor Sample','Fictional City, CA','ready',now()))
            conn.execute('INSERT INTO order_lines VALUES(?,?,?,?)',('DEMO-1001','GH-101',2,2495))
            conn.execute('INSERT INTO orders(id,buyer,city,status,created_at,label_ref) VALUES(?,?,?,?,?,NULL)',('DEMO-1002','Jordan Sample','Fictional City, CA','hold',now()))
            conn.execute('INSERT INTO order_lines VALUES(?,?,?,?)',('DEMO-1002','GT-403',3,2275))
            conn.execute('INSERT INTO alerts(order_id,sku,message,created_at) VALUES(?,?,?,?)',('DEMO-1002','GT-403','Purchase review needed: order DEMO-1002 requires 3 units; available to promise 0. Shipping is blocked.',now()))
            insert_audit(conn,'DEMO_INITIALIZED','Sample catalog and fictional orders created')
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    conn.close()


def p_json(row):
    d=dict(row)
    d['featured']=bool(d.get('featured',0))
    d['has_image']=True
    d['image_url']='/api/images/'+quote(d['sku'])
    d['price']=f"{d['price_cents']/100:.2f}"
    return d

def get_products(conn,admin=False):
    rows=conn.execute('SELECT * FROM products '+('' if admin else "WHERE status='published' ")+'ORDER BY featured DESC,name ASC').fetchall()
    return [p_json(r) for r in rows]

def order_json(conn,row):
    data=dict(row)
    data['label_verified']=bool(data.get('label_verified'))
    lines=conn.execute('SELECT * FROM order_lines WHERE order_id=?',(row['id'],)).fetchall()
    data['items']=[dict(x) for x in lines]
    data['total_cents']=sum(x['qty']*x['unit_cents'] for x in lines)
    data['shortages']={}
    if data['status']=='hold':
        for x in lines:
            stock=conn.execute('SELECT stock FROM products WHERE sku=?',(x['sku'],)).fetchone()
            data['shortages'][x['sku']]=max(0,x['qty']-(stock['stock'] if stock else 0))
    return data

def audit_new_order(conn, payload):
    items=payload.get('items')
    if not isinstance(items,list) or not (1<=len(items)<=30):
        raise InputError({'items':'Cart must contain 1–30 product lines.'})
    buyer=str(payload.get('buyer','')).strip()
    city=str(payload.get('city','')).strip()
    if not (2<=len(buyer)<=80) or not (2<=len(city)<=80):
        raise InputError({'buyer':'Enter a demo name and fictional shipping location.'})
    conn.execute('BEGIN IMMEDIATE')
    try:
        rows=conn.execute("SELECT sku,stock,price_cents FROM products WHERE status='published'").fetchall()
        products={r['sku']:r for r in rows}
        decision=order_decision(items,{sku:r['stock'] for sku,r in products.items()})
        order_id='DEMO-'+secrets.token_hex(4).upper()
        status='ready' if decision['ready'] else 'hold'
        conn.execute('INSERT INTO orders(id,buyer,city,status,created_at,label_ref) VALUES(?,?,?,?,?,NULL)',(order_id,buyer,city,status,now()))
        for sku,qty in decision['requested'].items():
            conn.execute('INSERT INTO order_lines VALUES(?,?,?,?)',(order_id,sku,qty,products[sku]['price_cents']))
            if decision['ready']:
                conn.execute('UPDATE products SET stock=stock-? WHERE sku=?',(qty,sku))
        for sku,shortage in decision['shortages'].items():
            conn.execute('INSERT INTO alerts(order_id,sku,message,created_at) VALUES(?,?,?,?)',(order_id,sku,f'Inventory shortage: {sku} needs {shortage} additional unit(s). Purchasing review required; do not generate label.',now()))
        insert_audit(conn,'ORDER_RECEIVED',f'{order_id}: {status}')
        result=order_json(conn,conn.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone())
        conn.execute('COMMIT')
        return result
    except Exception:
        conn.execute('ROLLBACK')
        raise


def build_import_review(conn,payload):
    rows=read_csv(payload.get('csv_text'))
    images=payload.get('images') or []
    if not isinstance(images,list) or len(images)>75:
        raise InputError({'images':'Select no more than 75 images.'})
    imap={}; image_errors=[]
    for f in images:
        if not isinstance(f,dict):
            raise InputError({'images':'Invalid image upload format.'})
        filename=str(f.get('filename','')).strip()
        key=filename.lower()
        if key in imap:
            image_errors.append(f'Duplicate image file: {filename}')
        imap[key]=f
    result=[]; seen=set()
    for i,row in enumerate(rows,2):
        sku=sku_value(row.get('sku'))
        action=(row.get('action') or 'create').lower()
        errors={}
        if sku in seen:
            errors['sku']='SKU appears more than once in this CSV.'
        seen.add(sku)
        if action not in ('create','update'):
            errors['action']='Action must be create or update.'
        existing_row=conn.execute('SELECT * FROM products WHERE sku=?',(sku,)).fetchone()
        existing=dict(existing_row) if existing_row else None
        if action=='create' and existing:
            errors['sku']='SKU already exists. Use action=update to modify it.'
        if action=='update' and not existing:
            errors['sku']='SKU not found. Use action=create for new products.'
        filename=(row.get('image_filename') or (sku+'.png' if action=='create' else '')).strip()
        image=imap.get(filename.lower()) if filename else None
        if filename and not image:
            errors['image']=f'Missing matching image file: {filename}'
        if image:
            try: verify_image(filename,image.get('content_b64'),sku)
            except InputError as exc:errors.update(exc.errors)
        if action=='create' and not image:
            errors['image']=errors.get('image','New products require a SKU-matched image.')
        merged, field_errors=product_fields(row,existing if action=='update' else None,bool(image or (existing if action=='update' else False)))
        errors.update(field_errors)
        result.append({'row':i,'sku':sku,'name':merged.get('name',''),'action':action,'errors':errors,'record':merged,'image_filename':filename or None})
    overall=not image_errors and all(not r['errors'] for r in result)
    return {'ready':overall,'rows':result,'image_errors':image_errors,'total':len(result),'valid':sum(not bool(r['errors']) for r in result),'invalid':sum(bool(r['errors']) for r in result)},imap


def save_product(conn,data,sku_in_path=None):
    sku=sku_value(data.get('sku') or sku_in_path)
    if sku_in_path and sku!=sku_value(sku_in_path):
        raise InputError({'sku':'SKU cannot be changed when editing a product.'})
    existing_row=conn.execute('SELECT * FROM products WHERE sku=?',(sku,)).fetchone()
    existing=dict(existing_row) if existing_row else None
    if sku_in_path and not existing:
        raise InputError({'sku':'Product does not exist.'})
    if not sku_in_path and existing:
        raise InputError({'sku':'This SKU already exists. Open Edit Product instead.'})
    image=data.get('image')
    verified_image=None
    if image:
        verified_image=verify_image(image.get('filename'),image.get('content_b64'),sku)
    merged,errs=product_fields(data,existing,bool(image or existing))
    if errs:raise InputError(errs)
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('''INSERT INTO products(sku,slug,name,category,description,price_cents,stock,status,featured,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(sku) DO UPDATE SET slug=excluded.slug,name=excluded.name,category=excluded.category,description=excluded.description,price_cents=excluded.price_cents,stock=excluded.stock,status=excluded.status,featured=excluded.featured,updated_at=excluded.updated_at''',
          (sku,merged['slug'],merged['name'],merged['category'],merged['description'],merged['price_cents'],merged['stock'],merged['status'],int(merged['featured']),now()))
        if verified_image:
            conn.execute('INSERT INTO images(sku,mime,data) VALUES(?,?,?) ON CONFLICT(sku) DO UPDATE SET mime=excluded.mime,data=excluded.data',(sku,*verified_image))
        insert_audit(conn,'PRODUCT_'+('UPDATED' if existing else 'CREATED'),f'{sku} · {merged["status"]} · ${merged["price_cents"]/100:.2f}')
        conn.execute('COMMIT')
        return p_json(conn.execute('SELECT * FROM products WHERE sku=?',(sku,)).fetchone())
    except Exception:
        conn.execute('ROLLBACK')
        raise


def import_commit(conn,payload):
    # Acquire SQLite's write reservation before validating existence: prevents a
    # concurrent create/update from invalidating the reviewed actions.
    conn.execute('BEGIN IMMEDIATE')
    try:
        review,imap=build_import_review(conn,payload)
        if not review['ready']:
            raise InputError({'import':'Review contains errors. Nothing was published.'})
        for row in review['rows']:
            m=row['record']
            conn.execute('''INSERT INTO products(sku,slug,name,category,description,price_cents,stock,status,featured,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(sku) DO UPDATE SET slug=excluded.slug,name=excluded.name,category=excluded.category,description=excluded.description,price_cents=excluded.price_cents,stock=excluded.stock,status=excluded.status,featured=excluded.featured,updated_at=excluded.updated_at''',
              (m['sku'],m['slug'],m['name'],m['category'],m['description'],m['price_cents'],m['stock'],m['status'],int(m['featured']),now()))
            if row['image_filename']:
                im=imap[row['image_filename'].lower()]
                mime,data=verify_image(im['filename'],im['content_b64'],m['sku'])
                conn.execute('INSERT INTO images VALUES(?,?,?) ON CONFLICT(sku) DO UPDATE SET mime=excluded.mime,data=excluded.data',(m['sku'],mime,data))
        insert_audit(conn,'CSV_IMPORT',f'{len(review["rows"])} product(s) created/updated')
        conn.execute('COMMIT')
        return {'imported':len(review['rows']),'created':sum(x['action']=='create' for x in review['rows']),'updated':sum(x['action']=='update' for x in review['rows'])}
    except Exception:
        conn.execute('ROLLBACK')
        raise


def session_token():
    stamp=str(int(time.time()))
    nonce=secrets.token_urlsafe(10)
    raw=(stamp+':'+nonce).encode()
    sig=hmac.new(SECRET,raw,hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(raw+b':'+sig.encode()).decode().rstrip('=')

def session_valid(cookie):
    try:
        text=base64.urlsafe_b64decode(cookie+'='*((-len(cookie))%4)).decode()
        stamp,nonce,sig=text.split(':')
        raw=f'{stamp}:{nonce}'.encode()
        if not hmac.compare_digest(sig,hmac.new(SECRET,raw,hashlib.sha256).hexdigest()):return False
        age=time.time()-int(stamp)
        return 0<=age<=28800
    except (TypeError,ValueError,UnicodeDecodeError):return False

def csrf_for(token):
    return hmac.new(SECRET,('csrf:'+token).encode(),hashlib.sha256).hexdigest()

class Handler(BaseHTTPRequestHandler):
    server_version='CommerceDeskDemo/2.0'
    def log_message(self,fmt,*args):
        print(f'{self.address_string()} {fmt % args}',flush=True)
    def headers_basic(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' https://api.github.com; base-uri 'none'; frame-ancestors 'none'; object-src 'none'")
    def send_data(self,code,blob,mime='application/json; charset=utf-8',headers=None):
        if isinstance(blob,(dict,list)):blob=json.dumps(blob,ensure_ascii=False).encode()
        if isinstance(blob,str):blob=blob.encode()
        self.send_response(code)
        self.headers_basic()
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(blob)))
        self.send_header('Cache-Control','no-store')
        for key,val in headers or []: self.send_header(key,val)
        self.end_headers()
        try:self.wfile.write(blob)
        except (BrokenPipeError,ConnectionResetError):pass
    def out(self,code,**data):self.send_data(code,data)
    def auth_cookie(self):
        for chunk in self.headers.get('Cookie','').split(';'):
            part=chunk.strip()
            if part.startswith('cd_session='):
                token=part.split('=',1)[1]
                if session_valid(token):return token
        return None
    def protected(self,write=False):
        token=self.auth_cookie()
        if not token:
            self.out(401,error='Admin login required.')
            return False
        if write and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),csrf_for(token)):
            self.out(403,error='Session verification failed. Refresh the admin page and sign in again.')
            return False
        return True
    def get_body(self):
        size=int(self.headers.get('Content-Length','0'))
        if size<=0 or size>MAX_BODY:
            raise InputError({'request':'Request is missing or larger than 12 MB.'})
        try:return json.loads(self.rfile.read(size))
        except (json.JSONDecodeError,UnicodeDecodeError):raise InputError({'request':'Invalid JSON request.'})
    def api(self,method,path,data):
        if method=='GET' and path=='/api/catalog':
            with db() as conn:
                rows=get_products(conn)
            q=(parse_qs(urlparse(self.path).query).get('q',[''])[0] or '').lower()[:100]
            cat=parse_qs(urlparse(self.path).query).get('category',[''])[0]
            if cat:rows=[x for x in rows if x['category']==cat]
            if q:rows=[x for x in rows if q in (x['name']+' '+x['sku']+' '+x['category']+' '+x['description']).lower()]
            return self.out(200,categories=CATEGORIES,products=rows)
        if method=='GET' and path.startswith('/api/images/'):
            sku=sku_value(path.split('/')[-1])
            with db() as conn:
                row=conn.execute('SELECT images.mime,images.data,products.status FROM images JOIN products USING(sku) WHERE sku=?',(sku,)).fetchone()
            if not row or (row['status']!='published' and not self.auth_cookie()):return self.out(404,error='Image not available')
            return self.send_data(200,row['data'],row['mime'])
        if method=='GET' and path.startswith('/api/product/'):
            slug=path.split('/')[-1]
            with db() as conn:
                r=conn.execute("SELECT * FROM products WHERE slug=? AND status='published'",(slug,)).fetchone()
                if not r:return self.out(404,error='Product not available')
                related=conn.execute("SELECT * FROM products WHERE category=? AND sku!=? AND status='published' LIMIT 5",(r['category'],r['sku'])).fetchall()
            return self.out(200,product=p_json(r),related=[p_json(x) for x in related])
        if method=='POST' and path=='/api/orders':
            with db() as conn:return self.out(201,order=audit_new_order(conn,data))
        if method=='POST' and path=='/api/admin/login':
            if not (hmac.compare_digest(str(data.get('username','')).strip().lower(),ADMIN_USERNAME.lower()) and hmac.compare_digest(str(data.get('password','')),ADMIN_PASSWORD)):
                return self.out(401,error='Incorrect admin username or password.')
            token=session_token()
            cookie=f'cd_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
            if self.headers.get('X-Forwarded-Proto','').lower()=='https':cookie+='; Secure'
            return self.send_data(200,{'authenticated':True,'csrf':csrf_for(token)},headers=[('Set-Cookie',cookie)])
        if method=='POST' and path=='/api/admin/logout':
            return self.send_data(200,{'ok':True},headers=[('Set-Cookie','cd_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict')])
        if path.startswith('/api/admin/'):
            if not self.protected(method!='GET'):return
            if method=='GET' and path=='/api/admin/session':return self.out(200,authenticated=True,csrf=csrf_for(self.auth_cookie()))
            with db() as conn:
                if method=='GET' and path=='/api/admin/dashboard':
                    allrows=get_products(conn,True)
                    orders=[order_json(conn,x) for x in conn.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 100')]
                    alerts=[dict(x) for x in conn.execute('SELECT * FROM alerts ORDER BY id DESC LIMIT 35')]
                    audits=[dict(x) for x in conn.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 25')]
                    return self.out(200,products=allrows,orders=orders,alerts=alerts,audit=audits,categories=CATEGORIES)
                if method=='POST' and path=='/api/admin/products':
                    return self.out(201,product=save_product(conn,data))
                if method=='PUT' and path.startswith('/api/admin/products/'):
                    return self.out(200,product=save_product(conn,data,path.split('/')[-1]))
                if method=='POST' and path=='/api/admin/import/preview':
                    review,_=build_import_review(conn,data)
                    return self.out(200,review=review)
                if method=='POST' and path=='/api/admin/import':
                    return self.out(200,result=import_commit(conn,data))
                if method=='POST' and re.fullmatch(r'/api/admin/orders/[A-Z0-9-]+/(?:label|verify|dispatch|recheck)',path):
                    parts=path.split('/');oid,action=parts[4],parts[5]
                    conn.execute('BEGIN IMMEDIATE')
                    try:
                        row=conn.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
                        if not row:raise InputError({'order':'Order not found.'})
                        if action=='label':
                            if row['status']!='ready':raise InputError({'order':'Label blocked: order must have fully reserved stock and be ready for fulfillment.'})
                            label='SAMPLE-'+oid
                            conn.execute('UPDATE orders SET status=?,label_ref=?,label_verified=0 WHERE id=?',('label_created',label,oid))
                            insert_audit(conn,'DEMO_LABEL',f'{oid} label prepared (NOT VALID FOR SHIPMENT)')
                        elif action=='verify':
                            if row['status']!='label_created':raise InputError({'label_ref':'Generate a sample label before verifying it.'})
                            supplied=str(data.get('label_ref') or '').strip().upper()
                            if not supplied or supplied!=row['label_ref']:
                                raise InputError({'label_ref':'Label reference does not match this order. Handoff is blocked.'})
                            conn.execute('UPDATE orders SET label_verified=1 WHERE id=?',(oid,))
                            insert_audit(conn,'LABEL_VERIFIED',f'{oid}: label reference matched')
                        elif action=='dispatch':
                            if row['status']!='label_created':raise InputError({'order':'Generate a sample label before marking the order dispatched.'})
                            if not row['label_verified']:raise InputError({'order':'Verify the sample label matches this order before warehouse handoff.'})
                            conn.execute('UPDATE orders SET status=? WHERE id=?',('shipped',oid))
                            insert_audit(conn,'DEMO_DISPATCH',oid)
                        else:
                            if row['status']!='hold':raise InputError({'order':'Only on-hold orders can be rechecked.'})
                            lines=[dict(x) for x in conn.execute('SELECT * FROM order_lines WHERE order_id=?',(oid,))]
                            available={x['sku']:conn.execute('SELECT stock FROM products WHERE sku=?',(x['sku'],)).fetchone()['stock'] for x in lines}
                            dec=order_decision(lines,available)
                            if not dec['ready']:
                                raise InputError({'inventory':'Still insufficient stock: '+', '.join(f'{k}: short {v}' for k,v in dec['shortages'].items())})
                            for sku,qty in dec['requested'].items():conn.execute('UPDATE products SET stock=stock-? WHERE sku=?',(qty,sku))
                            conn.execute('UPDATE orders SET status=? WHERE id=?',('ready',oid))
                            insert_audit(conn,'ORDER_RELEASED',f'{oid}: stock reserved after recheck')
                        result=order_json(conn,conn.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone())
                        conn.execute('COMMIT')
                        return self.out(200,order=result)
                    except Exception:
                        conn.execute('ROLLBACK')
                        raise
                if method=='POST' and path=='/api/admin/reset':
                    if data.get('confirmation')!='RESET DEMO':
                        raise InputError({'confirmation':'Type RESET DEMO to restore sample data.'})
                    conn.execute('PRAGMA foreign_keys=OFF')
                    for t in ['order_lines','orders','images','products','alerts','audit']:
                        conn.execute('DELETE FROM '+t)
                    conn.execute('PRAGMA foreign_keys=ON')
                    conn.close()
                    init_database()
                    return self.out(200,ok=True)
        return self.out(404,error='Endpoint not found.')
    def handle_request(self,method):
        parsed=urlparse(self.path)
        path=parsed.path.rstrip('/') or '/'
        try:
            if path.startswith('/api/'):
                data=self.get_body() if method in ('POST','PUT','PATCH') else None
                return self.api(method,path,data)
            if method!='GET':return self.out(405,error='Method not allowed.')
            if path=='/qa-bench.html':return self.send_data(200,(ROOT/'qa-bench.html').read_bytes(),'text/html; charset=utf-8')
            if path=='/health':return self.out(200,status='ok')
            if path=='/robots.txt':
                return self.send_data(200,'User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/admin\nSitemap: '+self.base_url()+'/sitemap.xml\n','text/plain; charset=utf-8')
            if path=='/sitemap.xml':
                with db() as conn:ps=conn.execute("SELECT slug FROM products WHERE status='published'").fetchall()
                u=[self.base_url()+'/',self.base_url()+'/shop']+[self.base_url()+'/product/'+quote(x['slug']) for x in ps]
                xml='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+xml_escape(x)+'</loc></url>' for x in u)+'</urlset>'
                return self.send_data(200,xml,'application/xml; charset=utf-8')
            if path.startswith('/assets/') or path.startswith('/samples/'):
                rel=path.lstrip('/')
                f=(ROOT/rel).resolve()
                if not f.is_file() or ROOT not in f.parents:return self.out(404,error='Not found.')
                ctype=mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
                return self.send_data(200,f.read_bytes(),ctype)
            # SEO-specific title, description, canonical & schema for product pages.
            title='CommerceDesk Supply | Glass & Hardware Demonstration Store'
            desc='Explore a fictional B2B glass hardware store with category browsing, product details, and simulated checkout.'
            schema=None
            canonical=self.base_url()+path
            if path.startswith('/product/'):
                slug=path.split('/')[-1]
                with db() as conn:prod=conn.execute("SELECT * FROM products WHERE slug=? AND status='published'",(slug,)).fetchone()
                if not prod:return self.send_data(404,'<h1>Product not found</h1>','text/html; charset=utf-8')
                title=prod['name']+' | CommerceDesk Supply'
                desc=prod['description'][:155]
                schema={'@context':'https://schema.org','@type':'Product','name':prod['name'],'sku':prod['sku'],'description':prod['description'],'image':self.base_url()+'/api/images/'+prod['sku'],'offers':{'@type':'Offer','priceCurrency':'USD','price':f"{prod['price_cents']/100:.2f}",'availability':'https://schema.org/InStock' if prod['stock'] else 'https://schema.org/OutOfStock','url':canonical}}
            elif path.startswith('/category/'):
                title=path.split('/')[-1].replace('-',' ').title()+' | CommerceDesk Supply'
            elif path.startswith('/admin'):
                title='Admin | CommerceDesk Supply';desc='Restricted demo storefront administration.'
            html=(ROOT/'index.html').read_text()
            html=html.replace('<!--PAGE_TITLE-->',escape(title,quote=True)).replace('<!--PAGE_DESC-->',escape(desc,quote=True)).replace('<!--CANONICAL-->',escape(canonical,quote=True))
            html=html.replace('<!--ROBOTS_META-->','<meta name="robots" content="noindex,nofollow">' if path.startswith('/admin') else ('' if os.environ.get('ALLOW_DEMO_INDEXING')=='true' else '<meta name="robots" content="noindex,follow">'))
            html=html.replace('<!--JSON_LD-->',('<script type="application/ld+json">'+json.dumps(schema).replace('<','\\u003c')+'</script>') if schema else '')
            return self.send_data(200,html,'text/html; charset=utf-8')
        except InputError as exc:
            return self.out(422,error='Validation failed.',errors=exc.errors)
        except sqlite3.IntegrityError:
            return self.out(409,error='Data conflict: a product or order may have changed. Refresh and retry.')
        except (OverflowError,ValueError,TypeError) as exc:
            return self.out(400,error='Invalid request format.')
        except Exception as exc:
            print('Request error:',repr(exc),flush=True)
            return self.out(500,error='The demo encountered an error. Refresh and try again.')
    def base_url(self):
        base=os.environ.get('PUBLIC_BASE_URL','').rstrip('/')
        if base:return base
        host=re.sub('[^A-Za-z0-9.:_-]','',self.headers.get('Host','localhost:10000'))
        return ('https' if self.headers.get('X-Forwarded-Proto')=='https' else 'http')+'://'+host
    def do_GET(self):self.handle_request('GET')
    def do_POST(self):self.handle_request('POST')
    def do_PUT(self):self.handle_request('PUT')

if __name__=='__main__':
    init_database()
    port=int(os.environ.get('PORT','10000'))
    print(f'CommerceDesk running on port {port}; DB={DB_PATH}; admin password from '+('environment' if os.environ.get('ADMIN_PASSWORD') else 'LOCAL DEMO FALLBACK'),flush=True)
    ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
