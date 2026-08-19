"""Customer-facing routes: landing, auth, shop, PDP, bag, wishlist,
checkout, payment, orders, profile."""
from __future__ import annotations

import re
from typing import Any

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, session, url_for,
)

import orders as orders_mod
import products as products_mod
from config import CATEGORIES, PAYMENT_METHODS
from customer_auth import (
    authenticate_customer, get_customer, register_customer, update_customer_address,
)
from decorators import customer_required


customer_bp = Blueprint("customer", __name__)


# =====================================================================
# Helpers
# =====================================================================

def _cart() -> dict[int, dict[str, Any]]:
    return session.setdefault("cart", {})


def _wishlist_ids() -> set[int]:
    return set(session.get("wishlist", []))


def _flash_login_required():
    flash("Please login to continue.", "info")


# =====================================================================
# Landing
# =====================================================================

@customer_bp.get("/")
def landing():
    return render_template("landing.html")


@customer_bp.get("/enter")
def enter():
    """Decide where the user goes after the landing 'Enter Store' button."""
    if session.get("role") == "customer":
        return redirect(url_for("customer.shop"))
    return redirect(url_for("customer.auth"))


# =====================================================================
# Auth (login, signup, logout) — also renders the combined auth page
# =====================================================================

@customer_bp.route("/auth", methods=["GET", "POST"])
def auth():
    """Combined auth page: CUSTOMER LOGIN / CUSTOMER SIGNUP / OWNER LOGIN.

    Per §3: customers MUST NOT see 'Become a Seller', 'Register as
    Seller', 'Sell on Speedoo', etc. Only the three tabs above are
    available.
    """
    tab = request.form.get("tab") or request.args.get("tab") or "login"

    # ---- Login ----
    if request.method == "POST" and tab == "login":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        row = authenticate_customer(identifier, password)
        if row is None:
            flash("Invalid username/email or password.", "error")
        else:
            session.clear()
            session["role"] = "customer"
            session["user_id"] = row["id"]
            session["username"] = row["full_name"]
            session["cart"] = {}
            session["wishlist"] = []
            flash(f"Welcome back, {row['full_name']}!", "success")
            nxt = request.args.get("next") or url_for("customer.shop")
            return redirect(nxt)

    # ---- Signup ----
    if request.method == "POST" and tab == "signup":
        ok, msg, row = register_customer({
            "full_name": request.form.get("full_name", ""),
            "username": request.form.get("username", ""),
            "email": request.form.get("email", ""),
            "mobile": request.form.get("mobile", ""),
            "address": request.form.get("address", ""),
            "pincode": request.form.get("pincode", ""),
            "password": request.form.get("password", ""),
            "confirm": request.form.get("confirm", ""),
        })
        if not ok:
            flash(msg, "error")
        else:
            session.clear()
            session["role"] = "customer"
            session["user_id"] = row["id"]
            session["username"] = row["full_name"]
            session["cart"] = {}
            session["wishlist"] = []
            flash("Account created. Welcome to Speedoo Fashion!", "success")
            return redirect(url_for("customer.shop"))

    return render_template("auth.html", tab=tab)


@customer_bp.get("/login")
def customer_login():
    return redirect(url_for("customer.auth", tab="login"))


@customer_bp.get("/signup")
def customer_signup():
    return redirect(url_for("customer.auth", tab="signup"))


@customer_bp.post("/logout")
def customer_logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("customer.landing"))


# =====================================================================
# Shop (browse men's collection)
# =====================================================================

@customer_bp.get("/men")
@customer_required
def shop():
    category = request.args.get("category") or "All"
    search = request.args.get("q") or ""
    rows = products_mod.list_products(category=category, search=search)
    return render_template(
        "shop.html",
        products=rows,
        categories=["All"] + CATEGORIES,
        selected_category=category,
        search=search,
    )


# =====================================================================
# Product detail
# =====================================================================

