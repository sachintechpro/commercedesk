"""CommerceDesk demo business rules — standard library only."""
import base64
import binascii
import csv
from decimal import Decimal, InvalidOperation
import io
import re
import struct

CATEGORIES = ('Glass Door Hardware', 'Seals & Gaskets', 'Installation Tools', 'Glazing Supplies')
ALLOWED_STATUSES = ('draft', 'published')
SKU_RE = re.compile(r'^[A-Z0-9][A-Z0-9-]{2,23}$')
IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
MAX_IMAGE_BYTES = 2_000_000
MAX_CSV_ROWS = 60
CSV_FIELDS = ('action','sku','name','category','description','price','stock','status','featured','image_filename')

class InputError(Exception):
    def __init__(self, errors):
        super().__init__('Please correct the highlighted fields.')
        self.errors = errors


def sku_value(value):
    return str(value or '').strip().upper()


def money_to_cents(raw):
    if isinstance(raw, bool):
        raise ValueError('Enter a valid positive price.')
    value = str(raw if raw is not None else '').strip()
    if not re.fullmatch(r'\d{1,7}(?:\.\d{1,2})?', value):
        raise ValueError('Enter a positive price with no more than 2 decimal places.')
    try:
        cents = int(Decimal(value) * 100)
    except (InvalidOperation, ValueError):
        raise ValueError('Enter a valid price.')
    if cents <= 0:
        raise ValueError('Price must be greater than zero.')
    return cents


def parse_stock(raw):
    if isinstance(raw, bool) or not re.fullmatch(r'\d{1,6}', str(raw if raw is not None else '').strip()):
        raise ValueError('Stock must be a non-negative whole number (maximum 999999).')
    return int(str(raw).strip())


def slug_for(name, sku):
    # Include SKU to ensure distinct SEO URLs even for identical titles.
    return re.sub(r'[^a-z0-9]+', '-', str(name).lower()).strip('-')[:56] + '-' + sku.lower()


