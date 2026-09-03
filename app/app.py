"""
Simple local e-commerce demo app.
Features: login, product listing, add/remove cart, mock checkout/payment.

Run with:
    python app.py
Then visit http://127.0.0.1:5000
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash
import uuid

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"  # fine for local demo only

USERS = {
    "admin": "admin123",
    "testuser": "password1",
}

PRODUCTS = [
    {"id": 1, "name": "Wireless Mouse", "price": 799, "emoji": "MOUSE"},
    {"id": 2, "name": "Mechanical Keyboard", "price": 3499, "emoji": "KEYBOARD"},
    {"id": 3, "name": "USB-C Hub", "price": 1299, "emoji": "HUB"},
    {"id": 4, "name": "Laptop Stand", "price": 1899, "emoji": "STAND"},
    {"id": 5, "name": "Noise Cancelling Headphones", "price": 5999, "emoji": "HEADPHONES"},
    {"id": 6, "name": "Webcam 1080p", "price": 2199, "emoji": "WEBCAM"},
]

ORDERS = {}


def get_product(product_id):
    return next((p for p in PRODUCTS if p["id"] == product_id), None)


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("products"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if USERS.get(username) == password:
            session["username"] = username
            session.setdefault("cart", {})
            flash(f"Welcome back, {username}!")
            return redirect(url_for("products"))
        flash("Invalid username or password.")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/products")
@login_required
def products():
    cart = session.get("cart", {})
    cart_count = sum(cart.values())
    return render_template("products.html", products=PRODUCTS, cart_count=cart_count)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def cart_add(product_id):
    product = get_product(product_id)
    if not product:
        flash("Product not found.")
        return redirect(url_for("products"))
    cart = session.get("cart", {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session["cart"] = cart
    flash(f"Added '{product['name']}' to cart.")
    return redirect(url_for("products"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
@login_required
def cart_remove(product_id):
    cart = session.get("cart", {})
    key = str(product_id)
    if key in cart:
        cart[key] -= 1
        if cart[key] <= 0:
            del cart[key]
        session["cart"] = cart
        flash("Item removed from cart.")
    return redirect(url_for("cart_view"))


@app.route("/cart")
@login_required
def cart_view():
    cart = session.get("cart", {})
    items = []
    total = 0
    for pid_str, qty in cart.items():
        product = get_product(int(pid_str))
        if product:
            line_total = product["price"] * qty
            total += line_total
            items.append({**product, "qty": qty, "line_total": line_total})
    return render_template("cart.html", items=items, total=total)


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for("products"))

    if request.method == "POST":
        card_name = request.form.get("card_name", "").strip()
        card_number = request.form.get("card_number", "").strip()
        expiry = request.form.get("expiry", "").strip()
        cvv = request.form.get("cvv", "").strip()

        if not (card_name and card_number and expiry and cvv):
            flash("Please fill in all payment fields.")
            return redirect(url_for("checkout"))

        order_id = str(uuid.uuid4())[:8].upper()
        items = []
        total = 0
        for pid_str, qty in cart.items():
            product = get_product(int(pid_str))
            if product:
                line_total = product["price"] * qty
                total += line_total
                items.append({**product, "qty": qty, "line_total": line_total})

        ORDERS[order_id] = {
            "username": session["username"],
            "line_items": items,
            "total": total,
        }
        session["cart"] = {}
        return redirect(url_for("order_confirmation", order_id=order_id))

    items = []
    total = 0
    for pid_str, qty in cart.items():
        product = get_product(int(pid_str))
        if product:
            line_total = product["price"] * qty
            total += line_total
            items.append({**product, "qty": qty, "line_total": line_total})
    return render_template("checkout.html", items=items, total=total)


@app.route("/order-confirmation/<order_id>")
@login_required
def order_confirmation(order_id):
    order = ORDERS.get(order_id)
    if not order:
        flash("Order not found.")
        return redirect(url_for("products"))
    return render_template("confirmation.html", order_id=order_id, order=order)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
