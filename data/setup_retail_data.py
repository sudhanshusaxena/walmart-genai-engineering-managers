"""Shared retail ops dataset for Day 3-5 exercises (E09-E15).

Creates retail_ops.db (SQLite) and shipments.json in this folder.
Idempotent: safe to run repeatedly; drops and recreates tables.

Analytics tables (E09 — Plain-English Analytics / SQL RAG):
    regions   (region_id, region_name)
    stores    (store_id, store_name, region_id, store_format, city, opened_date)
    sales     (sale_id, store_id, week_start, category, units_sold, revenue)
    inventory (inv_id, store_id, week_start, category, units_on_hand)   -- WEEKLY grain
    incidents (incident_id, store, incident_type, severity, opened_date, status, description)

Operational tables/files (E10+ — tool calling / MCP):
    sku_stock (sku, name, store_id, on_hand, reorder_point)   -- live SKU-level stock
    shipments.json                                            -- inbound shipment feed

Deliberate design notes (used by E09):
    * incidents.store holds the store NAME, not store_id  -> a realistic join trap.
    * Southeast region inventory turns visibly drop in Q2 2026 (Apr-Jun):
      on-hand inventory balloons while sales soften.
    * sales/inventory cover weekly grain from 2025-07-07 through 2026-08-10.
"""

import json
import os
import random
import sqlite3
from datetime import date, timedelta

random.seed(20260817)

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, 'retail_ops.db')
SHIPMENTS_PATH = os.path.join(HERE, 'shipments.json')

# ---------------------------------------------------------------- E10 data --

SKU_STOCK = [
    # sku, name, store_id, on_hand, reorder_point
    ('WM-KETTLE-01',  'Mainstays 1.7L Electric Kettle',       4479, 0,  12),
    ('WM-KETTLE-02',  'Farberware Stovetop Whistling Kettle', 4479, 34, 10),
    ('WM-TOWEL-04',   'Bath Towel 6-Pack, White',             4479, 88, 20),
    ('WM-AIRFRY-11',  'Gourmia 6-Qt Digital Air Fryer',       4479, 7,  15),
    ('WM-LED-32',     '32in LED Smart TV',                    4479, 21, 8),
    ('WM-KETTLE-01',  'Mainstays 1.7L Electric Kettle',       2091, 56, 12),
    ('WM-TOWEL-04',   'Bath Towel 6-Pack, White',             2091, 12, 20),
    ('WM-AIRFRY-11',  'Gourmia 6-Qt Digital Air Fryer',       2091, 41, 15),
]

SHIPMENTS = [
    {
        'shipment_id': 'SHP-88121', 'sku': 'WM-KETTLE-01', 'units': 48,
        'dest_store': 4479, 'status': 'DELAYED',
        'original_eta': '2026-08-11', 'current_eta': '2026-08-18',
        'note': 'Carrier weather hold at DC 6094; trailer re-slotted, +7 days.',
    },
    {
        'shipment_id': 'SHP-88377', 'sku': 'WM-AIRFRY-11', 'units': 24,
        'dest_store': 4479, 'status': 'IN_TRANSIT',
        'original_eta': '2026-08-15', 'current_eta': '2026-08-15',
        'note': 'On schedule.',
    },
    {
        'shipment_id': 'SHP-88402', 'sku': 'WM-TOWEL-04', 'units': 120,
        'dest_store': 2091, 'status': 'DELIVERED',
        'original_eta': '2026-08-12', 'current_eta': '2026-08-12',
        'note': 'Received and putaway complete.',
    },
]

# ---------------------------------------------------------------- E09 data --

REGIONS = [(1, 'Northeast'), (2, 'Southeast'), (3, 'Midwest'), (4, 'West')]