@customer_bp.route("/product/<int:product_id>", methods=["GET", "POST"])
@customer_required
def product_detail(product_id: int):
    product = products_mod.get_product(product_id)
    if product is None:
        abort(404)
    sizes = products_mod.list_sizes(product_id)
    in_wish = product["id"] in _wishlist_ids()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_to_bag":
            size = request.form.get("size")
            qty = int(request.form.get("qty", "1") or "1")
            if not size:
                flash("Please select a size.", "error")
            else:
                size_row = products_mod.get_size(product_id, size)
                if size_row is None or int(size_row["stock"]) < qty:
                    flash("Not enough stock for that size.", "error")
                else:
                    cart = _cart()
                    key = str(product_id)
                    existing = cart.get(key)
                    if existing is not None:
                        existing["qty"] = int(existing["qty"]) + qty
                    else:
                        cart[key] = {
                            "name": product["name"],
                            "size": size,
                            "qty": qty,
                            "price": float(product["price"]),
                            "image": product["image_file"],
                        }
                    flash(f"Added {product['name']} ({size}) to bag.", "success")
                    return redirect(url_for("customer.bag"))
        elif action == "wishlist_toggle":
            wish = session.setdefault("wishlist", [])
            if product["id"] in wish:
                wish.remove(product["id"])
                products_mod.remove_from_wishlist(session["user_id"], product_id)
                flash("Removed from wishlist.", "info")
            else:
                wish.append(product["id"])
                products_mod.add_to_wishlist(session["user_id"], product_id)
                flash("Saved to wishlist.", "success")
            return redirect(url_for("customer.product_detail", product_id=product_id))

    return render_template(
        "product.html",
        product=product, sizes=sizes, in_wish=in_wish,
    )


# =====================================================================
# Bag
# =====================================================================

@customer_bp.route("/bag", methods=["GET", "POST"])
@customer_required
def bag():
    cart = _cart()
    if request.method == "POST":
        action = request.form.get("action")
        pid = request.form.get("product_id")
        if pid and pid in cart:
            if action == "remove":
                cart.pop(pid, None)
            elif action == "decrease":
                cart[pid]["qty"] = max(1, int(cart[pid]["qty"]) - 1)
                if cart[pid]["qty"] == 0:
                    cart.pop(pid, None)
            elif action == "increase":
                pid_int = int(pid)
                size = cart[pid]["size"]
                size_row = products_mod.get_size(pid_int, size)
                cap = int(size_row["stock"]) if size_row else 0
                if int(cart[pid]["qty"]) + 1 > cap:
                    flash("Not enough stock for that size.", "error")
                else:
                    cart[pid]["qty"] = int(cart[pid]["qty"]) + 1
        return redirect(url_for("customer.bag"))

    # Decorate items with product ref so the template can show image + size
    items: list[dict[str, Any]] = []
    total = 0.0
    for pid_key, item in list(cart.items()):
        pid_int = int(pid_key)
        product = products_mod.get_product(pid_int)
        if product is None:
            cart.pop(pid_key, None)
            continue
        line_total = float(item["price"]) * int(item["qty"])
        total += line_total
        items.append({
            "pid": pid_int,
            "name": item["name"],
            "size": item["size"],
            "qty": int(item["qty"]),
            "price": float(item["price"]),
            "image": product["image_file"],
            "line_total": line_total,
            "stock_cap": int(products_mod.get_size(pid_int, item["size"])["stock"])
                if products_mod.get_size(pid_int, item["size"]) is not None else 0,
        })

    return render_template("bag.html", items=items, total=round(total, 2))


# =====================================================================
# Wishlist
# =====================================================================

@customer_bp.route("/wishlist", methods=["POST", "GET"])
@customer_required
def wishlist():
    if request.method == "POST":
        pid = request.form.get("product_id")
        if pid:
            pid_int = int(pid)
            local = session.setdefault("wishlist", [])
            if pid_int in local:
                local.remove(pid_int)
                products_mod.remove_from_wishlist(session["user_id"], pid_int)
            else:
                local.append(pid_int)
                products_mod.add_to_wishlist(session["user_id"], pid_int)
        return redirect(url_for("customer.wishlist"))

    rows = products_mod.list_wishlist(session["user_id"])
    return render_template("wishlist.html", products=rows)


# =====================================================================
# Checkout / Payment
# =====================================================================

