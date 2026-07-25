from flask import Flask, render_template, flash, redirect, url_for, request, jsonify, session, abort
from flask_sqlalchemy import SQLAlchemy
from forms import SignupForm, LoginForm, CheckoutForm
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import phonepe_payments as phonepe

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your-secret-key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contact.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

PAYMENTS_ENABLED = phonepe.is_phonepe_enabled()

db = SQLAlchemy(app)
# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    items_json = db.Column(db.Text, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)
    payment_id = db.Column(db.String(100))
    merchant_order_id = db.Column(db.String(100))
    phonepe_order_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def items(self):
        return json.loads(self.items_json)

def get_cart_totals(cart, member_discount=False):
    subtotal = sum(float(item['price']) for item in cart)
    discount = round(subtotal * 0.10, 2) if member_discount else 0
    total = round(subtotal - discount, 2)
    return subtotal, discount, total

def complete_paid_order(order, payment_id):
    order.status = "paid"
    order.payment_id = payment_id
    db.session.commit()
    session["cart"] = []

# Sample menu items data
MENU_ITEMS = {
    'burger': {'name': 'Burger', 'description': 'Juicy grilled burger with fresh lettuce and tomato.', 'price': 150, 'image': 'berger.jpg'},
    'chocolate-cake': {'name': 'Chocolate Cake', 'description': 'Rich and moist chocolate cake slice.', 'price': 120, 'image': 'chocolate_cake.jpg'},
    'cold-coffee': {'name': 'Cold Coffee', 'description': 'Refreshing cold coffee with ice cream.', 'price': 100, 'image': 'cold_coffee.jpg'},
    'pizza': {'name': 'Pizza', 'description': 'Cheesy pizza topped with fresh veggies and pepperoni.', 'price': 250, 'image': 'pizza.jpg'},
    'sandwich': {'name': 'Sandwich', 'description': 'Toasted sandwich with cheese, tomato, and lettuce.', 'price': 90, 'image': 'sandwiches.jpg'},
    'hazelnut-coffee': {'name': 'Hazelnut Coffee', 'description': 'Smooth coffee with rich hazelnut flavor.', 'price': 120, 'image': 'hazelnut_coffee.jpg'},
    'french-fries': {'name': 'French Fries', 'description': 'Crispy golden fries with a sprinkle of salt.', 'price': 80, 'image': 'frenchesfries.jpg'},
    'chocolate-chip-frappuccino': {'name': 'Chocolate Chip Frappuccino', 'description': 'Cold blended coffee with chocolate chips and whipped cream.', 'price': 150, 'image': 'chocolate_chip_frappuccino.jpg'},
    'hot-coffee': {'name': 'Hot Coffee', 'description': 'Classic hot brewed coffee to warm your day.', 'price': 100, 'image': 'hot_coffee.jpg'}
}

@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html", title="Home")

@app.route("/about")
def about():
    return render_template("about.html", title="About")

@app.route("/menu")
def menu():
    return render_template("menu.html", title="Menu", menu_items=list(MENU_ITEMS.values()))

@app.route('/menu/item/<item_name>')
def menu_item(item_name):
    item = MENU_ITEMS.get(item_name.lower())
    if not item:
        abort(404)
    return render_template('menu_item.html', item=item, title=item['name'])

