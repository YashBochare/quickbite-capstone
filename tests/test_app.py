import os
os.environ["QUICKBITE_NO_AUTOAPP"] = "1"
from main import create_app, MemoryStore


def client():
    return create_app(MemoryStore()).test_client()


def test_health():
    assert client().get("/health").get_json()["status"] == "ok"


def test_menu_has_items():
    menu = client().get("/api/menu").get_json()
    assert len(menu) == 5 and all(m["price"] > 0 for m in menu)


def test_place_and_fetch_order():
    c = client()
    res = c.post("/api/orders", json={"customer": "Asha", "items": [{"id": "m2", "qty": 2}, {"id": "m5"}]})
    assert res.status_code == 201
    order = res.get_json()
    assert order["total"] == 279 * 2 + 79 and order["status"] == "PLACED"
    assert c.get(f"/api/orders/{order['order_id']}").get_json()["customer"] == "Asha"


def test_rejects_missing_customer():
    assert client().post("/api/orders", json={"items": [{"id": "m1"}]}).status_code == 400


def test_rejects_unknown_item_and_bad_qty():
    c = client()
    assert c.post("/api/orders", json={"customer": "A", "items": [{"id": "zz"}]}).status_code == 400
    assert c.post("/api/orders", json={"customer": "A", "items": [{"id": "m1", "qty": 99}]}).status_code == 400


def test_unknown_order_404():
    assert client().get("/api/orders/nope").status_code == 404


def test_home_page():
    res = client().get("/")
    assert res.status_code == 200 and b"QuickBite" in res.data


def test_order_has_delivery_estimate():
    o = client().post("/api/orders", json={"customer": "Dev", "items": [{"id": "m1", "qty": 3}]}).get_json()
    assert o["eta_minutes"] == 35
