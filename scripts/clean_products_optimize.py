"""
Clean Shopify product export CSV for PostgreSQL import.

Strategy: Manual parsing approach. For each line:
1. Strip semicolons and unwrap outer quotes
2. For product lines: manually extract handle, title, body (using known patterns)
3. For variant lines: parse with csv.reader (no body field issues)
4. For continuation lines: accumulate into current product's body

FIX: Variant Price is extracted via regex (deny,manual,PRICE pattern) to avoid
column-index shifts caused by outer-quote wrapping. Price is also sanitized
to a valid decimal before writing, preventing PostgreSQL import errors like:
  "Can't parse numeric value [deny]"
"""
import csv
import re
from bs4 import BeautifulSoup
import os
import sys
from io import StringIO

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

HANDLE_RE = re.compile(r'^[a-z0-9][a-z0-9\-]+$')

# Matches the price directly from the raw variant line via known surrounding fields:
#   ...,<inventory_policy (deny|continue)>,<fulfillment_service>,<PRICE>,...
# This is immune to column-index shifts from quote-wrapping/unwrapping.
VARIANT_PRICE_RE = re.compile(
    r',(?:deny|continue),[^,]+,(\d+(?:\.\d+)?)\s*,'
)

# Known vendors from the Shopify export
KNOWN_VENDORS = [
    'Fast Print Indonesia', 'Fast Print', 'Epson', 'Canon', 'HP',
    'Brother', 'Favorite', 'Data Print', 'Direct To Garment',
    'TINTONLIFE Store', 'Lasika', 'Xerox',
]
# Build regex: "",VendorName, — with known vendors sorted longest first to avoid partial matches
_vendor_pattern = '|'.join(re.escape(v) for v in sorted(KNOWN_VENDORS, key=len, reverse=True))
BODY_CLOSE_RE = re.compile(r'"",(' + _vendor_pattern + r'),')


