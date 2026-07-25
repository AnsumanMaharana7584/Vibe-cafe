# Vibe Cafe

A Flask web app for **Vibe Cafe** — browse the menu, search items, manage a cart, and sign up for member discounts.

## Features

- Menu browsing with item detail pages
- Shopping cart (session-based)
- Checkout with Razorpay payments (demo mode without API keys)
- User signup and login with 10% member discount
- Search across menu items and users
- Member discount page

## Setup

1. **Clone the repo**

   ```bash
   git clone https://github.com/AnsumanMaharana7584/Vibe-cafe.git
   cd Vibe-cafe
   ```

2. **Create a virtual environment (recommended)**

   ```bash
   python -m venv venv
   venv\Scripts\activate        # Windows
   # source venv/bin/activate   # macOS / Linux
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app**

   ```bash
   python app.py
   ```

   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Payment setup

The app supports **Razorpay** for INR payments. Without API keys, it runs in **demo mode** (orders complete instantly with no real charge).

1. Copy the example env file:

   ```bash
   copy .env.example .env        # Windows
   # cp .env.example .env        # macOS / Linux
   ```

2. Add your Razorpay test keys from [dashboard.razorpay.com](https://dashboard.razorpay.com/):

   ```
   RAZORPAY_KEY_ID=rzp_test_xxxxx
   RAZORPAY_KEY_SECRET=your_secret_key
   ```

3. Restart the app, add items to cart, and go to **Checkout**.

Logged-in members automatically receive a **10% discount** at checkout.

## Project structure

```
app.py              # Main Flask application
forms.py            # WTForms for signup/login
requirements.txt    # Python dependencies
static/             # Images and media
templates/          # HTML templates
instance/           # SQLite database (created locally, not committed)
```

## Notes

- The SQLite database is created automatically on first run.
- Change `SECRET_KEY` in `app.py` before deploying to production.
