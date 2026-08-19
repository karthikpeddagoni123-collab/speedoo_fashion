"""Owner-only routes for managing the single-owner Speedoo Fashion store.

Every view is guarded by ``@owner_required`` which returns **403
Forbidden** to anyone who is not the single authorized owner — even a
logged-in customer (§5 and §6 of the spec).
"""
from __future__ import annotations

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, session, url_for,
)

import orders as orders_mod
import products as products_mod
from config import CATEGORIES, ORDER_STATUSES
from decorators import owner_required
from owner_auth import authenticate_owner


owner_bp = Blueprint("owner", __name__, url_prefix="/owner")


# =====================================================================
# Login / Logout
# =====================================================================

@owner_bp.route("/login", methods=["GET", "POST"])
def owner_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if authenticate_owner(username, password):
            session.clear()
            session["role"] = "owner"
            session["owner_id"] = 1
            session["username"] = username
            flash("Welcome back, Owner.", "success")
            return redirect(url_for("owner.dashboard"))
        flash("Invalid owner credentials.", "error")
    return render_template("owner/login.html")


@owner_bp.post("/logout")
@owner_required
def owner_logout():
    session.clear()
    flash("Owner logged out.", "info")
    return redirect(url_for("customer.landing"))


# =====================================================================
# Dashboard
# =====================================================================

@owner_bp.get("/dashboard")
@owner_required
def dashboard():
    products = products_mod.list_products()
    orders = orders_mod.list_all_orders()
    delivered = [o for o in orders if o["status"] == "Delivered"]
    in_process = [o for o in orders if o["status"] not in ("Delivered", "Cancelled")]
    revenue = sum(float(o["total"]) for o in delivered)
    return render_template(
        "owner/dashboard.html",
        product_count=len(products),
        order_count=len(orders),
        in_process=len(in_process),
        revenue=round(revenue, 2),
        latest=products[:8],
    )


# =====================================================================
# Products (list, add, edit, delete)
# =====================================================================

@owner_bp.get("/products")
@owner_required
def products_list():
    rows = products_mod.list_products()
    annotated = [
        {**dict(p), "sizes": products_mod.list_sizes(p["id"]),
         "total_stock": products_mod.total_stock(p["id"])}
        for p in rows
    ]
    return render_template("owner/products.html", products=annotated)


@owner_bp.route("/products/add", methods=["GET", "POST"])
@owner_required
def product_add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "0").strip()
        sizes_raw = request.form.get("sizes", "").strip()
        photo = request.files.get("photo")

        errors = []
        if not name:
            errors.append("Product name is required.")
        if category not in CATEGORIES:
            errors.append("Pick a valid category.")
        try:
            price_f = float(price)
        except ValueError:
            price_f = 0
        if price_f <= 0:
            errors.append("Price must be greater than zero.")
        if not sizes_raw:
            errors.append("Provide at least one size with stock.")

        from uploads import save_image
        image_file = None
        if photo is None or photo.filename == "":
            errors.append("Please upload a product photo.")
        else:
            try:
                image_file = save_image(photo)
            except ValueError as exc:
                errors.append(str(exc))

        sizes = []
        for line in sizes_raw.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            size, _, qty = line.partition(":")
            size = size.strip()
            try:
                qty_i = int(qty)
            except ValueError:
                qty_i = -1
            if size and qty_i >= 0:
                sizes.append((size, qty_i))
        if sizes_raw and not sizes:
            errors.append("Sizes must be of the form 'M: 10', one per line.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "owner/product_form.html",
                categories=CATEGORIES, mode="add",
                form={
                    "name": name, "category": category, "description": description,
                    "price": price_f, "sizes_raw": sizes_raw,
                },
            )

        pid = products_mod.create_product(
            name=name, category=category, description=description,
            price=price_f, image_file=image_file, sizes=sizes,
        )
        flash(f"Product '{name}' published.", "success")
        return redirect(url_for("owner.products_list") + f"#p-{pid}")

    return render_template(
        "owner/product_form.html",
        categories=CATEGORIES, mode="add",
        form={"name": "", "category": CATEGORIES[0], "description": "",
              "price": 0.0, "sizes_raw": "S: 10\nM: 10\nL: 10"},
    )


