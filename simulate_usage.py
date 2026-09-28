"""
HDAOS v3.0 — real-life usage simulation.

Drives the live API the way a real user would across a working day:
login, CRM work, FEFO dispensing, procurement, AI invoice ingest,
approvals, notification scans, audit trail, dashboard.

Stdlib-only HTTP client (urllib + cookie handling).  Uses the Bearer
token from /auth/login/ because the dev backend also accepts header auth
(CookieJWTAuthentication falls back to the Authorization header); this is
exactly equivalent to the browser's HttpOnly cookie path.

Usage:
    cd health-dispensary-analytical-ordering-system
    python simulate_usage.py > sim_report.txt 2>&1
"""
from __future__ import annotations

import json
import os
import sys
import uuid as uuid_module
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("HDAOS_BASE", "http://127.0.0.1:8000")
API = BASE + "/api"
INVOICE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch_invoices")

PASS = 0
FAIL = 0
BUGS: list[str] = []


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def check(label: str, ok: bool, detail: str = "") -> bool:
    global PASS, FAIL
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    if ok:
        PASS += 1
    else:
        FAIL += 1
    return ok


def bug(label: str, detail: str) -> None:
    BUGS.append(f"{label}: {detail}")
    print(f"  [BUG ] {label} — {detail}")