STORES = [
    # (store_id, name, region_id, format, city)
    (101, 'Store 101 - Jersey City', 1, 'Supercenter', 'Jersey City'),
    (102, 'Store 102 - Boston Fenway', 1, 'Neighborhood Market', 'Boston'),
    (103, 'Store 103 - Philadelphia North', 1, 'Supercenter', 'Philadelphia'),
    (104, 'Store 104 - Buffalo Ridge', 1, 'Discount Store', 'Buffalo'),
    (105, 'Store 105 - Hartford Plaza', 1, 'Neighborhood Market', 'Hartford'),
    (106, 'Store 106 - Pittsburgh East', 1, 'Supercenter', 'Pittsburgh'),
    (201, 'Store 201 - Atlanta Midtown', 2, 'Supercenter', 'Atlanta'),
    (202, 'Store 202 - Orlando Gateway', 2, 'Supercenter', 'Orlando'),
    (203, 'Store 203 - Charlotte South', 2, 'Neighborhood Market', 'Charlotte'),
    (204, 'Store 204 - Nashville West', 2, 'Discount Store', 'Nashville'),
    (205, 'Store 205 - Miami Shores', 2, 'Supercenter', 'Miami'),
    (206, 'Store 206 - Birmingham Central', 2, 'Neighborhood Market', 'Birmingham'),
    (301, 'Store 301 - Chicago Cicero', 3, 'Supercenter', 'Chicago'),
    (302, 'Store 302 - Columbus Easton', 3, 'Neighborhood Market', 'Columbus'),
    (303, 'Store 303 - Minneapolis Lake', 3, 'Supercenter', 'Minneapolis'),
    (304, 'Store 304 - Kansas City Plaza', 3, 'Discount Store', 'Kansas City'),
    (305, 'Store 305 - Detroit Riverside', 3, 'Supercenter', 'Detroit'),
    (306, 'Store 306 - St Louis Grove', 3, 'Neighborhood Market', 'St Louis'),
    (401, 'Store 401 - Phoenix Desert Sky', 4, 'Supercenter', 'Phoenix'),
    (402, 'Store 402 - Denver Stapleton', 4, 'Supercenter', 'Denver'),
    (403, 'Store 403 - Seattle Rainier', 4, 'Neighborhood Market', 'Seattle'),
    (404, 'Store 404 - Sacramento Delta', 4, 'Discount Store', 'Sacramento'),
    (405, 'Store 405 - Las Vegas Craig', 4, 'Supercenter', 'Las Vegas'),
    (406, 'Store 406 - Portland Gateway', 4, 'Neighborhood Market', 'Portland'),
]

CATEGORIES = ['Grocery', 'Electronics', 'Apparel', 'Home & Garden', 'Pharmacy']

# base weekly units per category for a Supercenter (scaled down for other formats)
BASE_UNITS = {'Grocery': 9000, 'Electronics': 650, 'Apparel': 1800,
              'Home & Garden': 1100, 'Pharmacy': 1400}
AVG_PRICE = {'Grocery': 6.5, 'Electronics': 185.0, 'Apparel': 22.0,
             'Home & Garden': 38.0, 'Pharmacy': 27.0}
FORMAT_SCALE = {'Supercenter': 1.0, 'Neighborhood Market': 0.45, 'Discount Store': 0.65}

INCIDENT_TYPES = [
    ('POS outage', 'checkout lanes down'),
    ('Refrigeration failure', 'cold chain excursion in grocery'),
    ('Inventory system sync error', 'on-hand counts frozen'),
    ('Slip and fall', 'customer safety incident on sales floor'),
    ('Delivery truck delay', 'inbound DC truck missed appointment window'),
    ('Theft / shrink event', 'organized retail crime incident'),
    ('Network outage', 'store lost WAN connectivity'),
]


