import base64, io, sys, unittest, zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from batch_import import parse_import_source, _google_csv_url

class SpreadsheetImportTests(unittest.TestCase):
    def workbook(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Products" sheetId="1" r:id="rId1"/></sheets></workbook>''')
            z.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>''')
            z.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>sku</t></is></c><c r="B1" t="inlineStr"><is><t>name</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>GL-1001</t></is></c><c r="B2" t="inlineStr"><is><t>Tempered Panel</t></is></c></row></sheetData></worksheet>''')
        return out.getvalue()
    def test_xlsx_first_sheet_is_normalized(self):
        raw=self.workbook()
        rows=parse_import_source({'file_name':'products.xlsx','file_b64':base64.b64encode(raw).decode()})
        self.assertEqual(rows,[{'sku':'GL-1001','name':'Tempered Panel'}])
    def test_csv_is_normalized(self):
        rows=parse_import_source({'file_name':'products.csv','csv_text':'sku,name\nGL-1001,Tempered Panel\n'})
        self.assertEqual(rows[0]['sku'],'GL-1001')
    def test_header_aliases_normalize_to_product_schema(self):
        rows=parse_import_source({'file_name':'products.csv','csv_text':'SKU,Product Name,Unit Price,Quantity,SLU,Image Path\\nGL-1001,Panel,19.95,7,782341,catalog/782341.png\\n'})
        self.assertEqual(rows[0]['name'],'Panel');self.assertEqual(rows[0]['price'],'19.95');self.assertEqual(rows[0]['stock'],'7');self.assertEqual(rows[0]['slu_number'],'782341')
    def test_google_sheet_fragment_gid(self):
        self.assertIn('gid=42',_google_csv_url('https://docs.google.com/spreadsheets/d/abc123/edit#gid=42'))
    def test_google_sheet_host_validation(self):
        with self.assertRaises(ValueError):_google_csv_url('https://evil.example/spreadsheets/d/not-a-sheet')
    def test_missing_sku_rejected(self):
        with self.assertRaises(ValueError):parse_import_source({'file_name':'products.csv','csv_text':'name,price\nWidget,2.00\n'})

if __name__=='__main__':unittest.main()
