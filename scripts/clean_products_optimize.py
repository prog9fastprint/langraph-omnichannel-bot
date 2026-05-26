"""
Clean Shopify product export CSV for PostgreSQL import.

Approach (two-pass):
  Pass 1 — Reconstruct logical CSV rows.
            Shopify wraps the Body (HTML) field in double-double-quotes and
            it often spans multiple physical lines with trailing semicolons.
            We feed lines into a single csv.reader (C-level state machine)
            so quote tracking is always correct — no repeated re-parsing,
            no hand-rolled quote counter that breaks on HTML content.
  Pass 2 — Each logical row is already parsed by csv.reader, so every column
            lands in the right position automatically.
            Clean body HTML → plain text, sanitise price columns, write output.

Output columns mirror the Shopify export 1-to-1.
"""

import csv
import re
import os
import sys
from io import StringIO
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Field-size safety
# ---------------------------------------------------------------------------
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2_147_483_647)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_trailing_junk(line: str) -> str:
    """Remove trailing semicolons and CR/LF that Shopify appends."""
    return re.sub(r';+\r?\n?$', '', line).rstrip('\r\n')


def clean_html(html: str) -> str:
    """Convert HTML body to plain text and normalise whitespace."""
    if not isinstance(html, str) or not html.strip():
        return ''
    try:
        text = BeautifulSoup(html, 'html.parser').get_text(separator=' ')
        return re.sub(r'\s+', ' ', text).strip()
    except Exception:
        return ''


def sanitise_price(raw: str) -> str:
    """
    Return a string PostgreSQL can cast to DECIMAL(10,2).
    Strips thousand-separator commas; returns '' for blank/non-numeric.
    """
    if not raw or not raw.strip():
        return ''
    cleaned = raw.strip().replace(',', '')
    try:
        float(cleaned)
        return cleaned
    except ValueError:
        return ''


def to_sql_col(name: str) -> str:
    """Convert a Shopify column header to a safe snake_case SQL identifier."""
    s = name.lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_')


# ---------------------------------------------------------------------------
# Pass 1 — stitch physical lines into logical CSV rows
# ---------------------------------------------------------------------------
# Shopify's Body (HTML) field:
#   • Wrapped in "" (double-double-quotes) on the product row.
#   • May contain real newlines, so a single logical row spans many physical lines.
#   • Lines also have trailing ;;; junk.
#
# Fix: we feed cleaned lines one at a time into ONE persistent csv.reader
# that sits on a generator.  Python's csv module is implemented in C and
# maintains its own quote-open/closed state between next() calls, so:
#   • next(reader) blocks until it has consumed enough lines to close all
#     open quoted fields and returns exactly one complete parsed row.
#   • We never re-parse from the beginning, never do hand-rolled quote math.
# This is O(n) in total bytes and correct for any HTML content inside quotes.

def _cleaned_line_generator(raw_lines):
    """Yield cleaned, non-empty lines one at a time."""
    for raw in raw_lines:
        cleaned = strip_trailing_junk(raw)
        if cleaned.strip():
            yield cleaned


def reconstruct_logical_rows(raw_lines: list[str]) -> list[list[str]]:
    """
    Stream physical lines through csv.reader, collecting complete parsed rows.
    Returns a list of field-lists (already split — no second parse needed).
    """
    logical: list[list[str]] = []
    gen    = _cleaned_line_generator(raw_lines)
    reader = csv.reader(gen)

    for row in reader:          # csv.reader pulls from gen until row is closed
        logical.append(row)

    return logical


# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------
SHOPIFY_COLUMNS = [
    'Handle', 'Title', 'Body (HTML)', 'Vendor', 'Product Category',
    'Type', 'Tags', 'Published',
    'Option1 Name', 'Option1 Value',
    'Option2 Name', 'Option2 Value',
    'Option3 Name', 'Option3 Value',
    'Variant SKU', 'Variant Grams', 'Variant Inventory Tracker',
    'Variant Inventory Qty', 'Variant Inventory Policy',
    'Variant Fulfillment Service',
    'Variant Price', 'Variant Compare At Price',
    'Variant Requires Shipping', 'Variant Taxable', 'Variant Barcode',
    'Image Src', 'Image Position', 'Image Alt Text',
    'Gift Card', 'SEO Title', 'SEO Description',
    'Google Shopping / Google Product Category',
    'Google Shopping / Gender', 'Google Shopping / Age Group',
    'Google Shopping / MPN', 'Google Shopping / Condition',
    'Google Shopping / Custom Product',
    'Google Shopping / Custom Label 0', 'Google Shopping / Custom Label 1',
    'Google Shopping / Custom Label 2', 'Google Shopping / Custom Label 3',
    'Google Shopping / Custom Label 4',
    'Variant Image', 'Variant Weight Unit', 'Variant Tax Code',
    'Cost per item',
    'Included / Indonesia', 'Price / Indonesia',
    'Compare At Price / Indonesia', 'Status',
]

