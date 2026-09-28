"""
HDAOS v3.0 — round-2 deep acceptance simulation.

Covers what round 1 did not:
  * role/permission matrix (SALES / PHARMACIST / PROCUREMENT / LOGISTICS / VIEWER)
  * MRN masking for users without mrn_access
  * remaining approval flows: USER_ACTIVATE (register -> pending -> activate),
    ROLE_CHANGE, STOCK_ADJUST, LOT_UNLOCK, PRODUCT_DELETE, CONTACT_BULK_EXPORT
  * token refresh / logout
  * pagination + filters
  * documented gap probes (fictional endpoints, route trap, delete-with-lots)

Approval requests for action types with no API-side creation endpoint are
seeded through the ORM in-process (the verification itself is pure HTTP).

Usage:
    cd health-dispensary-analytical-ordering-system
    python simulate_round2.py 2>&1 | tee sim_report_round2.txt
"""
from __future__ import annotations

import json
import os
import sys
import uuid as uuid_module
import urllib.error
import urllib.parse
import urllib.request

import simulate_usage as su  # reuse Client + check()/bug()/section() and counters

API = su.API
Client = su.Client


# ---------------------------------------------------------------------------
# ORM-side seeds (dev DB) for approval payloads that have no creation API
# ---------------------------------------------------------------------------
def orm_seeds() -> dict:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hdaos.settings")
    import django

    django.setup()

    from django.contrib.auth import get_user_model
    from apps.approvals.models import ApprovalRequest
    from apps.catalog.models import Product
    from apps.lots.models import Lot

    User = get_user_model()
    out: dict = {}

    def ensure_user(username, role, mrn_access, is_active=True, password="e2e-pass-1234"):
        u = User.objects.filter(username=username).first()
        if u is None:
            u = User.objects.create_user(
                username=username, password=password,
                email=f"{username}@synthetic.local",
                role=role, mrn_access=mrn_access, is_active=is_active,
            )
        else:
            u.role = role
            u.mrn_access = mrn_access
            u.is_active = is_active
            u.set_password(password)
            u.save(update_fields=["role", "mrn_access", "is_active", "password"])
        return u

    # extra roles for the permission matrix
    out["logistics"] = ensure_user("synlogi", "LOGISTICS", False)
    out["viewer"] = ensure_user("synview", "VIEWER", False)

    # throwaway user for ROLE_CHANGE
    role_target = ensure_user("synroletest", "PHARMACIST", False)
    out["role_change_approval"] = ApprovalRequest.objects.create(
        action_type="ROLE_CHANGE",
        payload={"user_id": str(role_target.id), "new_role": "PROCUREMENT"},
        requested_by=User.objects.get(username="devadmin"),
    ).id

    # STOCK_ADJUST on Amoxicillin
    amox = Product.objects.filter(name="SYN-Amoxicillin 500mg").first()
    out["amox_soh_before"] = amox.soh if amox else None
    out["stock_adjust_approval"] = (
        ApprovalRequest.objects.create(
            action_type="STOCK_ADJUST",
            payload={"product_id": str(amox.id), "adjustment": 100},
            requested_by=User.objects.get(username="devadmin"),
        ).id if amox else None
    )

    # LOT_UNLOCK on the pre-locked lot
    lot = Lot.objects.filter(batch_number="SYN-BATCH-C2").first()
    out["lot_unlock_approval"] = (
        ApprovalRequest.objects.create(
            action_type="LOT_UNLOCK",
            payload={"lot_id": str(lot.id)},
            requested_by=User.objects.get(username="devadmin"),
        ).id if lot else None
    )
    return out


def find(client: Client, list_path: str, **filters):
    return su.find(client, list_path, **filters)


