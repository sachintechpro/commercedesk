"""Spreadsheet normalization for CommerceDesk bulk catalog imports.
Supports CSV/TSV, XLSX, legacy XLS (xlrd), and exportable Google Sheets CSV URLs.
"""
import csv, io, re, zipfile
from pathlib import PurePosixPath
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

MAX_BYTES = 8_000_000
MAX_ROWS = 500
NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'p':'http://schemas.openxmlformats.org/package/2006/relationships'}

def _clean_rows(rows):
    if not rows: raise ValueError('The selected spreadsheet contains no rows.')
    headers=[str(x or '').strip().lower().replace(' ','_') for x in rows[0]]
    if 'sku' not in headers: raise ValueError('The spreadsheet must include a SKU column.')
    if len(headers)!=len(set(headers)): raise ValueError('The spreadsheet contains duplicate column headings.')
    result=[]
    for idx,values in enumerate(rows[1:],2):
        if not any(str(v or '').strip() for v in values): continue
        if len(result)>=MAX_ROWS: raise ValueError('Maximum 500 product rows per batch.')
        row={headers[i]:str(values[i] if i<len(values) else '').strip() for i in range(len(headers))}
        result.append(row)
    if not result: raise ValueError('The spreadsheet contains no product rows.')
    return result

def _xlsx(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall('m:si',NS):
                shared.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
        workbook=ET.fromstring(z.read('xl/workbook.xml'))
        sheet=workbook.find('m:sheets/m:sheet',NS)
        if sheet is None: raise ValueError('Workbook has no worksheets.')
        rel_id=sheet.attrib.get('{'+NS['r']+'}id')
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target=next((x.attrib['Target'] for x in rels if x.attrib.get('Id')==rel_id),None)
        if not target: raise ValueError('Could not locate the first worksheet.')
        path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        path=str(PurePosixPath(path))
        root=ET.fromstring(z.read(path))
        rows=[]
        for row in root.findall('.//m:sheetData/m:row',NS):
            vals=[]
            for cell in row.findall('m:c',NS):
                ref=cell.attrib.get('r','A1')
                col=re.match(r'[A-Z]+',ref).group(0)
                n=0
                for ch in col: n=n*26+ord(ch)-64
                while len(vals)<n-1: vals.append('')
                v=cell.find('m:v',NS); value='' if v is None else (v.text or '')
                if cell.attrib.get('t')=='s' and value: value=shared[int(value)]
                elif cell.attrib.get('t')=='inlineStr':
                    value=''.join(t.text or '' for t in cell.findall('.//m:t',NS))
                vals.append(value)
            rows.append(vals)
        return rows

def _google_csv_url(url):
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in ('docs.google.com','drive.google.com'):
        raise ValueError('Use a Google Sheets HTTPS URL or upload a spreadsheet file.')
    match=re.search(r'/spreadsheets/d/([A-Za-z0-9_-]+)',parsed.path)
    if not match: raise ValueError('Google Sheets URL is not recognized.')
    gid=parse_qs(parsed.query).get('gid',['0'])[0]
    return 'https://docs.google.com/spreadsheets/d/'+match.group(1)+'/export?'+urlencode({'format':'csv','gid':gid})

def parse_import_source(payload):
    if payload.get('sheet_url'):
        url=_google_csv_url(str(payload['sheet_url']).strip())
        req=Request(url,headers={'User-Agent':'CommerceDesk-Demo/1.0'})
        with urlopen(req,timeout=12) as response: data=response.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES: raise ValueError('Google Sheet export exceeds 8 MB.')
        text=data.decode('utf-8-sig')
        return _clean_rows(list(csv.reader(io.StringIO(text,newline=''))))
    if payload.get('csv_text') is not None:
        text=str(payload['csv_text'])
        if len(text.encode('utf-8'))>MAX_BYTES: raise ValueError('Spreadsheet exceeds 8 MB.')
        return _clean_rows(list(csv.reader(io.StringIO(text.lstrip('\ufeff'),newline=''),delimiter='\t' if payload.get('file_name','').lower().endswith('.tsv') else ',')))
    raw=payload.get('file_b64')
    if not raw: raise ValueError('Choose a CSV, TSV, XLSX or XLS file, or provide a Google Sheets URL.')
    import base64, binascii
    try: data=base64.b64decode(raw,validate=True)
    except (binascii.Error,ValueError): raise ValueError('Spreadsheet file data is invalid.')
    if not data or len(data)>MAX_BYTES: raise ValueError('Spreadsheet must be between 1 byte and 8 MB.')
    name=str(payload.get('file_name','')).lower()
    if name.endswith('.xlsx'):
        rows=_xlsx(data)
    elif name.endswith('.xls'):
        try:
            import xlrd
            book=xlrd.open_workbook(file_contents=data)
            sheet=book.sheet_by_index(0)
            rows=[[sheet.cell_value(r,c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
        except ImportError: raise ValueError('Legacy .xls support is unavailable. Save as .xlsx or CSV and retry.')
        except Exception as exc: raise ValueError('Could not read this .xls workbook: '+str(exc)[:160])
    elif name.endswith(('.csv','.tsv')):
        rows=list(csv.reader(io.StringIO(data.decode('utf-8-sig'),newline=''),delimiter='\t' if name.endswith('.tsv') else ','))
    else: raise ValueError('Supported formats: CSV, TSV, XLSX and XLS.')
    return _clean_rows(rows)