PRICE_COLUMNS = {
    'Variant Price', 'Variant Compare At Price',
    'Cost per item', 'Price / Indonesia', 'Compare At Price / Indonesia',
}

# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

def process_csv(input_file: str, output_file: str) -> None:
    if not os.path.exists(input_file):
        print(f'[ERROR] File not found: {input_file}')
        return

    # ── Step 1: read raw lines ─────────────────────────────────────────────
    print('Step 1: Reading file …')
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as fh:
        raw_lines = fh.readlines()
    print(f'  {len(raw_lines):,} physical lines')

    # Parse header (first line)
    header_raw    = strip_trailing_junk(raw_lines[0])
    actual_header = [h.strip() for h in next(csv.reader(StringIO(header_raw)))]
    num_cols      = len(actual_header)
    print(f'  {num_cols} columns detected from header')

    if actual_header != SHOPIFY_COLUMNS[:num_cols]:
        print('  [warn] Header differs from SHOPIFY_COLUMNS — using actual header.')
    output_columns = actual_header

    # ── Step 2: reconstruct logical rows ───────────────────────────────────
    print('Step 2: Reconstructing logical rows …')
    logical_rows = reconstruct_logical_rows(raw_lines[1:])
    print(f'  {len(logical_rows):,} logical rows reconstructed')

    # ── Step 3: clean each row ─────────────────────────────────────────────
    print('Step 3: Cleaning rows …')
    sql_columns = [to_sql_col(c) for c in output_columns]
    body_idx    = output_columns.index('Body (HTML)') \
                  if 'Body (HTML)' in output_columns else None
    price_idxs  = {i for i, c in enumerate(output_columns) if c in PRICE_COLUMNS}

    cleaned_rows: list[list[str]] = []
    skipped = 0

    for fields in logical_rows:
        # Skip rows with completely wrong column count (truly malformed)
        if len(fields) > num_cols * 2:
            skipped += 1
            continue

        # Pad short rows — variant/image rows legitimately omit trailing cols
        while len(fields) < num_cols:
            fields.append('')

        # Clean Body (HTML) → plain text
        if body_idx is not None:
            fields[body_idx] = clean_html(fields[body_idx])

        # Sanitise price columns
        for idx in price_idxs:
            if idx < len(fields):
                fields[idx] = sanitise_price(fields[idx])

        cleaned_rows.append(fields[:num_cols])

    print(f'  {len(cleaned_rows):,} rows cleaned  |  {skipped} skipped (malformed)')

    # ── Step 4: write output CSV ───────────────────────────────────────────
    print('Step 4: Writing output CSV …')
    out_dir = os.path.dirname(os.path.abspath(output_file))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8', newline='') as fout:
        writer = csv.writer(fout, quoting=csv.QUOTE_ALL)
        writer.writerow(sql_columns)
        writer.writerows(cleaned_rows)

    abs_out = os.path.abspath(output_file)
    print(f'\nDone!  {len(cleaned_rows):,} rows written')
    print(f'Output: {abs_out}')

    # ── PostgreSQL DDL + COPY ──────────────────────────────────────────────
    type_map = {
        'handle':                       'VARCHAR(255) NOT NULL',
        'title':                        'VARCHAR(500)',
        'body_html':                    'TEXT',
        'vendor':                       'VARCHAR(255)',
        'product_category':             'VARCHAR(255)',
        'type':                         'VARCHAR(255)',
        'tags':                         'TEXT',
        'published':                    'BOOLEAN',
        'variant_sku':                  'VARCHAR(100)',
        'variant_grams':                'NUMERIC(10,2)',
        'variant_inventory_qty':        'INTEGER',
        'variant_price':                'DECIMAL(10,2)',
        'variant_compare_at_price':     'DECIMAL(10,2)',
        'variant_requires_shipping':    'BOOLEAN',
        'variant_taxable':              'BOOLEAN',
        'image_position':               'INTEGER',
        'cost_per_item':                'DECIMAL(10,2)',
        'price_indonesia':              'DECIMAL(10,2)',
        'compare_at_price_indonesia':   'DECIMAL(10,2)',
        'status':                       'VARCHAR(50)',
    }

    col_defs    = [f'    {c:<50} {type_map.get(c, "TEXT")}' for c in sql_columns]
    import_cols = ', '.join(sql_columns)

    print(f"""
-- ── PostgreSQL DDL ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
{chr(10).join(f"{d}," for d in col_defs[:-1])}
{col_defs[-1]}
);

-- ── Import (run from psql) ────────────────────────────────────────────────────
\\COPY products({import_cols})
FROM '{abs_out}'
WITH (FORMAT csv, HEADER true, QUOTE '"', ENCODING 'UTF8', NULL '');
""")


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    process_csv(
        input_file='products_export_1.csv',
        output_file='scripts/products_for_postgres_final.csv',
    )