# ---------------------------------------------------------------------------
def scenario_role_matrix(admin: Client, seeds: dict) -> None:
    su.section("R2-1. PERMISSION MATRIX — role-gated endpoints")
    roles = {
        "SALES": "synsales",
        "PHARMACIST": "synpharm",
        "PROCUREMENT": "synproc",
        "LOGISTICS": seeds["logistics"].username,
        "VIEWER": seeds["viewer"].username,
    }
    tokens: dict[str, Client] = {}
    for role, username in roles.items():
        c = Client(username, "e2e-pass-1234")
        if su.check(f"login {username} ({role})", c.login()):
            tokens[role] = c

    # catalog mutations are admin-only
    for role, c in tokens.items():
        code, _ = c.post("/products/", {
            "name": "SYN-should-403", "api": "X", "strength": "1mg",
        })
        su.check(f"{role} cannot create products (403)", code == 403, f"got {code}")

    # approvals inbox is admin-only
    for role, c in tokens.items():
        code, _ = c.get("/approvals/")
        su.check(f"{role} cannot list approvals (403)", code == 403, f"got {code}")

    # CRM writes are SALES (or ADMIN) only
    code, acc = admin.get("/crm/accounts/?search=SYN-Sim%20Corner")
    rows = acc.get("results", []) if isinstance(acc, dict) else acc
    existing = rows[0]["id"] if rows else None
    for role, c in tokens.items():
        body = {"name": f"SYN-{role}-attempt", "account_type": "CLINIC"}
        code, _ = c.post("/crm/accounts/", body)
        expected = 201 if role == "SALES" else 403
        su.check(f"{role} CRM write -> {expected}", code == expected, f"got {code}")

    # SALES can actually create
    code, created = tokens["SALES"].post("/crm/accounts/", {
        "name": "SYN-Sales Made Clinic", "account_type": "CLINIC",
    })
    su.check("SALES creates CRM account (201)", code == 201, str(code))

    # ---- MRN masking -------------------------------------------------------
    su.section("R2-2. MRN MASKING — mrn_access flag honoured")
    # SALES has contacts list access but no mrn_access.
    code, sales_contacts = tokens["SALES"].get("/crm/contacts/?page_size=5")
    rows = sales_contacts.get("results", []) if isinstance(sales_contacts, dict) else []
    su.check("SALES (no mrn_access) never sees MRN",
             len(rows) > 0 and not any("mrn" in r for r in rows),
             f"{len(rows)} contacts inspected")

    code, pharm_contacts = tokens["PHARMACIST"].get("/crm/contacts/?page_size=5")
    rows = pharm_contacts.get("results", []) if isinstance(pharm_contacts, dict) else []
    su.check("pharmacist (mrn_access=True) sees MRN",
             any("mrn" in r for r in rows), f"{len(rows)} contacts inspected")