class Client:
    """Tiny authenticated HTTP client for one user session."""

    def __init__(self, username: str, password: str, use_cookies: bool = False):
        self.username = username
        self.token: str | None = None
        self.password = password
        self.calls = 0
        self.opener = None
        if use_cookies:
            # Browser-equivalent session: keep the HttpOnly JWT cookies the
            # server sets on login/refresh.
            import http.cookiejar

            jar = http.cookiejar.CookieJar()
            self.opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(jar))

    # -- internals ---------------------------------------------------------
    def _request(self, method: str, path: str, body=None, raw_body: bytes | None = None,
                 content_type: str = "application/json") -> tuple[int, dict | list | str]:
        self.calls += 1
        url = API + path
        data = None
        if raw_body is not None:
            data = raw_body
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", content_type)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            urlopen = self.opener.open if self.opener else urllib.request.urlopen
            with urlopen(req, timeout=60) as resp:
                payload = resp.read()
                code = resp.status
        except urllib.error.HTTPError as e:
            payload = e.read()
            code = e.code
        try:
            parsed = json.loads(payload.decode("utf-8")) if payload else ""
        except (json.JSONDecodeError, UnicodeDecodeError):
            parsed = payload[:300].decode("utf-8", errors="replace")
        return code, parsed

    # -- public ------------------------------------------------------------
    def login(self) -> bool:
        code, data = self._request("POST", "/auth/login/",
                                   {"username": self.username, "password": self.password})
        ok = code == 200 and isinstance(data, dict) and data.get("access")
        if ok:
            self.token = data["access"]
        return ok

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, body=None):
        return self._request("POST", path, body)

    def patch(self, path: str, body=None):
        return self._request("PATCH", path, body)

    def delete(self, path: str):
        return self._request("DELETE", path)

    def post_multipart(self, path: str, fields: dict[str, str]) -> tuple[int, dict | str]:
        boundary = "----HDAOS-sim-boundary-42"
        lines: list[bytes] = []
        for name, value in fields.items():
            lines.append(f"--{boundary}\r\n".encode())
            lines.append(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            lines.append(value.encode("utf-8"))
            lines.append(b"\r\n")
        lines.append(f"--{boundary}--\r\n".encode())
        return self._request("POST", path, raw_body=b"".join(lines),
                             content_type=f"multipart/form-data; boundary={boundary}")


# ---------------------------------------------------------------------------
# shared fixtures loaded from the seeder's output
# ---------------------------------------------------------------------------
def load_synthetic_audit_id() -> str | None:
    path = os.path.join(INVOICE_DIR, "synthetic_audit_id.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return None


def find(client: Client, list_path: str, **filters) -> dict | None:
    """Fetch a list endpoint and return the first result matching filters."""
    code, data = client.get(list_path)
    if code != 200:
        return None
    results = data["results"] if isinstance(data, dict) and "results" in data else data
    if not isinstance(results, list):
        return None
    for item in results:
        if all(item.get(k) == v for k, v in filters.items()):
            return item
    return None


# ---------------------------------------------------------------------------
# 1. authentication
# ---------------------------------------------------------------------------
def scenario_auth() -> Client:
    section("1. AUTH — admin logs in")
    admin = Client("devadmin", "e2e-pass-1234")
    if not check("devadmin login", admin.login()):
        print("FATAL: cannot continue without auth")
        sys.exit(1)
    code, me = admin.get("/auth/me/")
    check("GET /auth/me/", code == 200 and me.get("username") == "devadmin",
          f"role={me.get('role') if isinstance(me, dict) else '?'}")

    bad = Client("devadmin", "wrong-password")
    code, _ = bad.post("/auth/login/", {"username": "devadmin", "password": "wrong-password"})
    check("wrong password rejected (401)", code == 401, f"got {code}")
    return admin


# ---------------------------------------------------------------------------
# 2. CRM journey (sales rep)
# ---------------------------------------------------------------------------
def scenario_crm(admin: Client) -> None:
    section("2. CRM — sales rep daily journey (via devadmin, full permissions)")
    stamp = "sim"

    code, tag = admin.post("/crm/tags/", {
        "name": f"SYN-sim-tag-{uuid_module.uuid4().hex[:6]}", "color": "accent",
    })
    ok = check("create tag", code in (200, 201), str(code))
    tag_id = tag.get("id") if isinstance(tag, dict) else None

    code, acc = admin.post("/crm/accounts/", {
        "name": "SYN-Sim Corner Pharmacy", "account_type": "CHAIN",
        "billing_address": "42 Sim Street",
    })
    check("create account", code in (200, 201), str(code))
    account_id = acc.get("id") if isinstance(acc, dict) else None

    code, contact = admin.post("/crm/contacts/", {
        "contact_type": "PATIENT", "first_name": "Sim", "last_name": "Patient",
        "email": "sim.patient@example.com", "mrn": "SYN-MRN-SIM-1",
        "account": account_id, "consent_marketing": True,
    })
    check("create contact (PATIENT + MRN)", code in (200, 201), str(code))
    contact_id = contact.get("id") if isinstance(contact, dict) else None

    code, lead = admin.post("/crm/leads/", {
        "name": "SYN-Sim Wholesale Lead", "source": "Simulation",
        "status": "NEW", "est_value": 5000,
    })
    check("create lead", code in (200, 201), str(code))
    lead_id = lead.get("id") if isinstance(lead, dict) else None

    if lead_id:
        code, opp = admin.post(f"/crm/leads/{lead_id}/convert/", {
            "account_name": "SYN-Sim Wholesale Account",
            "contact_first": "Sim", "contact_last": "Buyer",
        })
        check("lead convert -> account+contact+opportunity",
              code == 201 and isinstance(opp, dict) and opp.get("stage") == "QUALIFICATION",
              f"stage={opp.get('stage') if isinstance(opp, dict) else code}")
        code, converted = admin.get(f"/crm/leads/{lead_id}/")
        check("lead marked CONVERTED after conversion",
              code == 200 and isinstance(converted, dict) and converted.get("status") == "CONVERTED",
              str(converted.get("status") if isinstance(converted, dict) else code))

    code, opp2 = admin.post("/crm/opportunities/", {
        "name": "SYN-Sim Chain Deal", "account": account_id,
        "stage": "PROPOSAL", "amount": 12000, "probability": 40,
    })
    check("create opportunity", code in (200, 201), str(code))
    opp_id = opp2.get("id") if isinstance(opp2, dict) else None

    if opp_id:
        code, moved = admin.patch(f"/crm/opportunities/{opp_id}/stage/",
                                  {"stage": "NEGOTIATION"})
        check("opportunity stage PROPOSAL -> NEGOTIATION",
              code == 200 and isinstance(moved, dict) and moved.get("stage") == "NEGOTIATION", str(code))

    code, act = admin.post("/crm/activities/", {
        "activity_type": "MEETING", "subject": "SYN-Sim kickoff meeting",
        "body": "Walked through the refill programme.",
        "contact": contact_id, "account": account_id,
    })
    check("log activity", code in (200, 201), str(code))

    if contact_id:
        code, timeline = admin.get(f"/crm/contacts/{contact_id}/timeline/")
        entries = timeline if isinstance(timeline, list) else []
        check("contact 360 timeline returns entries", code == 200 and len(entries) >= 1,
              f"{len(entries)} entries")

    # consent gate on campaigns: a campaign with NO target tags targets ALL
    # contacts, and the backend must count only consent_marketing=True ones.
    code, camp = admin.post("/crm/campaigns/", {
        "name": "SYN-Sim Promo Campaign", "campaign_type": "PROMO",
    })
    sent = camp.get("sent_count") if isinstance(camp, dict) else None
    check("campaign created with consent-gated sent_count",
          code in (200, 201) and sent is not None,
          f"sent_count={sent} (counts only consent_marketing=True contacts)")
    if sent is not None:
        code, contacts = admin.get("/crm/contacts/?page_size=250")
        rows = contacts.get("results", []) if isinstance(contacts, dict) else contacts
        with_consent = sum(1 for c in rows if c.get("consent_marketing")) if isinstance(rows, list) else "?"
        check("sent_count matches # consenting contacts",
              sent == with_consent, f"endpoint={sent}, contacts w/ consent={with_consent}")


# ---------------------------------------------------------------------------
# 3. dispensing (FEFO)
# ---------------------------------------------------------------------------
def scenario_dispense(admin: Client) -> dict | None:
    section("3. DISPENSE — FEFO workflow")
    code, prods = admin.get("/products/?search=SYN-Amoxicillin")
    rows = prods.get("results", []) if isinstance(prods, dict) else prods
    amox = next((p for p in rows if p.get("name") == "SYN-Amoxicillin 500mg"), None)
    if not check("find SYN-Amoxicillin 500mg", amox is not None):
        return None
    pid = amox["id"]
    soh_before = amox["soh"]

    code, sug = admin.get(f"/lots/fefo_suggestion/?product_id={pid}")
    lots = sug.get("lots", []) if isinstance(sug, dict) else []
    check("FEFO suggestion endpoint", code == 200 and len(lots) >= 2,
          f"{len(lots)} lots; first={lots[0]['batch_number'] if lots else '-'}")
    fefo_order_ok = [l["expiry_date"] for l in lots] == sorted(l["expiry_date"] for l in lots)
    check("FEFO orders by earliest expiry", fefo_order_ok)

    # dispense 200 across lots (A2 has 120 -> must span into A3)
    code, result = admin.post("/lots/dispense/", {
        "product_id": pid, "quantity": 200, "mrn": "SYN-MRN-1001",
    })
    allocs = result.get("allocations", []) if isinstance(result, dict) else []
    check("dispense 200 units (spans 2 lots)", code == 200 and result.get("total_dispensed") == 200,
          f"allocations={[(a['batch_number'], a['qty']) for a in allocs]}" if allocs else str(code))

    code, after = admin.get(f"/products/{pid}/")
    check("SOH reduced by 200", code == 200 and after.get("soh") == soh_before - 200,
          f"{soh_before} -> {after.get('soh') if isinstance(after, dict) else '?'}")

    # audit trail entry
    code, audits = admin.get("/audit/?search=DISPENSE")
    audit_rows = audits if isinstance(audits, list) else []
    entry = next((a for a in audit_rows if a.get("action") == "DISPENSE"
                  and (a.get("details") or {}).get("mrn") == "SYN-MRN-1001"), None)
    check("DISPENSE audit entry recorded", entry is not None,
          f"{len(audit_rows)} DISPENSE entries")

    # over-dispense must 409
    code, err = admin.post("/lots/dispense/", {
        "product_id": pid, "quantity": 10_000_000, "mrn": "SYN-MRN-1001",
    })
    check("over-dispense rejected with 409", code == 409, f"got {code}")

    # ---- BUG PROBE: timeline dispense visibility --------------------------
    code, contacts = admin.get("/crm/contacts/?search=SYN-MRN-1001")
    rows = contacts.get("results", []) if isinstance(contacts, dict) else contacts
    alice = rows[0] if rows else None
    if alice:
        code, tl = admin.get(f"/crm/contacts/{alice['id']}/timeline/")
        entries = tl if isinstance(tl, list) else []
        dispense_entries = [e for e in entries if e.get("type") == "dispense"]
        if not dispense_entries:
            bug("CRM timeline misses dispenses",
                f"contact with MRN SYN-MRN-1001 just had a dispense audited, but "
                f"timeline shows {len(entries)} entries, none of type 'dispense' "
                f"(services.get_timeline filters category='dispense' but "
                f"lots.services writes category='CLINICAL')")
        else:
            check("timeline shows the dispense", True, f"{len(dispense_entries)} dispense entries")
    return {"product_id": pid, "soh_before": soh_before}


# ---------------------------------------------------------------------------
# 4. procurement + order approval flow
# ---------------------------------------------------------------------------
def scenario_procurement(admin: Client) -> None:
    section("4. PROCUREMENT — reorder -> PO -> approval -> SENT")
    code, sugg = admin.get("/orders/procurement-suggestions/?min_stock_only=false")
    groups = sugg if isinstance(sugg, list) else []
    check("procurement suggestions list low-stock products", code == 200 and len(groups) >= 1,
          f"{len(groups)} supplier group(s)")
    if groups:
        names = [i["product_name"] for g in groups for i in g["items"]]
        check("suggestions include SYN stockout/critical products",
              any("SYN-Atorvastatin" in n or "SYN-Metformin" in n or "SYN-Cetirizine" in n for n in names),
              ", ".join(names[:6]))

    # create a PENDING order from suggestions
    if groups:
        g = groups[0]
        items = [{"product": i["product_id"], "quantity": i["recommended_qty"],
                  "unit_cost": i["unit_cost"]} for i in g["items"]]
        code, order = admin.post("/orders/", {
            "supplier": g["supplier_id"], "status": "PENDING",
            "total_cost": g["estimated_total"], "items": items,
        })
        check("create PENDING order from suggestions", code in (200, 201),
              f"{len(items)} item(s), total={g['estimated_total']}")
        order_id = order.get("id") if isinstance(order, dict) else None

        if order_id:
            code, sub = admin.post(f"/orders/{order_id}/submit/")
            check("order submit staged for approval (202)",
                  code == 202 and isinstance(sub, dict) and sub.get("approval_id"),
                  str(code))
            approval_id = sub.get("approval_id") if isinstance(sub, dict) else None

            # non-admins must not approve
            sales = Client("synsales", "e2e-pass-1234")
            if sales.login():
                code, _ = sales.post(f"/approvals/{approval_id}/approve/")
                check("SALES role cannot approve (403)", code == 403, f"got {code}")

            code, appr = admin.post(f"/approvals/{approval_id}/approve/")
            check("admin approves ORDER_SUBMIT", code == 200, str(code))

            code, sent_order = admin.get(f"/orders/{order_id}/")
            check("order status PENDING -> SENT after approval",
                  code == 200 and sent_order.get("status") == "SENT",
                  str(sent_order.get("status") if isinstance(sent_order, dict) else code))

            code, audits = admin.get("/audit/?search=ORDER_SENT")
            rows = audits if isinstance(audits, list) else []
            check("ORDER_SENT audit entry", any(a.get("action") == "ORDER_SENT" for a in rows),
                  f"{len(rows)} entries")

            # double-approve must fail
            code, again = admin.post(f"/approvals/{approval_id}/approve/")
            check("double-approve rejected (400)", code == 400, f"got {code}")

    # reject flow with a reason
    if not groups:
        print("  [info] skipping reject-flow (no supplier groups available)")
        return
    code, order2 = admin.post("/orders/", {
        "supplier": groups[0]["supplier_id"],
        "status": "PENDING", "total_cost": 10.0,
        "items": [],
    })
    order2_id = order2.get("id") if isinstance(order2, dict) else None
    if order2_id:
        code, sub2 = admin.post(f"/orders/orders/{order2_id}/submit/")
        appr2 = sub2.get("approval_id") if isinstance(sub2, dict) else None
        if appr2:
            code, rej = admin.post(f"/approvals/{appr2}/reject/", {"reason": "Simulated: wrong supplier selected"})
            check("reject with reason accepted", code == 200, str(code))
            code, detail = admin.get(f"/approvals/{appr2}/")
            stored = detail.get("reason") if isinstance(detail, dict) else None
            check("rejection reason stored", stored == "Simulated: wrong supplier selected",
                  f"stored={stored!r}")


# ---------------------------------------------------------------------------
# 5. AI ingest
# ---------------------------------------------------------------------------
def scenario_ingest(admin: Client) -> None:
    section("5. AI INGEST — invoice upload -> poll -> commit -> approve")
    invoice_text = open(os.path.join(INVOICE_DIR, "invoice_1_medicorp.txt"), encoding="utf-8").read()

    code, up = admin.post("/ingest/", {"text": invoice_text, "doc_type": "supplier_invoice"})
    task_id = up.get("task_id") if isinstance(up, dict) else None
    check("upload invoice (task_id returned)",
          code in (200, 202) and task_id is not None,
          f"status={up.get('status') if isinstance(up, dict) else code}")
    if task_id is None:
        bug("ingest upload returned no task_id", f"code={code} body={up}")
        return

    code, st = admin.get(f"/ingest/{task_id}/status/")
    body = st.get("data") if isinstance(st, dict) and isinstance(st.get("data"), dict) else st
    succeeded = body.get("succeeded") if isinstance(body, dict) else None
    check("poll /ingest/{task_id}/status/", code == 200 and succeeded is not None,
          f"status={st.get('status') if isinstance(st, dict) else code}, succeeded={succeeded}")

    if succeeded is False:
        err = body.get("error_message") if isinstance(body, dict) else None
        print(f"  [info] ingest failed as expected without LLM keys: {str(err)[:160]}")

    # ---- BUG PROBE: per-task polling (two distinct uploads) ----------------
    # Each upload must later poll back to ITS OWN audit row.
    text2 = open(os.path.join(INVOICE_DIR, "invoice_2_pharmadirect.txt"), encoding="utf-8").read()
    code, up2 = admin.post("/ingest/", {"text": text2, "doc_type": "supplier_invoice"})
    task_id2 = up2.get("task_id") if isinstance(up2, dict) else None
    if task_id2:
        code1, st1 = admin.get(f"/ingest/{task_id}/status/")
        code2, st2 = admin.get(f"/ingest/{task_id2}/status/")
        b1 = st1.get("data") if isinstance(st1, dict) and isinstance(st1.get("data"), dict) else st1
        b2 = st2.get("data") if isinstance(st2, dict) and isinstance(st2.get("data"), dict) else st2
        id1 = b1.get("id") if isinstance(b1, dict) else None
        id2 = b2.get("id") if isinstance(b2, dict) else None
        if id1 and id2 and id1 != id2:
            check("per-task polling returns each upload's own audit", True,
                  f"audit {str(id1)[:8]}... vs {str(id2)[:8]}...")
        else:
            bug("per-task ingest polling is broken",
                f"two different uploads polled by task_id returned the same audit "
                f"row ({id1}) — the task-specific endpoint ignores task_id")
    else:
        bug("second ingest upload returned no task_id", str(up2)[:200])

    # commit workflow (uses seeded successful synthetic audit)
    audit_id = load_synthetic_audit_id()
    if audit_id:
        code, com = admin.post("/ingest/commit/", {"audit_id": audit_id})
        check("commit staged AI_COMMIT approval (202)",
              code == 202 and isinstance(com, dict) and com.get("approval_id"), str(code))
        appr_id = com.get("approval_id") if isinstance(com, dict) else None
        if appr_id:
            # capture SOH before approval to verify the fix later
            code, prods = admin.get("/products/?search=SYN-Amoxicillin")
            rows = prods.get("results", []) if isinstance(prods, dict) else prods
            amox_before = next((p["soh"] for p in rows if p.get("name") == "SYN-Amoxicillin 500mg"), None)

            code, appr = admin.post(f"/approvals/{appr_id}/approve/")
            check("admin approves AI_COMMIT", code == 200, str(code))

            code, prods_after = admin.get("/products/?search=SYN-Amoxicillin")
            rows_after = prods_after.get("results", []) if isinstance(prods_after, dict) else prods_after
            amox_after = next((p["soh"] for p in rows_after if p.get("name") == "SYN-Amoxicillin 500mg"), None)
            if amox_before is not None and amox_after == amox_before:
                bug("AI commit does not update inventory",
                    f"approved AI_COMMIT for invoice with 500 units of "
                    f"SYN-Amoxicillin 500mg; product SOH unchanged ({amox_before} -> {amox_after}); "
                    f"commit_ingestion only writes an AuditLog, no Lots created")
            else:
                check("AI commit created lots + updated SOH",
                      amox_after is not None and amox_after > (amox_before or 0),
                      f"SOH {amox_before} -> {amox_after}")

            code, audits = admin.get("/audit/?search=AI_INGEST_COMMIT")
            rows = audits if isinstance(audits, list) else []
            check("AI_INGEST_COMMIT audit entry", len(rows) >= 1, f"{len(rows)} entries")

    # malformed doc still handled gracefully
    bad_text = open(os.path.join(INVOICE_DIR, "invoice_3_malformed.txt"), encoding="utf-8").read()
    code, up2 = admin.post("/ingest/", {"text": bad_text})
    check("malformed doc upload accepted (graceful)",
          code in (200, 202), str(code))


# ---------------------------------------------------------------------------
# 6. notification scans
# ---------------------------------------------------------------------------
def scenario_notifications(admin: Client) -> None:
    section("6. NOTIFICATIONS — nightly scans (run in-process via run_scans.py)")
    import subprocess
    r = subprocess.run([sys.executable, "run_scans.py"],
                       capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)),
                       timeout=300, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = (r.stdout or "") + (r.stderr or "")
    print("  " + out.strip().replace("\n", "\n  "))

    code, unread = admin.get("/notifications/unread_count/")
    count = unread.get("unread_count") if isinstance(unread, dict) else None
    check("notifications generated by scans", code == 200 and (count or 0) > 0,
          f"unread_count={count}")

    code, notifs = admin.get("/notifications/")
    rows = notifs.get("results", []) if isinstance(notifs, dict) else notifs
    kinds = sorted({n.get("notif_type") for n in rows}) if isinstance(rows, list) else []
    check("expected notification kinds present",
          any(k in kinds for k in ("EXPIRY_WARNING", "REORDER", "STOCKOUT", "REFILL_DUE", "TASK_DUE")),
          f"kinds={kinds}")

    # Auto-lock check via the lots API (idempotent across re-runs; the
    # notification itself may have scrolled past the first page of /notifications/).
    code, syn_lots = admin.get("/lots/?search=SYN-BATCH-A1")
    lot_rows = syn_lots.get("results", []) if isinstance(syn_lots, dict) else syn_lots
    a1 = next((l for l in lot_rows if l.get("batch_number") == "SYN-BATCH-A1"), None)
    if a1 is not None and a1.get("is_locked"):
        check("expired lot SYN-BATCH-A1 is auto-locked by scan", True,
              f"is_locked={a1.get('is_locked')}")
    elif a1 is None:
        bug("seeded expired lot missing", "SYN-BATCH-A1 not returned by /lots/?search=SYN-BATCH-A1")
    else:
        bug("expired lots not auto-locked by scan",
            "SYN-BATCH-A1 expired 10 days ago but scan_expiries left it unlocked")

    # mark one read then read_all
    if rows:
        first = rows[0]
        code, _ = admin.patch(f"/notifications/{first['id']}/read/")
        check("mark single notification read", code == 200, str(code))
    code, after = admin.patch("/notifications/read_all/")
    check("read_all", code == 200, str(code))
    code, unread2 = admin.get("/notifications/unread_count/")
    check("unread_count zero after read_all",
          isinstance(unread2, dict) and unread2.get("unread_count") == 0,
          str(unread2))


# ---------------------------------------------------------------------------
# 7. audit + dashboard
# ---------------------------------------------------------------------------
def scenario_dashboard(admin: Client) -> None:
    section("7. AUDIT + DASHBOARD")
    code, audits = admin.get("/audit/?search=DISPENSE")
    rows = audits if isinstance(audits, list) else []
    check("audit search works", code == 200 and len(rows) >= 1, f"{len(rows)} DISPENSE rows")

    code, summ = admin.get("/dashboard/summary/")
    s = summ if isinstance(summ, dict) else {}
    checks = {
        "total_products": s.get("total_products", 0) >= 8,
        "stockout_products": s.get("stockout_products", 0) >= 1,
        "pending_approvals is int": isinstance(s.get("pending_approvals"), int),
        "pipeline_value > 0": s.get("pipeline_value", 0) > 0,
        "total_contacts >= 6": s.get("total_contacts", 0) >= 6,
    }
    for label, ok in checks.items():
        check(f"dashboard.{label}", ok, str(s.get(label.split('.')[0] if '.' in label else label, "?"))[:40])


# ---------------------------------------------------------------------------
def main() -> None:
    print(f"HDAOS usage simulation — {BASE}")
    admin = scenario_auth()
    scenario_crm(admin)
    scenario_dispense(admin)
    scenario_procurement(admin)
    scenario_ingest(admin)
    scenario_notifications(admin)
    scenario_dashboard(admin)

    print(f"\n{'=' * 72}\nRESULT: {PASS} passed, {FAIL} failed, {len(BUGS)} bugs found\n{'=' * 72}")
    if BUGS:
        print("\nBUGS CONFIRMED BY SIMULATION:")
        for i, b in enumerate(BUGS, 1):
            print(f"  {i}. {b}")
    # exit code 0 even with bugs: bugs are findings, not script crashes
    sys.exit(0)


if __name__ == "__main__":
    main()
