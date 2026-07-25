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

try:
    import razorpay
except ImportError:
    razorpay = None

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your-secret-key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contact.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
PAYMENTS_ENABLED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET and razorpay)

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
    razorpay_order_id = db.Column(db.String(100))
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

def get_razorpay_client():
    if not PAYMENTS_ENABLED:
        return None
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

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
            client = get_razorpay_client()
            razorpay_order = client.order.create({
                "amount": int(total * 100),
                "currency": "INR",
                "receipt": f"order_{order.id}",
            })
            order.razorpay_order_id = razorpay_order["id"]
            db.session.commit()
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
        order=order,
        razorpay_key=RAZORPAY_KEY_ID,
    )

@app.route("/payment/verify", methods=["POST"])
def verify_payment():
    if not PAYMENTS_ENABLED:
        return jsonify({"success": False, "message": "Payments are not configured."}), 400

    data = request.get_json() or {}
    payment_id = data.get("razorpay_payment_id")
    order_id = data.get("razorpay_order_id")
    signature = data.get("razorpay_signature")

    if not all([payment_id, order_id, signature]):
        return jsonify({"success": False, "message": "Missing payment details."}), 400

    client = get_razorpay_client()
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"success": False, "message": "Payment verification failed."}), 400

    order = Order.query.filter_by(razorpay_order_id=order_id).first_or_404()
    order.status = "paid"
    order.payment_id = payment_id
    db.session.commit()
    session["cart"] = []

    return jsonify({
        "success": True,
        "redirect": url_for("payment_success", order_id=order.id),
    })

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