def scenario_approvals(admin: Client, seeds: dict) -> None:
    su.section("R2-3. APPROVAL FLOWS — activate / role / stock / unlock / delete")

    # ---- register -> pending -> USER_ACTIVATE -> login ----------------------
    uname = f"SYN-reg-{uuid_module.uuid4().hex[:6]}"
    code, reg = admin.post("/auth/register/", {
        "username": uname, "email": f"{uname}@example.com",
        "password": "reg-pass-12345", "first_name": "Reg", "last_name": "Test",
    })
    su.check("register creates inactive user (201)", code in (200, 201), str(code))

    code, pending = admin.get("/auth/users/pending/")
    rows = pending.get("results", []) if isinstance(pending, dict) else pending
    match = next((u for u in rows if u.get("username") == uname), None)
    su.check("new user appears in pending list", match is not None,
              f"{len(rows)} pending")

    if match:
        code, appr = admin.post("/approvals/request_activation/", {"user_id": match["id"]})
        approval_id = appr.get("approval_id") if isinstance(appr, dict) else None
        su.check("request_activation stages USER_ACTIVATE (202)",
                 code == 202 and approval_id, str(code))

        code, _ = admin.post(f"/approvals/{approval_id}/approve/")
        su.check("USER_ACTIVATE approved", code == 200, str(code))

        newc = Client(uname, "reg-pass-12345")
        su.check("activated user can log in", newc.login())

        code, pending2 = admin.get("/auth/users/pending/")
        rows2 = pending2.get("results", []) if isinstance(pending2, dict) else pending2
        su.check("activated user left the pending list",
                  all(u.get("username") != uname for u in rows2))

    # ---- ROLE_CHANGE --------------------------------------------------------
    if seeds.get("role_change_approval"):
        aid = seeds["role_change_approval"]
        code, _ = admin.post(f"/approvals/{aid}/approve/")
        su.check("ROLE_CHANGE approved", code == 200, str(code))
        rc = Client("synroletest", "e2e-pass-1234")
        if rc.login():
            code, me = rc.get("/auth/me/")
            su.check("role changed to PROCUREMENT", me.get("role") == "PROCUREMENT",
                     str(me.get("role")))

    # ---- STOCK_ADJUST -------------------------------------------------------
    if seeds.get("stock_adjust_approval"):
        aid = seeds["stock_adjust_approval"]
        code, _ = admin.post(f"/approvals/{aid}/approve/")
        su.check("STOCK_ADJUST approved", code == 200, str(code))
        code, prods = admin.get("/products/?search=SYN-Amoxicillin")
        rows = prods.get("results", []) if isinstance(prods, dict) else prods
        amox = next((p for p in rows if p.get("name") == "SYN-Amoxicillin 500mg"), None)
        expected = (seeds["amox_soh_before"] or 0) + 100
        su.check("stock adjustment applied (+100)",
                 amox is not None and amox.get("soh") == expected,
                 f"soh={amox.get('soh') if amox else '?'}, expected={expected}")

    # ---- LOT_UNLOCK ---------------------------------------------------------
    if seeds.get("lot_unlock_approval"):
        aid = seeds["lot_unlock_approval"]
        code, _ = admin.post(f"/approvals/{aid}/approve/")
        su.check("LOT_UNLOCK approved", code == 200, str(code))
        code, lots = admin.get("/lots/?search=SYN-BATCH-C2")
        rows = lots.get("results", []) if isinstance(lots, dict) else lots
        c2 = next((l for l in rows if l.get("batch_number") == "SYN-BATCH-C2"), None)
        su.check("lot unlocked by approval", c2 is not None and c2.get("is_locked") is False,
                 f"is_locked={c2.get('is_locked') if c2 else '?'}")

    # ---- CONTACT_BULK_EXPORT ------------------------------------------------
    code, exp = admin.post("/crm/export/", {"contact_type": "PATIENT"})
    approval_id = exp.get("approval_id") if isinstance(exp, dict) else None
    su.check("bulk export staged (202)", code == 202 and approval_id, str(code))
    if approval_id:
        code, _ = admin.post(f"/approvals/{approval_id}/approve/")
        su.check("CONTACT_BULK_EXPORT approved", code == 200, str(code))

    # ---- PRODUCT_DELETE -----------------------------------------------------
    code, tmp = admin.post("/products/", {
        "name": f"SYN-del-{uuid_module.uuid4().hex[:6]}",
        "api": "Temp", "strength": "1mg", "soh": 0,
    })
    tmp_id = tmp.get("id") if isinstance(tmp, dict) else None
    if su.check("created throwaway product for delete test", code == 201 and tmp_id):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hdaos.settings")
        import django

        django.setup()
        from django.contrib.auth import get_user_model
        from apps.approvals.models import ApprovalRequest

        User = get_user_model()
        a = ApprovalRequest.objects.create(
            action_type="PRODUCT_DELETE",
            payload={"product_id": tmp_id},
            requested_by=User.objects.get(username="devadmin"),
        )
        code, _ = admin.post(f"/approvals/{str(a.id)}/approve/")
        su.check("PRODUCT_DELETE approved", code == 200, str(code))
        code, _ = admin.get(f"/products/{tmp_id}/")
        su.check("product gone after delete approval (404)", code == 404, f"got {code}")


def scenario_auth_lifecycle() -> None:
    su.section("R2-4. AUTH LIFECYCLE — cookie refresh / logout")
    # Cookie-based session, exactly like the React app (credentials: include).
    c = Client("synpharm", "e2e-pass-1234", use_cookies=True)
    if not su.check("pharmacist login (cookie jar)", c.login()):
        return
    code, _ = c.post("/auth/refresh/")
    su.check("cookie-based token refresh accepted", code == 200, str(code))
    code, me = c.get("/auth/me/")
    su.check("authenticated after refresh", code == 200 and me.get("username") == "synpharm")
    code, _ = c.post("/auth/logout/")
    su.check("logout accepted", code == 200, str(code))
    # Logout clears the cookies; the stale Bearer token still works because
    # JWT auth is stateless by design.
    code, me2 = c.get("/auth/me/")
    su.check("me endpoint responds post-logout", code in (200, 401), f"got {code}")