def week_starts(first: date, last: date):
    d = first
    while d <= last:
        yield d
        d += timedelta(days=7)


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS inventory;
        DROP TABLE IF EXISTS incidents;
        DROP TABLE IF EXISTS stores;
        DROP TABLE IF EXISTS regions;
        DROP TABLE IF EXISTS sku_stock;

        CREATE TABLE regions (
            region_id INTEGER PRIMARY KEY,
            region_name TEXT NOT NULL
        );
        CREATE TABLE stores (
            store_id INTEGER PRIMARY KEY,
            store_name TEXT NOT NULL,
            region_id INTEGER NOT NULL REFERENCES regions(region_id),
            store_format TEXT NOT NULL,
            city TEXT NOT NULL,
            opened_date TEXT NOT NULL
        );
        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL REFERENCES stores(store_id),
            week_start TEXT NOT NULL,
            category TEXT NOT NULL,
            units_sold INTEGER NOT NULL,
            revenue REAL NOT NULL
        );
        CREATE TABLE inventory (
            inv_id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL REFERENCES stores(store_id),
            week_start TEXT NOT NULL,
            category TEXT NOT NULL,
            units_on_hand INTEGER NOT NULL
        );
        CREATE TABLE incidents (
            incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
            store TEXT NOT NULL,             -- store NAME (legacy ticketing system)
            incident_type TEXT NOT NULL,
            severity TEXT NOT NULL,          -- low / medium / high
            opened_date TEXT NOT NULL,
            status TEXT NOT NULL,            -- open / resolved
            description TEXT NOT NULL
        );
        CREATE TABLE sku_stock (
            sku TEXT NOT NULL,
            name TEXT NOT NULL,
            store_id INTEGER NOT NULL,
            on_hand INTEGER NOT NULL,
            reorder_point INTEGER NOT NULL
        );
        """
    )

    cur.executemany('INSERT INTO regions VALUES (?,?)', REGIONS)
    for sid, name, rid, fmt, city in STORES:
        opened = date(random.randint(1998, 2019), random.randint(1, 12), 1)
        cur.execute('INSERT INTO stores VALUES (?,?,?,?,?,?)',
                    (sid, name, rid, fmt, city, opened.isoformat()))

    first_week = date(2025, 7, 7)
    last_week = date(2026, 8, 10)
    store_rows = {s[0]: s for s in STORES}

    for wk in week_starts(first_week, last_week):
        # mild seasonality: holiday bump Nov-Dec, summer bump Jun-Jul
        season = 1.0
        if wk.month in (11, 12):
            season = 1.25
        elif wk.month in (6, 7):
            season = 1.08
        in_q2_2026 = date(2026, 4, 1) <= wk <= date(2026, 6, 30)

        for sid, (_, _, rid, fmt, _c) in store_rows.items():
            scale = FORMAT_SCALE[fmt]
            for cat in CATEGORIES:
                units = BASE_UNITS[cat] * scale * season * random.uniform(0.85, 1.15)
                on_hand = units * random.uniform(3.2, 4.2)  # ~3-4 weeks of supply

                if rid == 2 and in_q2_2026:
                    # Southeast Q2-2026 story: demand softens ~12%,
                    # inventory balloons ~70% (over-ordering ahead of a promo
                    # that under-performed) -> inventory turns visibly drop.
                    units *= 0.88
                    on_hand *= 1.70

                units = int(units)
                on_hand = int(on_hand)
                revenue = round(units * AVG_PRICE[cat] * random.uniform(0.92, 1.08), 2)
                cur.execute(
                    'INSERT INTO sales (store_id, week_start, category, units_sold, revenue)'
                    ' VALUES (?,?,?,?,?)',
                    (sid, wk.isoformat(), cat, units, revenue))
                cur.execute(
                    'INSERT INTO inventory (store_id, week_start, category, units_on_hand)'
                    ' VALUES (?,?,?,?)',
                    (sid, wk.isoformat(), cat, on_hand))

    # incidents: ~340 across the period; Southeast slightly elevated in Q2 2026
    n_days = (last_week - first_week).days
    for _ in range(340):
        sid = random.choice(list(store_rows))
        opened = first_week + timedelta(days=random.randint(0, n_days))
        itype, desc = random.choice(INCIDENT_TYPES)
        sev = random.choices(['low', 'medium', 'high'], weights=[5, 3, 1])[0]
        status = 'resolved' if random.random() < 0.85 else 'open'
        cur.execute(
            'INSERT INTO incidents (store, incident_type, severity, opened_date, status, description)'
            ' VALUES (?,?,?,?,?,?)',
            (store_rows[sid][1], itype, sev, opened.isoformat(), status,
             f'{itype}: {desc} at {store_rows[sid][1]}'))
    # extra Southeast Q2-2026 inventory-sync incidents (part of the story)
    se_stores = [s for s in STORES if s[2] == 2]
    for _ in range(22):
        s = random.choice(se_stores)
        opened = date(2026, 4, 1) + timedelta(days=random.randint(0, 89))
        cur.execute(
            'INSERT INTO incidents (store, incident_type, severity, opened_date, status, description)'
            ' VALUES (?,?,?,?,?,?)',
            (s[1], 'Inventory system sync error', 'medium', opened.isoformat(),
             random.choice(['resolved', 'resolved', 'open']),
             f'Inventory system sync error: on-hand counts frozen at {s[1]}'))

    # E10+ live-operations data
    cur.executemany('INSERT INTO sku_stock VALUES (?,?,?,?,?)', SKU_STOCK)

    conn.commit()
    for t in ('regions', 'stores', 'sales', 'inventory', 'incidents', 'sku_stock'):
        n = cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'  {t:<10} {n:>7,} rows')
    conn.close()

    with open(SHIPMENTS_PATH, 'w') as f:
        json.dump(SHIPMENTS, f, indent=2)

    print(f'Created {DB_PATH}')
    print(f'Created {SHIPMENTS_PATH}')


if __name__ == '__main__':
    main()
