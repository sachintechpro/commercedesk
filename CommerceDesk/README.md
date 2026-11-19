# CommerceDesk

**A B2B storefront, product catalog and order-operations demonstration for glass, glazing and construction-material distributors.**

CommerceDesk is a working demonstration of how a distributor's customer orders, product catalog, inventory and internal order processing can fit into one application. It uses fictional sample products and orders.

## Open the demo

- **Storefront:** https://commercedesk.onrender.com/
- **Admin:** https://commercedesk.onrender.com/admin
- **QA Bench:** https://commercedesk.onrender.com/qa-bench.html
- **How to use the demo:** https://commercedesk.onrender.com/how-to
- **About CommerceDesk:** https://commercedesk.onrender.com/about

Demo admin credentials are available on the admin sign-in page. Do not enter real customer, payment or business-sensitive data.

## Five-minute walkthrough

1. Open the storefront and browse the sample glass hardware and glazing products.
2. Open a product detail page, add an item to the cart and place a fictional demo order.
3. Sign in to Admin and open **Order Management** to review the new order and inventory status.
4. Open **Product Management** to add a product or choose **Batch Import** to preview a spreadsheet and match PNG images.
5. Open **Integrations** to review example workflows for email, accounting, carriers, AI, CRM and warehouse systems.
6. Finish with **How to use this app** and the Contact SachinTechPro call to action.

## Product Management and Batch Import

Product Management includes **Add Product** and **Batch Import**.

Batch Import accepts CSV and TSV files, XLSX workbooks, legacy XLS workbooks when the optional xlrd dependency is installed, and Google Sheets links that are accessible for CSV export. Private Google Sheets OAuth is not configured in this demonstration.

Each new product row should include:

- SKU, product name, category, description, selling price, stock and status
- SLU number
- Image location
- Optional brand, unit of measure, warehouse, bin/shelf, shipping weight, dimensions, reorder level and cost price

Every new product requires a PNG image. The image filename must contain the exact SLU number in the filename, without being part of a longer number, for example glass-front_782341.png. The importer previews each row and image match, blocks the entire batch if any row fails validation, and commits valid products in a single database transaction.

The complete example template is available at samples/products-import-template.csv.

## What is working in this demo

- Public storefront, categories, product details, search, cart and fictional checkout
- Shared SQLite product and order records
- Admin product creation and editing
- Spreadsheet batch preview and server-side validation
- SLU-based PNG image matching and product metadata
- Inventory-aware order creation, all-or-nothing stock reservation and shortage holds
- Demonstration shipping label generation, label-to-order verification and simulated dispatch
- QA Bench with source-backed test design, browser-local manual evidence and live read-only product-link, image and performance checks

## Integration showcase — illustrative, not live

The Integrations page presents possible connections to Gmail, Google Drive, Outlook, WhatsApp Business, SMS, QuickBooks/Intuit, banks, credit-card processors, UPS, FedEx, USPS, freight carriers, OpenAI/ChatGPT APIs, Google Gemini APIs, CRM, ERP and WMS platforms, barcode devices and social channels.

These are capability examples. They are not connected accounts, vendor partnerships or completed integrations. Live connections require provider authorization, API access, configuration and implementation.

## Important demonstration boundaries

- All products, customers, orders and prices are fictional.
- Checkout does not collect or process real payment information.
- Sample shipping labels are visibly marked NOT VALID FOR SHIPMENT. No postage, carrier booking or live tracking is created.
- External email, WhatsApp, accounting, bank, card, CRM, AI, ERP and carrier integrations are not active.
- Product image matching verifies filename and SLU metadata; it does not visually verify that an image depicts the correct product.

## Quality and test evidence

The QA Bench separates source-backed test specifications, actual live read-only checks, manual tester-entered results and GitHub Actions CI evidence. Live performance values are observations from the visitor's browser and network, not a load test or service-level guarantee.

Automated source tests are in tests/. The optional Playwright browser journey is in tests/browser_smoke.py.