@owner_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@owner_required
def product_edit(product_id: int):
    product = products_mod.get_product(product_id)
    if product is None:
        abort(404)
    sizes = products_mod.list_sizes(product_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "0").strip()
        sizes_raw = request.form.get("sizes", "").strip()
        photo = request.files.get("photo")

        errors = []
        if not name:
            errors.append("Product name is required.")
        if category not in CATEGORIES:
            errors.append("Pick a valid category.")
        try:
            price_f = float(price)
        except ValueError:
            price_f = 0
        if price_f <= 0:
            errors.append("Price must be greater than zero.")

        from uploads import delete_image, save_image
        new_image = None
        if photo and photo.filename:
            try:
                new_image = save_image(photo)
            except ValueError as exc:
                errors.append(str(exc))

        new_sizes = []
        for line in sizes_raw.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            size, _, qty = line.partition(":")
            size = size.strip()
            try:
                qty_i = int(qty)
            except ValueError:
                qty_i = -1
            if size and qty_i >= 0:
                new_sizes.append((size, qty_i))
        if sizes_raw and not new_sizes:
            errors.append("Sizes must be of the form 'M: 10', one per line.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            products_mod.update_product(
                product_id,
                name=name, category=category, description=description,
                price=price_f,
                image_file=new_image,
            )
            products_mod.replace_sizes(product_id, new_sizes)
            if new_image:
                delete_image(product["image_file"])
            flash(f"'{name}' updated.", "success")
            return redirect(url_for("owner.products_list") + f"#p-{product_id}")

    sizes_raw = "\n".join(f"{s['size']}: {s['stock']}" for s in sizes)
    return render_template(
        "owner/product_form.html", categories=CATEGORIES, mode="edit",
        product=product, sizes_raw=sizes_raw,
        form={"name": product["name"], "category": product["category"],
              "description": product["description"] or "",
              "price": float(product["price"]), "sizes_raw": sizes_raw},
    )


@owner_bp.post("/products/<int:product_id>/delete")
@owner_required
def product_delete(product_id: int):
    product = products_mod.get_product(product_id)
    if product is None:
        abort(404)
    from uploads import delete_image
    products_mod.delete_product(product_id)
    delete_image(product["image_file"])
    flash(f"Deleted '{product['name']}'.", "info")
    return redirect(url_for("owner.products_list"))


# =====================================================================
# Inventory (stock per size, per product)
# =====================================================================

@owner_bp.get("/inventory")
@owner_required
def inventory():
    products = products_mod.list_products()
    rows = []
    for p in products:
        sizes = products_mod.list_sizes(p["id"])
        rows.append({
            "product": p, "sizes": sizes,
            "total": products_mod.total_stock(p["id"]),
        })
    return render_template("owner/inventory.html", rows=rows)


@owner_bp.post("/inventory/<int:product_id>/stock")
@owner_required
def inventory_update(product_id: int):
    sizes = products_mod.list_sizes(product_id)
    for s in sizes:
        raw = request.form.get(f"stock_{s['size']}")
        try:
            stock_i = max(0, int(raw)) if raw is not None else int(s["stock"])
        except ValueError:
            stock_i = int(s["stock"])
        products_mod.set_size_stock(product_id, s["size"], stock_i)
    flash("Inventory updated.", "success")
    return redirect(url_for("owner.inventory") + f"#p-{product_id}")


# =====================================================================
# Orders (list, detail, status update)
# =====================================================================

@owner_bp.get("/orders")
@owner_required
def orders_list():
    rows = orders_mod.list_all_orders()
    annotated = []
    for o in rows:
        cust = orders_mod.customer_for_order(o)
        annotated.append({
            **dict(o), "customer": cust,
            "items": orders_mod.get_order_items(o["id"]),
        })
    return render_template("owner/orders.html", orders=annotated)


@owner_bp.get("/order/<int:order_id>")
@owner_required
def order_detail(order_id: int):
    order = orders_mod.get_order(order_id)
    if order is None:
        abort(404)
    cust = orders_mod.customer_for_order(order)
    items = orders_mod.get_order_items(order_id)
    return render_template(
        "owner/order_detail.html", order=order,
        customer=cust, items=items, statuses=ORDER_STATUSES,
    )


@owner_bp.post("/order/<int:order_id>/status")
@owner_required
def order_status(order_id: int):
    order = orders_mod.get_order(order_id)
    if order is None:
        abort(404)
    new_status = request.form.get("status", "").strip()
    if new_status not in ORDER_STATUSES:
        flash("Invalid status.", "error")
    else:
        orders_mod.update_order_status(order_id, new_status)
        flash(f"Order #{order_id} -> {new_status}.", "success")
    return redirect(url_for("owner.order_detail", order_id=order_id))


# =====================================================================
# Customers
# =====================================================================

@owner_bp.get("/customers")
@owner_required
def customers_list():
    rows = orders_mod.list_customers()
    return render_template("owner/customers.html", customers=rows)


# =====================================================================
# Settings (read-only store info)
# =====================================================================

@owner_bp.get("/settings")
@owner_required
def settings():
    return render_template("owner/settings.html")
