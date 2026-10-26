"""QuickBite - food ordering service (Experiment 8 capstone).

Orders are stored in Amazon DynamoDB when ORDERS_TABLE is set; otherwise in memory
(local development and unit tests).
"""
import os
import socket
import time
import uuid
from decimal import Decimal

from flask import Flask, jsonify, render_template, request

APP_VERSION = os.environ.get("APP_VERSION", "dev")
BUILD = os.environ.get("BUILD_NUMBER", "local")

MENU = [
    {"id": "m1", "name": "Paneer Tikka Wrap", "price": 189, "veg": True},
    {"id": "m2", "name": "Chicken Biryani", "price": 279, "veg": False},
    {"id": "m3", "name": "Masala Dosa", "price": 129, "veg": True},
    {"id": "m4", "name": "Veg Hakka Noodles", "price": 169, "veg": True},
    {"id": "m5", "name": "Mango Lassi", "price": 79, "veg": True},
]
MENU_BY_ID = {m["id"]: m for m in MENU}
STATUSES = ["PLACED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"]


class MemoryStore:
    def __init__(self):
        self.items = {}

    def put(self, order):
        self.items[order["order_id"]] = order

    def get(self, order_id):
        return self.items.get(order_id)

    def recent(self, limit=10):
        return sorted(self.items.values(), key=lambda o: o["created_at"], reverse=True)[:limit]


class DynamoStore:
    def __init__(self, table_name):
        import boto3
        self.table = boto3.resource("dynamodb").Table(table_name)

    def put(self, order):
        self.table.put_item(Item={**order, "total": Decimal(str(order["total"])),
                                  "items": [{**i, "price": Decimal(str(i["price"]))} for i in order["items"]]})

    def get(self, order_id):
        item = self.table.get_item(Key={"order_id": order_id}).get("Item")
        return _plain(item) if item else None

    def recent(self, limit=10):
        items = self.table.scan(Limit=50).get("Items", [])
        return sorted((_plain(i) for i in items), key=lambda o: o["created_at"], reverse=True)[:limit]


def _plain(value):
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    return value


def create_app(store=None):
    app = Flask(__name__)
    table = os.environ.get("ORDERS_TABLE")
    store = store or (DynamoStore(table) if table else MemoryStore())

    @app.get("/health")
    def health():
        return jsonify(status="ok", version=APP_VERSION, build=BUILD)

    @app.get("/api/menu")
    def menu():
        return jsonify(MENU)

    @app.post("/api/orders")
    def place_order():
        body = request.get_json(silent=True) or {}
        customer = str(body.get("customer", "")).strip()
        lines = body.get("items") or []
        if not customer or len(customer) > 60:
            return jsonify(error="customer name is required (max 60 chars)"), 400
        if not isinstance(lines, list) or not lines:
            return jsonify(error="at least one item is required"), 400
        items = []
        for line in lines:
            item = MENU_BY_ID.get(str(line.get("id")))
            qty = line.get("qty", 1)
            if item is None or not isinstance(qty, int) or not 1 <= qty <= 20:
                return jsonify(error="invalid menu item or quantity"), 400
            items.append({"id": item["id"], "name": item["name"], "price": item["price"], "qty": qty})
        order = {
            "order_id": uuid.uuid4().hex[:10],
            "customer": customer,
            "items": items,
            "total": sum(i["price"] * i["qty"] for i in items),
            "status": STATUSES[0],
            "created_at": int(time.time()),
        }
        store.put(order)
        return jsonify(order), 201

    @app.get("/api/orders/<order_id>")
    def get_order(order_id):
        order = store.get(order_id)
        if order is None:
            return jsonify(error="order not found"), 404
        return jsonify(order)

    @app.get("/")
    def index():
        return render_template("index.html", menu=MENU, orders=store.recent(),
                               version=APP_VERSION, build=BUILD, host=socket.gethostname(),
                               storage="Amazon DynamoDB" if table else "In-memory (dev)")

    return app


app = create_app() if os.environ.get("QUICKBITE_NO_AUTOAPP") is None else None