def verify_image(filename, data_b64, sku):
    errors = {}
    filename = str(filename or '').strip()
    if '/' in filename or '\\' in filename or '\x00' in filename:
        errors['image'] = 'Use a filename such as GH-101.png; paths are not accepted.'
        raise InputError(errors)
    dot = filename.rfind('.')
    stem, ext = filename[:dot].upper() if dot > 0 else '', filename[dot:].lower() if dot > 0 else ''
    if stem != sku or ext not in IMAGE_TYPES:
        errors['image'] = f'Image filename must match SKU {sku} (for example {sku}.png).'
        raise InputError(errors)
    try:
        data = base64.b64decode(data_b64, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise InputError({'image': 'Image data is not valid base64.'})
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise InputError({'image': 'Image must be between 1 byte and 2 MB.'})
    if ext == '.png':
        if len(data) < 45 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR' or b'IEND' not in data[-32:]:
            raise InputError({'image': 'File is not a valid PNG image.'})
        width, height = struct.unpack('>II', data[16:24])
        if not (1 <= width <= 8000 and 1 <= height <= 8000):
            raise InputError({'image': 'Image dimensions are not supported.'})
    elif ext in ('.jpeg','.jpg'):
        if not (data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9')):
            raise InputError({'image': 'File is not a valid JPEG image.'})
    else:
        if not (len(data) >= 20 and data[:4] == b'RIFF' and data[8:12] == b'WEBP' and int.from_bytes(data[4:8], 'little')+8 == len(data)):
            raise InputError({'image': 'File is not a valid WebP image.'})
    return IMAGE_TYPES[ext], data


def product_fields(raw, existing=None, image_present=False):
    """Return merged validated record and errors, supporting explicit create and partial updates."""
    errors = {}
    creating = existing is None
    sku = sku_value(raw.get('sku') or (existing or {}).get('sku'))
    if not SKU_RE.fullmatch(sku):
        errors['sku'] = 'SKU must be 3–24 characters: letters, numbers or hyphens.'
    merged = dict(existing or {})
    merged['sku'] = sku
    for field, limit in [('name',130),('description',1800),('category',100)]:
        input_value = raw.get(field)
        if input_value is not None and str(input_value).strip() != '':
            merged[field] = str(input_value).strip()
        elif creating:
            merged[field] = ''
        if not merged.get(field):
            errors[field] = f'{field.title()} is required.'
        elif len(merged[field]) > limit:
            errors[field] = f'{field.title()} exceeds {limit} characters.'
    if merged.get('category') and merged['category'] not in CATEGORIES:
        errors['category'] = 'Select one of the available categories.'
    if raw.get('price') is not None and str(raw.get('price')).strip() != '':
        try: merged['price_cents'] = money_to_cents(raw['price'])
        except ValueError as exc: errors['price'] = str(exc)
    elif creating:
        errors['price'] = 'Price is required.'
    if raw.get('stock') is not None and str(raw.get('stock')).strip() != '':
        try: merged['stock'] = parse_stock(raw['stock'])
        except ValueError as exc: errors['stock'] = str(exc)
    elif creating:
        errors['stock'] = 'Stock is required.'
    status = str(raw.get('status') or (existing or {}).get('status') or 'draft').lower()
    if status not in ALLOWED_STATUSES:
        errors['status'] = 'Choose Draft or Published.'
    merged['status'] = status
    featured = raw.get('featured', (existing or {}).get('featured', False))
    if featured is None or str(featured).strip() == '':
        featured = (existing or {}).get('featured', False)
    merged['featured'] = str(featured).strip().lower() in ('true','1','yes','on') if not isinstance(featured, bool) else featured
    merged['slug'] = slug_for(merged.get('name',''), sku)
    if creating and not image_present:
        errors['image'] = 'A primary product image is required.'
    return merged, errors


def read_csv(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 250_000:
        raise InputError({'csv': 'Choose a UTF-8 CSV file smaller than 250 KB.'})
    try:
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff'), newline=''), strict=True)
        headers = [(x or '').strip().lower() for x in (reader.fieldnames or [])]
        if 'sku' not in headers:
            raise InputError({'csv': 'CSV must contain a sku column.'})
        if len(set(headers)) != len(headers) or any(x not in CSV_FIELDS for x in headers):
            raise InputError({'csv': 'CSV has duplicate or unsupported column names.'})
        rows=[]
        for row in reader:
            if len(rows) >= MAX_CSV_ROWS:
                raise InputError({'csv': 'Maximum 60 products per batch.'})
            if None in row:
                raise InputError({'csv': f'Row {len(rows)+2} has more values than header columns.'})
            if not any(str(v or '').strip() for v in row.values()):
                continue
            rows.append({str(k).strip().lower(): str(v or '').strip() for k,v in row.items()})
    except csv.Error as exc:
        raise InputError({'csv': f'Malformed CSV: {exc}'})
    if not rows:
        raise InputError({'csv': 'CSV contains no product rows.'})
    return rows


def order_decision(lines, available):
    """Evaluate all quantities together; never reserve partial order lines."""
    errors={}
    desired={}
    for line in lines:
        sku=sku_value(line.get('sku'))
        qty=line.get('qty')
        if not SKU_RE.fullmatch(sku) or isinstance(qty,bool) or not isinstance(qty,int) or qty<1 or qty>99:
            errors[sku or 'items']='Choose an existing SKU and quantity between 1 and 99.'
        else:
            desired[sku]=desired.get(sku,0)+qty
    for sku,qty in desired.items():
        if qty>99:
            errors[sku]='Maximum 99 units per SKU per demo order.'
        if sku not in available:
            errors[sku]='Product is not available for purchase.'
    if errors: raise InputError(errors)
    shortages={sku:max(0, qty-available[sku]) for sku,qty in desired.items()}
    shortages={sku:v for sku,v in shortages.items() if v}
    return {'requested': desired, 'shortages':shortages, 'ready': not shortages}