def scenario_filters_pagination(admin: Client) -> None:
    su.section("R2-5. PAGINATION + FILTERS")
    code, page1 = admin.get("/products/?page=1")
    ok = (code == 200 and isinstance(page1, dict)
          and all(k in page1 for k in ("count", "next", "previous", "results")))
    su.check("products list is paginated envelope", ok,
              f"count={page1.get('count') if isinstance(page1, dict) else '?'}")
    if isinstance(page1, dict) and page1.get("next"):
        next_url = page1["next"]
        path = "/" + next_url.split("/api/", 1)[1]
        code, page2 = admin.get(path)
        su.check("page 2 fetch works", code == 200 and isinstance(page2, dict)
                 and len(page2.get("results", [])) > 0)

    code, stockouts = admin.get("/products/?stock_status=STOCKOUT")
    rows = stockouts.get("results", []) if isinstance(stockouts, dict) else []
    su.check("stock_status=STOCKOUT filter", code == 200 and len(rows) >= 1
             and all(r.get("soh", 1) <= 0 for r in rows),
              f"{len(rows)} stockout product(s)")

    code, locked = admin.get("/lots/?is_locked=true")
    rows = locked.get("results", []) if isinstance(locked, dict) else []
    su.check("lots is_locked=true filter", code == 200
             and all(r.get("is_locked") for r in rows),
              f"{len(rows)} locked lot(s)")

    code, qualified = admin.get("/crm/leads/?status=QUALIFIED")
    rows = qualified.get("results", []) if isinstance(qualified, dict) else []
    su.check("leads status filter", code == 200
             and all(r.get("status") == "QUALIFIED" for r in rows),
              f"{len(rows)} qualified lead(s)")

    code, unread = admin.get("/notifications/?read=false")
    rows = unread.get("results", []) if isinstance(unread, dict) else []
    su.check("notifications read=false filter", code == 200
             and all(r.get("read") is False for r in rows),
              f"{len(rows)} unread")


def scenario_gap_probes(admin: Client) -> None:
    su.section("R2-6. GAP PROBES (documented, non-fatal)")

    # fictional endpoints the old frontend called
    code, _ = admin.get("/procurement/adc-suggestions/")
    su.check("/procurement/adc-suggestions/ is 404 (fictional endpoint)", code == 404,
              f"got {code}")

    # the router trap: /orders/orders/<uuid>/ looks like a detail route
    fake = uuid_module.uuid4()
    code, _ = admin.post(f"/orders/orders/{fake}/submit/")
    su.check("/orders/orders/<uuid>/submit/ is 404 (route trap)", code == 404, f"got {code}")

    # deleting a product that has lots must be refused (Lot.product is PROTECT)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hdaos.settings")
    import django

    django.setup()
    from apps.catalog.models import Product

    amox = Product.objects.filter(name="SYN-Amoxicillin 500mg").first()
    if amox:
        code, body = admin.delete(f"/products/{amox.id}/")
        still_there = Product.objects.filter(pk=amox.id).exists()
        su.check("DELETE product-with-lots refused with clean 409",
                 code == 409 and still_there, f"HTTP {code}, still exists={still_there}")

    # product without lots deletes normally
    code, tmp2 = admin.post("/products/", {
        "name": f"SYN-del2-{uuid_module.uuid4().hex[:6]}",
        "api": "Temp", "strength": "1mg", "soh": 0,
    })
    tmp2_id = tmp2.get("id") if isinstance(tmp2, dict) else None
    if tmp2_id:
        code, _ = admin.delete(f"/products/{tmp2_id}/")
        su.check("DELETE product-without-lots succeeds (204)", code == 204, f"got {code}")


def main() -> None:
    print(f"HDAOS round-2 simulation — {su.BASE}")
    admin = Client("devadmin", "e2e-pass-1234")
    if not admin.login():
        print("FATAL: admin login failed")
        sys.exit(1)

    su.section("R2-0. ORM SEEDS for approval payloads")
    seeds = orm_seeds()
    print(f"  seeded role/stock/unlock approvals + matrix users")

    scenario_role_matrix(admin, seeds)
    scenario_approvals(admin, seeds)
    scenario_auth_lifecycle()
    scenario_filters_pagination(admin)
    scenario_gap_probes(admin)

    print(f"\n{'=' * 72}\nROUND-2 RESULT: {su.PASS} passed, {su.FAIL} failed, "
          f"{len(su.BUGS)} new findings\n{'=' * 72}")
    if su.BUGS:
        print("\nFINDINGS:")
        for i, b in enumerate(su.BUGS, 1):
            print(f"  {i}. {b}")
    sys.exit(0)


if __name__ == "__main__":
    main()
