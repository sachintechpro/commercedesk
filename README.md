# CommerceDesk

### Connected B2B Storefront & E-Commerce Operations Demonstration

CommerceDesk demonstrates the core mechanics of a conventional online wholesale store and its administration workflow. A public storefront and password-protected admin portal share an actual server-side SQLite catalog and order database. This is an **independent, fictional demonstration**; it has no integration with WGS Online, BigCommerce, ShipStation, a payment gateway, a shipping carrier, or real suppliers.

CommerceDesk — Demo Login
Admin page	/admin
Username	admin@commercedesk.demo
Password	DemoAdmin!2026

## Features

**Public shopping experience**

- Homepage with promotional content, featured products, four browseable categories, searchable listings and price sorting.
- Individual product detail pages with product images, SKU, stock status, quantities, descriptions and related products.
- Cart with quantity editing, server-authoritative checkout prices and simulated order confirmation.
- Items with zero stock are shown as unavailable. Checkout checks stock again, atomically reserves it if available, or holds the entire order if a shortage appears.

**Admin — Product Management**

- Password-protected admin portal with draft and published products; only published products appear in the public catalog.
- Add/edit individual products, pricing, stock, categories, descriptions and images. Changes are immediately visible to visitors after publishing.
- Validations include mandatory fields, unique and immutable SKUs, positive prices, integer stock and category constraints.
- CSV import workflow with server-side row-by-row preview; explicitly `create` vs `update` operations; SKU-to-image filename matching (e.g. `GH-205.png`); byte signature, image dimensions where applicable and a visual preview.
- If **any CSV row** has an error, the batch is blocked. A successful batch is committed in one database transaction. Images and product changes cannot partially publish if validation fails.
- The image convention checks **filename identity, not photo subject identity**. The user must inspect the displayed preview to confirm that the photo depicts the intended product.

**Admin — Order Management (including shipping)**

- Order queue showing ready, held, label-created and dispatched orders.
- In-stock orders reserve available inventory and become ready to fulfill.
- Shortages hold the order, create an internal purchasing alert and **block label generation**. The admin can update stock and recheck the held order.
- Ready orders can generate clearly invalid **demonstration shipping labels** for printing. A warehouse handoff requires matching the generated label reference to the order; wrong references block dispatch. No actual ShipStation label, postage, tracking number, dispatch or supplier communication is created.
- Activity history of catalog edits, imports and order processing.

## Try the two main workflows

1. **Catalog:** Admin → Product Management → Edit `GH-101`, change price and save as published. Open its public product page to see the updated price. For new products, use the Add Product form and upload a filename matching its SKU. Alternatively, visit **Admin → CSV product import**, choose `samples/products-create.csv` plus the matching three images under `samples/images/` (`GH-205.png`, `GS-305.png`, `GT-505.png`), validate and publish. The new products will appear in the storefront and category listings.
2. **Order processing:** Admin → Order Management. The fictional order **DEMO-1001** is ready to fulfill and can receive a sample label. **DEMO-1002** is held because `GT-403` is out of stock. Label creation is blocked; edit the stock for `GT-403`, then recheck the held order to make it eligible.

CSV samples:

| File | Purpose |
|---|---|
| `samples/products-create.csv` | Three new products and matching images |
| `samples/products-update.csv` | Two existing SKU price updates; image upload not required |
| `samples/products-errors.csv` | Demonstrates duplicate SKU, invalid price, missing category/image |

## Run locally

Requires **Python 3.11+**; no runtime packages or external API keys are required.

```bash
python server.py
```

Open `http://localhost:10000`. Local-only development login password is `DemoAdmin!2026`. This fallback is disabled on Render. **Do not deploy with a default or publicly shared admin password.**

The default admin username is `admin@commercedesk.demo`; this is a fictional login identifier, not a real email address. No external authentication service is used. Production systems require account management, hashed user credentials, authorization roles, audit retention policies and rate limiting.

Run automated checks:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
node --check assets/app.js
```

There is an optional `tests/browser_smoke.py` script, requiring Playwright and a locally installed Chromium binary. It is not part of GitHub Actions and may be restricted in some preview environments.

## Deploy to Render

**This version is a Python Web Service, not a Static Site.** A static hosting service cannot run the shared product database and order APIs. If you previously deployed the older static CommerceDesk, create a **new Web Service** from the updated GitHub repository.

| Render setting | Value |
|---|---|
| Service type | **Web Service** |
| Runtime | Python 3 |
| Repository | `sachintechpro/commercedesk` (after you create or update it) |
| Branch | `main` |
| Root Directory | leave blank (files live at repository root) |
| Build Command | `echo "No external dependencies"` |
| Start Command | `python server.py` |
| Health check path | `/health` |

Set environment variables:

- `ADMIN_USERNAME` — optional demo admin username (defaults to `admin@commercedesk.demo`).
- `ADMIN_PASSWORD` — a **strong private password you choose**, required when running on Render. Never commit it to GitHub.
- `SESSION_SECRET` — a long unpredictable random value. Keep stable between deployments to retain sessions.
- `PUBLIC_BASE_URL` — the actual Render public URL, e.g. `https://<your-service>.onrender.com` (for canonical URLs and sitemap).
- Optional `COMMERCE_DB_PATH` — SQLite file path. Defaults to `data/commerce.sqlite3` relative to the app.
- Optional `ALLOW_DEMO_INDEXING=true` — removes the default public `noindex` metadata. Keep off for fictional product prices.

**Persistence limitation:** The store has real shared database changes while a web-service instance is running. Render instances without persistent storage can lose SQLite data during a restart/redeploy. In that case CommerceDesk reseeds its sample products and orders. For changes that must survive restarts, use an appropriate persistent disk mounted to this service and set `COMMERCE_DB_PATH` to a writable path on that disk. This demo does not currently support PostgreSQL. Shared public demo orders can modify sample stock; an admin-only **Reset demonstration data** button restores the initial fictional state.

## Architectural boundaries

```text
Browser: /, /shop, /category/..., /product/..., /cart, /checkout
    ↕ Same-origin JSON API and cookie-based demo session
Python HTTP server (server.py) + validation rules (model.py)
    ↕ SQLite DB: products, images, orders, order lines, alerts, audit
Admin: /admin → /admin/products · /admin/import · /admin/orders
```

- Public pages have semantic HTML, responsive CSS, per-product canonical/meta tags and Product JSON-LD, a sample sitemap and robots.txt. Fictional storefront pages are marked `noindex` by default.
- The server verifies admin session signatures and requires a matching CSRF token for administrative changes. Prices and inventory are validated and calculated on the server rather than trusted from the browser.
- Demo checkout intentionally requests only a fictional display name and location. **Do not enter real customer or payment information.**
- No live payments, taxes, carrier rates, shipment tracking, supplier integrations or actual BigCommerce API publishing are present.

## Project layout

```text
index.html
server.py
model.py
assets/app.js
assets/styles.css
assets/placeholder.svg
samples/products-create.csv
samples/products-update.csv
samples/products-errors.csv
samples/images/<SKU>.png
.github/workflows/tests.yml
tests/test_model.py
tests/test_api.py
tests/browser_smoke.py (optional)
```

Everything is synthetic. Product photos are self-contained illustrative drawings named by SKU for matching tests—not copied wholesale product photos.

The optional `generate_samples.py` regeneration utility uses Pillow; its sample PNGs are already included, so Pillow is **not required** for deployment or routine use.