@app.route("/contacts")
def contacts():
    return render_template("contacts.html", title="Contact Us")

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            session['user_id'] = user.id
            session['username'] = user.username
            flash("Logged in successfully!", "success")
            return redirect(url_for("home"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html", title="Login", form=form)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash("Email already registered.", "warning")
        else:
            hashed_password = generate_password_hash(form.password.data)
            new_user = User(username=form.username.data, email=form.email.data, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash(f"Account created for {form.username.data}!", "success")
            return redirect(url_for("login"))
    return render_template("signup.html", title="Sign Up", form=form)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/cart")
def cart():
    return render_template("cart.html", title="Your Cart", cart=session.get("cart", []))

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.get_json()
    if not data or "name" not in data or "price" not in data:
        return jsonify({"message": "Invalid request"}), 400
    cart = session.get("cart", [])
    cart.append({"name": data["name"], "price": data["price"]})
    session["cart"] = cart
    return jsonify({"message": f"{data['name']} added to cart!"})

@app.route('/clear-cart')
def clear_cart():
    session['cart'] = []
    flash("Cart cleared.", "info")
    return redirect(url_for('cart'))

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", [])
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))

    form = CheckoutForm()
    is_member = "user_id" in session
    subtotal, discount, total = get_cart_totals(cart, is_member)

    if "user_id" in session:
        user = User.query.get(session["user_id"])
        if user and request.method == "GET":
            form.name.data = user.username
            form.email.data = user.email

    order = None
    if form.validate_on_submit():
        order = Order(
            user_id=session.get("user_id"),
            customer_name=form.name.data,
            customer_email=form.email.data,
            customer_phone=form.phone.data,
            items_json=json.dumps(cart),
            subtotal=subtotal,
            discount=discount,
            total=total,
        )
        db.session.add(order)
        db.session.commit()

        if PAYMENTS_ENABLED:
            redirect_url = url_for("phonepe_callback", order_id=order.id, _external=True)
            try:
                merchant_order_id, pay_response = phonepe.initiate_payment(order, redirect_url)
                order.merchant_order_id = merchant_order_id
                order.phonepe_order_id = pay_response.order_id
                db.session.commit()
                return redirect(pay_response.redirect_url)
            except Exception as exc:
                db.session.delete(order)
                db.session.commit()
                flash(f"Could not start PhonePe payment: {exc}", "danger")
        else:
            order.status = "paid"
            order.payment_id = f"demo_{order.id}"
            db.session.commit()
            session["cart"] = []
            flash("Payment successful (demo mode)!", "success")
            return redirect(url_for("payment_success", order_id=order.id))

    return render_template(
        "checkout.html",
        title="Checkout",
        form=form,
        cart=cart,
        subtotal=subtotal,
        discount=discount,
        total=total,
        is_member=is_member,
        payments_enabled=PAYMENTS_ENABLED,
        payment_provider="phonepe",
    )

@app.route("/payment/phonepe/callback/<int:order_id>")
def phonepe_callback(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status == "paid":
        return redirect(url_for("payment_success", order_id=order.id))

    if not PAYMENTS_ENABLED or not order.merchant_order_id:
        flash("Payment is not configured for this order.", "warning")
        return redirect(url_for("checkout"))

    try:
        status_response = phonepe.get_payment_status(order.merchant_order_id)
    except Exception as exc:
        flash(f"Could not verify payment status: {exc}", "danger")
        return redirect(url_for("checkout"))

    if status_response.state == "COMPLETED":
        transaction_id = order.merchant_order_id
        if status_response.payment_details:
            transaction_id = status_response.payment_details[0].transaction_id or transaction_id
        complete_paid_order(order, transaction_id)
        flash("Payment successful!", "success")
        return redirect(url_for("payment_success", order_id=order.id))

    if status_response.state == "FAILED":
        order.status = "failed"
        db.session.commit()
        flash("Payment failed. Please try again.", "danger")
        return redirect(url_for("checkout"))

    flash("Payment is still pending. Please wait or try again.", "warning")
    return redirect(url_for("checkout"))

@app.route("/payment/phonepe/webhook", methods=["POST"])
def phonepe_webhook():
    if not PAYMENTS_ENABLED:
        return jsonify({"success": False}), 400

    body = request.get_data(as_text=True)
    authorization = request.headers.get("Authorization", "")

    try:
        callback = phonepe.validate_webhook(authorization, body)
    except Exception:
        return jsonify({"success": False}), 400

    if not callback:
        return jsonify({"success": False}), 401

    merchant_order_id = getattr(callback.payload, "merchant_order_id", None)
    if not merchant_order_id:
        return jsonify({"success": True})

    order = Order.query.filter_by(merchant_order_id=merchant_order_id).first()
    if order and order.status != "paid" and callback.payload.state == "COMPLETED":
        transaction_id = getattr(callback.payload, "transaction_id", merchant_order_id)
        complete_paid_order(order, transaction_id)

    return jsonify({"success": True})
@app.route("/payment/success/<int:order_id>")
def payment_success(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status != "paid":
        flash("Payment is not complete for this order.", "warning")
        return redirect(url_for("checkout"))
    return render_template("payment_success.html", title="Order Confirmed", order=order)

@app.route("/search")
def search():
    query = request.args.get('query', '').strip().lower()
    if not query:
        flash("Please enter a search term.", "warning")
        return redirect(url_for('home'))

    # Search users by username or email
    matched_users = User.query.filter(
        (User.username.ilike(f"%{query}%")) | (User.email.ilike(f"%{query}%"))
    ).all()
    results = [{'name': u.username, 'type': 'User', 'url': url_for('user_profile', username=u.username)} for u in matched_users]

    # Search menu items by name
    matched_menu = [
        {'name': item['name'], 'type': 'Menu Item', 'url': url_for('menu_item', item_name=key)}
        for key, item in MENU_ITEMS.items()
        if query in item['name'].lower()
    ]
    results.extend(matched_menu)

    return render_template("search_results.html", title="Search Results", query=query, results=results)

@app.route('/user/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('user_profile.html', user=user, title=f"{user.username}'s Profile")

@app.route('/search_suggestions')
def search_suggestions():
    query = request.args.get('query', '').strip().lower()
    if not query:
        return jsonify([])

    matched_menu = [
        {'name': item['name'], 'type': 'Menu Item', 'url': url_for('menu_item', item_name=key)}
        for key, item in MENU_ITEMS.items()
        if query in item['name'].lower()
    ]

    matched_users = User.query.filter(
        (User.username.ilike(f"%{query}%")) | (User.email.ilike(f"%{query}%"))
    ).all()
    matched_users_list = [
        {'name': user.username, 'type': 'User', 'url': url_for('user_profile', username=user.username)}
        for user in matched_users
    ]

    combined_results = matched_menu + matched_users_list
    return jsonify(combined_results[:100])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