@customer_bp.route("/checkout", methods=["GET", "POST"])
@customer_required
def checkout():
    cart = _cart()
    if not cart:
        flash("Your bag is empty.", "info")
        return redirect(url_for("customer.shop"))

    customer = get_customer(session["user_id"])
    if request.method == "POST":
        address = request.form.get("address", "").strip()
        pincode = request.form.get("pincode", "").strip()
        method = request.form.get("payment_method", "Card")
        if not address:
            flash("Please enter a delivery address.", "error")
            return redirect(url_for("customer.checkout"))
        if not re.match(r"^\d{6}$", pincode):
            flash("Pincode must be exactly 6 digits.", "error")
            return redirect(url_for("customer.checkout"))
        if method not in PAYMENT_METHODS:
            flash("Please choose a valid payment method.", "error")
            return redirect(url_for("customer.checkout"))

        update_customer_address(session["user_id"], address, pincode)
        session["checkout"] = {
            "address": address, "pincode": pincode, "method": method,
        }
        return redirect(url_for("customer.payment"))

    # Rebuild items for the checkout summary
    items = []
    total = 0.0
    for pid_key, item in cart.items():
        pid_int = int(pid_key)
        product = products_mod.get_product(pid_int)
        if product is None:
            continue
        line_total = float(item["price"]) * int(item["qty"])
        total += line_total
        items.append({
            "name": item["name"], "size": item["size"], "qty": int(item["qty"]),
            "price": float(item["price"]), "image": product["image_file"],
            "line_total": line_total,
        })

    return render_template(
        "checkout.html", items=items, total=round(total, 2),
        customer=customer, methods=PAYMENT_METHODS,
        default_address=customer["address"], default_pincode=customer["pincode"],
    )


@customer_bp.route("/payment", methods=["GET", "POST"])
@customer_required
def payment():
    cart = _cart()
    if not cart:
        return redirect(url_for("customer.shop"))
    if "checkout" not in session:
        return redirect(url_for("customer.checkout"))

    checkout = session["checkout"]
    if request.method == "POST":
        # Mock: in a real app this would call a payment gateway.
        order_id = orders_mod.place_order(
            session["user_id"],
            cart,
            payment_method=checkout["method"],
            delivery_address=checkout["address"],
            delivery_pincode=checkout["pincode"],
            payment_status="Confirmed",
        )
        session.pop("cart", None)
        session.pop("checkout", None)
        return redirect(url_for("customer.order_confirmation", order_id=order_id))

    items = []
    total = 0.0
    for pid_key, item in cart.items():
        line_total = float(item["price"]) * int(item["qty"])
        total += line_total
        items.append({
            "name": item["name"], "size": item["size"], "qty": int(item["qty"]),
            "price": float(item["price"]), "line_total": line_total,
        })

    return render_template("payment.html", items=items, total=round(total, 2),
                           method=checkout["method"])


@customer_bp.get("/order/<int:order_id>/confirmation")
@customer_required
def order_confirmation(order_id: int):
    order = orders_mod.get_order_for(
        order_id, role="customer", customer_id=session["user_id"]
    )
    if order is None:
        abort(403)
    items = orders_mod.get_order_items(order_id)
    return render_template("order_confirmation.html", order=order, items=items)


# =====================================================================
# My orders + order privacy-enforced detail
# =====================================================================

@customer_bp.get("/orders")
@customer_required
def my_orders():
    rows = orders_mod.list_orders_for_customer(session["user_id"])
    annotated = []
    for o in rows:
        annotated.append({
            **dict(o),
            "items": orders_mod.get_order_items(o["id"]),
        })
    return render_template("my_orders.html", orders=annotated)


@customer_bp.get("/order/<int:order_id>")
@customer_required
def order_detail(order_id: int):
    # Privacy check happens inside get_order_for.
    order = orders_mod.get_order_for(
        order_id, role="customer", customer_id=session["user_id"]
    )
    if order is None:
        abort(403)
    items = orders_mod.get_order_items(order_id)
    return render_template("order_confirmation.html", order=order, items=items,
                           compact=True)


# =====================================================================
# Profile
# =====================================================================

@customer_bp.route("/profile", methods=["GET", "POST"])
@customer_required
def profile():
    customer = get_customer(session["user_id"])
    if request.method == "POST":
        address = request.form.get("address", "").strip()
        pincode = request.form.get("pincode", "").strip()
        if address and re.match(r"^\d{6}$", pincode):
            update_customer_address(session["user_id"], address, pincode)
            flash("Profile updated.", "success")
            return redirect(url_for("customer.profile"))
        flash("Please provide a valid address and 6-digit pincode.", "error")
    customer = get_customer(session["user_id"])
    return render_template("profile.html", customer=customer)
