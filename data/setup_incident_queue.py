"""
Builds incident_tickets.json — the store-systems incident queue used by
A1 (tool calling) and A3 (the triage agent case study).

Run:  python setup_incident_queue.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

TICKETS = [
    {
        "id": "INC-30017",
        "opened": "2026-08-14T11:42:00-05:00",
        "store": "Store 2203 (Plano, TX)",
        "reported_by": "Store manager via ops hotline",
        "title": "Card payments failing at most registers",
        "body": ("Since about 11:30 nearly every card transaction is timing out. Screen says "
                 "'no response from acquirer' after a long wait. Cash is fine. Self-checkouts have "
                 "all switched to 'payment unavailable, see associate'. Customers are retrying cards "
                 "multiple times. Lines are building fast — this is our lunch rush."),
        "severity_reported": None,
        "status": "NEW",
    },
    {
        "id": "INC-30021",
        "opened": "2026-08-14T12:05:00-05:00",
        "store": "Store 4471 (Bentonville, AR)",
        "reported_by": "POS_SYNC_LAG alert",
        "title": "POS sync backlog climbing steadily",
        "body": ("Sync backlog crossed 900 transactions around 11:50 and is still climbing at roughly "
                 "120 per minute. Checkout is unaffected — terminals are queueing locally. Store edge "
                 "gateway heartbeat looks normal. No other store in the region is affected."),
        "severity_reported": None,
        "status": "NEW",
    },
    {
        "id": "INC-30024",
        "opened": "2026-08-14T12:18:00-05:00",
        "store": "14 stores, South-Central region",
        "reported_by": "INVENTORY_FEED_STALE alert",
        "title": "Inventory feed stale across South-Central",
        "body": ("Inventory feed has not advanced for 62 minutes across 14 stores. Online stock counts "
                 "for those stores are drifting from shelf reality. Pickup orders are still being "
                 "accepted against stale counts."),
        "severity_reported": None,
        "status": "NEW",
    },
    {
        "id": "INC-30028",
        "opened": "2026-08-14T12:31:00-05:00",
        "store": "Store 0554 (Tulsa, OK)",
        "reported_by": "CHECKOUT_LATENCY alert",
        "title": "Checkout completion time ~15 seconds",
        "body": ("Median checkout completion has climbed to about 15 seconds, up from a normal 2. "
                 "Associates report the terminal 'hangs on the payment screen then catches up'. "
                 "Card payments are completing — just very slowly."),
        "severity_reported": None,
        "status": "NEW",
    },
    {
        "id": "INC-30031",
        "opened": "2026-08-14T12:44:00-05:00",
        "store": "Store 3110 (Springdale, AR)",
        "reported_by": "Store associate, verbal via district lead",
        "title": "Registers 'acting weird'",
        "body": ("Second-hand verbal report relayed through the district lead: the registers are "
                 "'acting weird' this morning. No alert has fired for this store. No error text, no "
                 "affected count, no start time given. The associate who called is now off shift."),
        "severity_reported": None,
        "status": "NEW",
    },
    {
        "id": "INC-30047",
        "opened": "2026-08-14T13:02:00-05:00",
        "store": "Store 1188 (Rogers, AR)",
        "reported_by": "Store manager via ops hotline",
        "title": "Self-checkout lane 4 rejecting all coupons",
        "body": ("Since roughly 12:40, lane 4 rejects every scanned coupon with 'offer not valid'. "
                 "Other lanes at the same store accept the same coupons without issue. Manager has "
                 "closed lane 4 for now."),
        "severity_reported": None,
        "status": "NEW",
    },
]

if __name__ == "__main__":
    out = os.path.join(HERE, "incident_tickets.json")

    # Non-destructive: if a queue file already exists (e.g. the facilitator's own),
    # leave it alone. Delete the file, or pass --force, to regenerate.
    import sys
    if os.path.exists(out) and "--force" not in sys.argv:
        existing = json.load(open(out, encoding="utf-8"))
        print(f"  incident_tickets.json already exists "
              f"({len(existing.get('tickets', []))} tickets) — left untouched.")
        raise SystemExit(0)

    with open(out, "w", encoding="utf-8") as f:
        json.dump({"tickets": TICKETS}, f, indent=2)
    print(f"  created  incident_tickets.json  {len(TICKETS)} tickets, {os.path.getsize(out):,} bytes")
    for t in TICKETS:
        print(f"    {t['id']}  {t['status']:>4}  {t['title'][:52]}")