def clean_html(html_text):
    """Strip HTML tags and normalize whitespace."""
    if not isinstance(html_text, str) or not html_text:
        return ""
    try:
        html_text = re.sub(r';+$', '', html_text)
        soup = BeautifulSoup(html_text, "html.parser")
        text = soup.get_text(separator=' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception:
        return ""


def sanitize_price(value):
    """
    Return a clean decimal string or empty string.

    Accepts: '160000.00', '390', '2900000.00'
    Rejects (returns ''): 'deny', 'manual', '', None, 'Variant Price'

    This is the safety net — even if price extraction produces a bad value,
    PostgreSQL will receive NULL (via empty string) rather than a word.
    """
    if not value:
        return ''
    value = value.strip().strip("'\"")
    # Must be digits with an optional single decimal point
    if re.match(r'^\d+(\.\d+)?$', value):
        return value
    return ''


def extract_price_from_raw(raw_line):
    """
    Extract the Variant Price from a raw variant row string using the known
    field pattern:  ...,deny|continue,<fulfillment>,<PRICE>,...

    Returns the price string (e.g. '160000.00') or '' if not found.
    This bypasses column-index issues caused by outer-quote wrapping.
    """
    m = VARIANT_PRICE_RE.search(raw_line)
    if m:
        return m.group(1)
    return ''


def is_valid_handle(text):
    if not text:
        return False
    return bool(HANDLE_RE.match(text.strip()))


def strip_line(line):
    """Strip trailing semicolons, CR/LF."""
    return re.sub(r';{3,}\r?\n?$', '', line).rstrip('\r\n')


def extract_metadata_after_body(text):
    """
    Extract Vendor, Category, Type, Tags from the metadata that follows body close.

    The metadata portion looks like:
    Vendor,Category,Type,"Tags" or Vendor,Category,Type,""Tags""

    Returns (vendor, tags) tuple.
    """
    if not text:
        return '', ''

    try:
        # Parse as CSV to handle quoted fields
        rows = list(csv.reader(StringIO(text)))
        if rows and rows[0]:
            fields = rows[0]
            vendor = fields[0].strip() if len(fields) > 0 else ''
            # Type is index 2, Tags is index 3
            tags = fields[3].strip() if len(fields) > 3 else ''
            return vendor, tags
    except Exception:
        pass
    return '', ''


def extract_sku_from_raw(raw_line, idx_sku):
    """
    Extract SKU from raw line via csv.reader with fallback.
    The SKU field often has a leading apostrophe (e.g. '2611916) — strip it.
    """
    try:
        rows = list(csv.reader(StringIO(raw_line)))
        if rows and rows[0]:
            fields = rows[0]
            if len(fields) > idx_sku:
                return fields[idx_sku].strip().strip("'")
    except Exception:
        pass
    return ''


def process_csv(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"File {input_file} not found.")
        return

    print("Step 1: Reading file...")
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        raw_lines = f.readlines()
    print(f"  {len(raw_lines)} raw lines")

    # Parse header to get column indices for variant rows
    header_line = strip_line(raw_lines[0])
    header_fields = next(csv.reader(StringIO(header_line)))
    col_map = {name.strip(): i for i, name in enumerate(header_fields)}
    idx_sku = col_map.get('Variant SKU', 17)
    idx_price = col_map.get('Variant Price', 23)
    print(f"  Header: {len(header_fields)} cols, SKU col={idx_sku}, Price col={idx_price}")
    print(f"  NOTE: Price will be extracted via regex pattern (immune to index shifts)")

    # Process data lines
    print("Step 2: Parsing products...")
    products = []       # list of product dicts
    current = None      # current product being built
    body_parts = []     # accumulates body HTML parts

    for line in raw_lines[1:]:
        stripped = strip_line(line).strip()
        if not stripped:
            continue

        # Unwrap outer quotes if present
        unwrapped = stripped
        starts_with_quote = stripped.startswith('"')
        if starts_with_quote:
            inner = stripped[1:]
            fc = inner.find(',')
            if fc > 0 and is_valid_handle(inner[:fc]):
                unwrapped = inner
                if unwrapped.endswith('"'):
                    unwrapped = unwrapped[:-1]

        # Check if line starts with a handle
        fc = unwrapped.find(',')
        handle_candidate = unwrapped[:fc] if fc > 0 else ''

        if is_valid_handle(handle_candidate):
            rest = unwrapped[fc+1:]  # everything after handle,

            # Check if this has a title (product definition) or not (variant/image row)
            tc = rest.find(',')
            title_candidate = rest[:tc].strip() if tc >= 0 else rest.strip()

            if title_candidate and not title_candidate.startswith('"') and not title_candidate.startswith('<'):
                # PRODUCT DEFINITION LINE
                # Save previous product
                if current:
                    current['body_html'] = ' '.join(body_parts)
                    products.append(current)

                title = title_candidate
                body_and_rest = rest[tc+1:] if tc >= 0 else ''

                # The body starts with "" and ends with "",
                # Everything after the body close is: Vendor,Category,Type,"Tags",Published,...
                # Find where body starts: should start with ""
                if body_and_rest.startswith('""'):
                    body_content = body_and_rest[2:]  # remove opening ""

                    # Find the body close: "",VendorName,
                    m = BODY_CLOSE_RE.search(body_content)

                    if m:
                        body_raw = body_content[:m.start()]
                        metadata = body_content[m.start()+3:]  # skip the "",
                        vendor, tags = extract_metadata_after_body(metadata)
                    else:
                        body_raw = body_content
                        vendor, tags = '', ''
                else:
                    body_raw = body_and_rest
                    vendor, tags = '', ''

                current = {
                    'handle': handle_candidate,
                    'title': title,
                    'vendor': vendor,
                    'tags': tags,
                    'variants': [],
                }
                body_parts = [body_raw] if body_raw else []

            else:
                # VARIANT or IMAGE ROW (handle present, no title)
                if current and handle_candidate == current['handle']:
                    # -------------------------------------------------------
                    # FIX: Extract price via regex from the raw (original)
                    # line — not from field index — to avoid index shifts
                    # caused by outer-quote wrapping/unwrapping.
                    # -------------------------------------------------------
                    price = extract_price_from_raw(stripped)   # use `stripped` (original, before unwrap)
                    if not price:
                        price = extract_price_from_raw(unwrapped)  # fallback to unwrapped

                    # SKU can still use index-based extraction (it's near the
                    # start of the line and less affected by index shifts)
                    sku = extract_sku_from_raw(unwrapped, idx_sku)

                    # Final safety: sanitize both fields
                    price = sanitize_price(price)
                    sku = sku if re.match(r'^[A-Za-z0-9\-_\']+$', sku) else sku  # keep as-is (text field)

                    if sku or price:
                        current['variants'].append({'sku': sku, 'price': price})

        else:
            # CONTINUATION LINE (body HTML or metadata)
            if current:
                # Check if this line contains the body-closing + metadata
                m = BODY_CLOSE_RE.search(unwrapped)
                if m and not current.get('vendor'):
                    # Body part before close
                    body_parts.append(unwrapped[:m.start()])
                    # Extract metadata (skip "",)
                    metadata = unwrapped[m.start()+3:]
                    vendor, tags = extract_metadata_after_body(metadata)
                    current['vendor'] = vendor
                    current['tags'] = tags
                    if vendor:
                        print(f"  DEBUG: Found vendor=[{vendor}] tags=[{tags[:40]}] for handle=[{current['handle'][:40]}]")
                else:
                    body_parts.append(unwrapped)

    # Save last product
    if current:
        current['body_html'] = ' '.join(body_parts)
        products.append(current)

    print(f"  Found {len(products)} products")
    total_variants = sum(len(p['variants']) for p in products)
    print(f"  Found {total_variants} variant rows")
    with_vendor = sum(1 for p in products if p['vendor'])
    print(f"  Products with vendor: {with_vendor}")

    # Step 3: Write output
    print("Step 3: Writing output CSV...")
    output_fields = ['handle', 'title', 'body', 'vendor', 'tags', 'variant_sku', 'variant_price']

    bad_price_count = 0

    with open(output_file, 'w', encoding='utf-8', newline='') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=output_fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        rows_written = 0
        for product in products:
            body = clean_html(product.get('body_html', ''))
            vendor = product.get('vendor', '')
            tags = product.get('tags', '')

            variants = product.get('variants', [])
            if variants:
                for var in variants:
                    raw_price = var.get('price', '')
                    clean_price = sanitize_price(raw_price)
                    if raw_price and not clean_price:
                        bad_price_count += 1
                        print(f"  WARN: Dropped bad price [{raw_price}] for handle [{product['handle']}]")
                    writer.writerow({
                        'handle': product['handle'],
                        'title': product['title'],
                        'body': body,
                        'vendor': vendor,
                        'tags': tags,
                        'variant_sku': var.get('sku', ''),
                        'variant_price': clean_price,
                    })
                    rows_written += 1
            else:
                writer.writerow({
                    'handle': product['handle'],
                    'title': product['title'],
                    'body': body,
                    'vendor': vendor,
                    'tags': tags,
                    'variant_sku': '',
                    'variant_price': '',
                })
                rows_written += 1

    print(f"\nDone! {rows_written} rows written from {len(products)} products")
    if bad_price_count:
        print(f"WARNING: {bad_price_count} non-numeric price(s) were cleared (set to empty)")
    else:
        print("All price values are clean numeric strings.")
    print(f"Output: {output_file}")

    print(f"""
-- PostgreSQL CREATE TABLE + COPY:
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    handle VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    body TEXT,
    vendor VARCHAR(255),
    tags TEXT,
    variant_sku VARCHAR(100),
    variant_price DECIMAL(10,2)
);

\\COPY products(handle, title, body, vendor, tags, variant_sku, variant_price)
FROM '{os.path.abspath(output_file)}'
WITH (FORMAT csv, HEADER true, QUOTE '"', ENCODING 'UTF8');
""")


if __name__ == "__main__":
    process_csv('products_export_1.csv', 'scripts/products_for_postgres_final.csv')