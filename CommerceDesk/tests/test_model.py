import base64, pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from model import InputError, money_to_cents, parse_stock, sku_value, slug_for, verify_image, product_fields, read_csv, order_decision
ROOT=pathlib.Path(__file__).resolve().parents[1]

class ModelRulesTests(unittest.TestCase):
    def test_price_valid(self):
        self.assertEqual(money_to_cents('13.90'),1390)
        self.assertEqual(money_to_cents('0.01'),1)
    def test_price_invalid(self):
        for value in ['-1','0','1.234','$12','12.2.3','abc','',None,False]:
            with self.subTest(value=value),self.assertRaises(ValueError):money_to_cents(value)
    def test_stock(self):
        self.assertEqual(parse_stock('0'),0)
        for value in ['-1','1.2','1e6','',None,True]:
            with self.subTest(value=value),self.assertRaises(ValueError):parse_stock(value)
    def test_new_product_requires_image(self):
        p,e=product_fields({'sku':'AB-123','name':'X','category':'Glass Door Hardware','description':'Test','price':'11.50','stock':'3'})
        self.assertIn('image',e)
    def test_missing_fields(self):
        p,e=product_fields({'sku':'bad'});self.assertTrue(all(x in e for x in ['name','category','description','price','stock','image']))
    def test_unexpected_category(self):
        p,e=product_fields({'sku':'AB-123','name':'X','category':'Foo','description':'Test','price':'11.50','stock':'3'},image_present=True)
        self.assertIn('category',e)
    def test_image_sku_match(self):
        data=base64.b64encode((ROOT/'samples/images/GH-101.png').read_bytes()).decode()
        mime, blob=verify_image('GH-101.png',data,'GH-101');self.assertEqual(mime,'image/png');self.assertTrue(blob)
        with self.assertRaises(InputError):verify_image('GH-102.png',data,'GH-101')
    def test_corrupt_image(self):
        with self.assertRaises(InputError):verify_image('GH-101.png',base64.b64encode(b'not an image').decode(),'GH-101')
    def test_csv_parses_quoted_comma(self):
        rows=read_csv('sku,description,price\nGH-100,"Hinge, polished",12.50\n')
        self.assertEqual(rows[0]['description'],'Hinge, polished')
    def test_csv_missing_sku(self):
        with self.assertRaises(InputError):read_csv('name,price\nName,12.00\n')
    def test_csv_rejects_extra_columns(self):
        with self.assertRaises(InputError):read_csv('sku,name\nGH-100,Foo,extra\n')
    def test_order_ready(self):
        d=order_decision([{'sku':'GH-101','qty':2}],{'GH-101':3});self.assertTrue(d['ready'])
    def test_order_shortage(self):
        d=order_decision([{'sku':'GH-101','qty':5}],{'GH-101':2});self.assertFalse(d['ready']);self.assertEqual(d['shortages']['GH-101'],3)
    def test_order_no_partial_reservation(self):
        d=order_decision([{'sku':'GH-101','qty':1},{'sku':'GH-102','qty':4}],{'GH-101':5,'GH-102':1});self.assertFalse(d['ready'])
    def test_order_rejects_unknown_sku(self):
        with self.assertRaises(InputError):order_decision([{'sku':'GH-999','qty':1}],{'GH-101':3})
    def test_order_rejects_duplicate_qty_over_limit(self):
        with self.assertRaises(InputError):order_decision([{'sku':'GH-101','qty':60},{'sku':'GH-101','qty':60}],{'GH-101':300})
    def test_update_preserves_fields(self):
        existing={'sku':'GH-101','name':'Old','description':'Existing','category':'Glass Door Hardware','price_cents':2000,'stock':3,'status':'published','featured':True}
        p,e=product_fields({'sku':'GH-101','price':'25.00','featured':''},existing,True)
        self.assertFalse(e);self.assertEqual(p['name'],'Old');self.assertEqual(p['price_cents'],2500);self.assertTrue(p['featured'])

if __name__=='__main__':unittest.main()
