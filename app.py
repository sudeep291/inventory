from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g, send_from_directory
import os
import datetime
import decimal
import traceback
import base64
import json
from flask.json.provider import DefaultJSONProvider
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from db import get_db_connection, init_db, release_db_connection
from apscheduler.schedulers.background import BackgroundScheduler
from flask_compress import Compress
from PIL import Image
import io
import bleach
import logging

from google.cloud.firestore_v1.base_query import FieldFilter

# 🚀 Enterprise Service Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Enterprise Persistence Layer (Zero-Crash Infrastructure)
GLOBAL_ANALYTICS_CACHE = {}
BACKUP_FILE = 'static/resilience_backup.json'

# 🔐 BRUTE-FORCE LOCKOUT ENGINE
_LOGIN_LOCKOUT = {}
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def save_cache_to_disk():
    try:
        with open(BACKUP_FILE, 'w') as f:
            json.dump(GLOBAL_ANALYTICS_CACHE, f)
    except Exception as e:
        logger.warning(f"Cache save error: {e}")

def load_cache_from_disk():
    global GLOBAL_ANALYTICS_CACHE
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, 'r') as f:
                GLOBAL_ANALYTICS_CACHE = json.load(f)
        except Exception as e:
            logger.warning(f"Cache load error, starting fresh: {e}")
            GLOBAL_ANALYTICS_CACHE = {}

load_cache_from_disk()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def safe_float(val, default=0.0):
    try: return float(val) if val is not None and val != '' else default
    except: return default

def safe_int(val, default=0):
    try: return int(val) if val is not None and val != '' else default
    except: return default

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        return super().default(obj)

def process_image(image_file, max_size=(600, 600)):
    """Professional Image Optimizer."""
    try:
        img = Image.open(image_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{b64_str}"
    except Exception as e:
        print(f"IMAGE OPTIMIZATION ERROR: {e}")
        return None

def clean_input(text):
    """Enterprise-grade sanitization to prevent XSS"""
    if not text or not isinstance(text, str): return text
    return bleach.clean(text, tags=[], attributes={}, strip=True)

# ============================================================
# FIREBASE HELPER FUNCTIONS (replaces SQL queries)
# ============================================================

def fb_get_all_categories(db):
    """Returns list of {id, name} dicts from Firestore Categories collection."""
    docs = db.collection('Categories').stream()
    return [{"id": doc.id, "name": doc.to_dict().get('name', '')} for doc in docs]

def fb_get_all_products_with_sizes(db, active_only=True):
    """
    Returns list of product dicts, each with a 'sizes' list and 'total_stock'.
    Preserves exact structure used by the frontend.
    """
    prod_query = db.collection('Products')
    if active_only:
        prod_query = prod_query.where(filter=FieldFilter('is_active', '==', True))
    
    products = []
    product_map = {}
    for doc in prod_query.stream():
        d = doc.to_dict()
        p = {
            "id": doc.id,
            "name": d.get('name', ''),
            "article_no": d.get('article_no', ''),
            "category_id": d.get('category_id', ''),
            "category_name": d.get('category_name', ''),
            "gender": d.get('gender', ''),
            "image_path": d.get('image_path', None),
            "mrp": safe_float(d.get('mrp')),
            "default_discount": safe_float(d.get('default_discount')),
            "selling_price": safe_float(d.get('selling_price')),
            "barcode": d.get('barcode', ''),
            "total_stock": 0,
            "sizes": []
        }
        # Sizes are stored inside the product document as an array
        for sz in d.get('sizes', []):
            stock = safe_int(sz.get('stock', 0))
            p['sizes'].append({
                "id": sz.get('id', ''),
                "product_id": doc.id,
                "size": safe_float(sz.get('size')),
                "stock": stock
            })
            p['total_stock'] += stock
        p['sizes'] = sorted(p['sizes'], key=lambda x: x['size'])
        products.append(p)
        product_map[doc.id] = p
    return products, product_map

def fb_get_product(db, product_id):
    """Get a single product document."""
    doc = db.collection('Products').document(product_id).get()
    if doc.exists:
        d = doc.to_dict()
        d['id'] = doc.id
        return d
    return None

def fb_get_sales(db, status_filter=None, date_filter=None, days=None):
    """
    Generic sales fetcher. Returns list of sale dicts.
    date_filter: 'today', 'week', None (all)
    """
    query = db.collection('Sales')
    if status_filter:
        query = query.where(filter=FieldFilter('status', '==', status_filter))
    
    docs = query.stream()
    sales = []
    now = datetime.datetime.now(datetime.timezone.utc)
    today_start = datetime.datetime(now.year, now.month, now.day)
    week_start = today_start - datetime.timedelta(days=7)

    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        # Normalize sale_date
        sale_date = d.get('sale_date')
        if hasattr(sale_date, 'ToDatetime'):
            sale_date = sale_date.ToDatetime()
        elif not isinstance(sale_date, datetime.datetime):
            sale_date = None
        d['sale_date'] = sale_date

        if date_filter == 'today' and sale_date and sale_date >= today_start:
            sales.append(d)
        elif date_filter == 'week' and sale_date and sale_date >= week_start:
            sales.append(d)
        elif date_filter is None:
            sales.append(d)

    return sales

# ============================================================
# APP SETUP
# ============================================================

app = Flask(__name__)
app.json = CustomJSONProvider(app)
app.secret_key = os.environ.get('SECRET_KEY', 'enterprise_super_secret_key_999')

OWNER_PASSWORD = os.environ.get('OWNER_PASSWORD', 'admin123')
EMPLOYEE_PASSWORD = os.environ.get('EMPLOYEE_PASSWORD', 'staff123')
UPLOAD_FOLDER = os.path.join('static', 'images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=8)
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
Compress(app)

@app.after_request
def add_security_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=604800, stale-while-revalidate=86400'
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    else:
        response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(self), geolocation=(), microphone=(), payment=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "worker-src 'self' blob:; "
        "connect-src 'self' https://api.upcitemdb.com"
    )
    return response

@app.route('/ping')
def enterprise_ping():
    return "SYSTEM_HEALTHY", 200

@app.route('/service-worker.js')
def serve_sw():
    return send_from_directory('static', 'service-worker.js', mimetype='application/javascript')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# 🛡️ GLOBAL ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404,
        message="Page not found. It may have moved or never existed."), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 ERROR: {traceback.format_exc()}")
    return render_template('error.html', code=500,
        message="Something went wrong on our end. We've logged it and will fix it."), 500

@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    logger.error(f"UNHANDLED EXCEPTION: {tb}")
    return render_template('error.html', code=500,
        message="An unexpected error occurred. The team has been notified."), 500

# Centralized DB helper (returns Firestore client via g)
def get_db():
    if 'db' not in g:
        g.db = get_db_connection()
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    g.pop('db', None)

@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and 'logged_in' not in session:
        return redirect(url_for('login'))
    if request.endpoint in ['analytics', 'overview', 'factory_reset']:
        if session.get('role') != 'owner':
            return "403 Forbidden: You do not have owner privileges to view this section.", 403

# ============================================================
# AUTH
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    record = _LOGIN_LOCKOUT.get(ip, {"attempts": 0, "locked_until": None})

    if record["locked_until"] and datetime.datetime.now(datetime.timezone.utc) < record["locked_until"]:
        remaining = int((record["locked_until"] - datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 60) + 1
        return render_template('login.html', error=f"Too many failed attempts. Try again in {remaining} minute(s).")

    if request.method == 'POST':
        password = request.form.get('password')
        if password == OWNER_PASSWORD:
            _LOGIN_LOCKOUT.pop(ip, None)
            session['logged_in'] = True
            session['role'] = 'owner'
            session.permanent = True
            return redirect(url_for('dashboard'))
        elif password == EMPLOYEE_PASSWORD:
            _LOGIN_LOCKOUT.pop(ip, None)
            session['logged_in'] = True
            session['role'] = 'employee'
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            record["attempts"] = record.get("attempts", 0) + 1
            attempts_left = MAX_ATTEMPTS - record["attempts"]
            if record["attempts"] >= MAX_ATTEMPTS:
                record["locked_until"] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=LOCKOUT_MINUTES)
                logger.warning(f"🔒 SECURITY: IP {ip} locked out after {MAX_ATTEMPTS} failed login attempts.")
                error = f"Access locked for {LOCKOUT_MINUTES} minutes due to too many wrong attempts."
            else:
                error = f"Invalid password. {attempts_left} attempt(s) remaining before lockout."
            _LOGIN_LOCKOUT[ip] = record
            expired = [k for k, v in _LOGIN_LOCKOUT.items()
                       if v["locked_until"] and datetime.datetime.now(datetime.timezone.utc) > v["locked_until"]
                       and v["attempts"] >= MAX_ATTEMPTS]
            for k in expired:
                _LOGIN_LOCKOUT.pop(k, None)

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# ============================================================
# PAGE ROUTES
# ============================================================
@app.route('/')
def dashboard():
    return render_template('index.html', active_page='dashboard')

@app.route('/overview')
def overview():
    return render_template('overview.html', active_page='overview')

@app.route('/inventory')
def inventory():
    return render_template('inventory.html', active_page='sell')

@app.route('/update_stock')
def update_stock():
    return render_template('update_stock.html', active_page='update')

@app.route('/add_product')
def add_product_page():
    return render_template('add_product.html', active_page='add')

@app.route('/analytics')
def analytics():
    return render_template('analytics.html', active_page='analytics')

@app.route('/sales_history')
def sales_history():
    return render_template('sales_history.html', active_page='sales_history')

# ============================================================
# FACTORY RESET
# ============================================================
@app.route('/admin/factory_reset')
def factory_reset():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.args.get('confirm') != OWNER_PASSWORD:
        return "ACCESS DENIED: Provide your password as confirmation key in the URL. Example: /admin/factory_reset?confirm=YOUR_PASSWORD", 403

    db = get_db()
    if not db: return "Database connection error", 500

    try:
        for col in ['Categories', 'Products', 'Sales', 'WeeklyMetrics']:
            docs = db.collection(col).stream()
            for doc in docs:
                doc.reference.delete()

        global GLOBAL_ANALYTICS_CACHE
        GLOBAL_ANALYTICS_CACHE.clear()
        save_cache_to_disk()
        return "DATABASE COMPLETELY WIPED TO FACTORY SETTINGS. All practice data has been deleted. You can now navigate back to the app.", 200
    except Exception as e:
        return f"CRITICAL ERROR DURING WIPE: {e}", 500

# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/api/stats')
def api_stats():
    global GLOBAL_ANALYTICS_CACHE
    if GLOBAL_ANALYTICS_CACHE and 'stats' in GLOBAL_ANALYTICS_CACHE:
        return jsonify(GLOBAL_ANALYTICS_CACHE['stats'])

    db = get_db()
    if not db:
        if GLOBAL_ANALYTICS_CACHE and 'stats' in GLOBAL_ANALYTICS_CACHE:
            return jsonify(GLOBAL_ANALYTICS_CACHE['stats'])
        return jsonify({"error": "No DB"}), 500

    try:
        # Total active products
        products_docs = list(db.collection('Products').where(filter=FieldFilter('is_active', '==', True)).stream())
        total_products = len(products_docs)

        # Total stock and low-stock count
        total_stock = 0
        low_stock_alerts = 0
        best_seller_map = {}

        for doc in products_docs:
            d = doc.to_dict()
            for sz in d.get('sizes', []):
                stk = safe_int(sz.get('stock', 0))
                total_stock += stk
                if stk < 5:
                    low_stock_alerts += 1

        # Best seller: from Sales
        sales_docs = list(db.collection('Sales').where(filter=FieldFilter('status', '==', 'SALE')).stream())
        for sdoc in sales_docs:
            sd = sdoc.to_dict()
            pid = sd.get('product_id', '')
            qty = safe_int(sd.get('quantity', 0))
            best_seller_map[pid] = best_seller_map.get(pid, 0) + qty

        best_seller = "No sales yet"
        if best_seller_map:
            best_pid = max(best_seller_map, key=best_seller_map.get)
            prod_doc = db.collection('Products').document(best_pid).get()
            if prod_doc.exists:
                pd = prod_doc.to_dict()
                best_seller = f"{pd.get('name', '')} ({pd.get('article_no', '')})"

        res = {
            "total_products": total_products,
            "total_stock": total_stock,
            "low_stock_alerts": low_stock_alerts,
            "best_seller": best_seller
        }
        GLOBAL_ANALYTICS_CACHE['stats'] = res
        save_cache_to_disk()
        return jsonify(res)
    except Exception as e:
        logger.error(f"api_stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/inventory')
def api_inventory():
    db = get_db()
    if not db: return jsonify({"error": "No DB"}), 500

    try:
        categories = fb_get_all_categories(db)
        products, _ = fb_get_all_products_with_sizes(db, active_only=True)
        return jsonify({"categories": categories, "products": products})
    except Exception as e:
        logger.error(f"api_inventory error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/categories', methods=['POST'])
def api_add_category():
    name = clean_input(request.json.get('name', '').strip())
    if not name: return jsonify({"error": "Name required"}), 400

    db = get_db()
    try:
        # Duplicate check
        existing = db.collection('Categories').where(filter=FieldFilter('name_lower', '==', name.lower())).stream()
        if any(True for _ in existing):
            return jsonify({"error": f"Category '{name}' already exists!"}), 400

        new_ref = db.collection('Categories').add({
            'name': name,
            'name_lower': name.lower()
        })
        new_id = new_ref[1].id
        import threading
        threading.Thread(target=enterprise_heartbeat, daemon=True).start()
        return jsonify({"id": new_id, "name": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/products', methods=['POST'])
def api_add_product():
    name = clean_input(request.form.get('name'))
    article_no = clean_input(request.form.get('article_no'))
    category_id = request.form.get('category_id')
    gender = clean_input(request.form.get('gender'))
    sizes_json = request.form.get('sizes_json')
    mrp = request.form.get('mrp')
    default_discount = request.form.get('default_discount')
    image = request.files.get('image')
    barcode = clean_input(request.form.get('barcode'))

    if not all([name, article_no, category_id, sizes_json, mrp, default_discount]):
        return jsonify({"error": "Missing required fields"}), 400

    db = get_db()
    try:
        # Duplicate article_no check
        existing = db.collection('Products').where(filter=FieldFilter('article_no', '==', article_no)).stream()
        if any(True for _ in existing):
            return jsonify({"error": "Article number already exists!"}), 400

        mrp_f = safe_float(mrp)
        disc_f = safe_float(default_discount)
        selling_price = round(mrp_f - (mrp_f * disc_f / 100), 2)

        # Get category name
        cat_doc = db.collection('Categories').document(category_id).get()
        category_name = cat_doc.to_dict().get('name', '') if cat_doc.exists else ''

        image_path = None
        if image and image.filename:
            if not allowed_file(image.filename):
                return jsonify({"error": "Invalid file type. Only JPG, PNG, WEBP allowed."}), 400
            image_path = process_image(image)

        sizes_data = json.loads(sizes_json)
        # Build sizes array with unique IDs
        import uuid
        sizes_list = []
        for sObj in sizes_data:
            sizes_list.append({
                "id": str(uuid.uuid4()),
                "size": safe_float(sObj['size']),
                "stock": safe_int(sObj['stock'])
            })

        new_ref = db.collection('Products').add({
            'name': name,
            'article_no': article_no,
            'category_id': category_id,
            'category_name': category_name,
            'gender': gender,
            'image_path': image_path,
            'mrp': mrp_f,
            'default_discount': disc_f,
            'selling_price': selling_price,
            'is_active': True,
            'barcode': barcode,
            'sizes': sizes_list
        })
        import threading
        threading.Thread(target=enterprise_heartbeat, daemon=True).start()
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"api_add_product error: {e}")
        return jsonify({"error": str(e)}), 400


@app.route('/api/products/<string:id>/image', methods=['POST'])
def api_update_product_image(id):
    image = request.files.get('image')
    if not image or not image.filename:
        return jsonify({"error": "No image provided"}), 400
    if not allowed_file(image.filename):
        return jsonify({"error": "Invalid file type. Only JPG, PNG, WEBP allowed."}), 400

    try:
        image_data_uri = process_image(image)
        if not image_data_uri:
            return jsonify({"error": "Failed to process image"}), 400
        db = get_db()
        db.collection('Products').document(id).update({'image_path': image_data_uri})
        import threading
        threading.Thread(target=enterprise_heartbeat, daemon=True).start()
        return jsonify({"success": True, "image_path": image_data_uri})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/products/<string:id>/image/remove', methods=['POST'])
def api_remove_product_image(id):
    try:
        db = get_db()
        db.collection('Products').document(id).update({'image_path': None})
        import threading
        threading.Thread(target=enterprise_heartbeat, daemon=True).start()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/products/remove', methods=['POST'])
def api_remove_product():
    product_id = request.json.get('product_id')
    if not product_id: return jsonify({"error": "Missing product_id"}), 400
    try:
        db = get_db()
        db.collection('Products').document(product_id).update({'is_active': False})
        import threading
        threading.Thread(target=enterprise_heartbeat, daemon=True).start()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/stock/adjust', methods=['POST'])
def api_stock_adjust():
    data = request.json
    size_id = data.get('size_id')
    amount = data.get('amount')
    operation = data.get('operation')
    sold_price = data.get('sold_price')
    discount_applied = data.get('discount_applied')

    if not all([size_id, amount, operation]):
        return jsonify({"error": "Missing params"}), 400

    amount = safe_int(amount)
    db = get_db()

    try:
        # Find the product containing this size_id
        products_docs = db.collection('Products').where(filter=FieldFilter('is_active', '==', True)).stream()
        target_product = None
        target_size = None

        for pdoc in products_docs:
            d = pdoc.to_dict()
            for sz in d.get('sizes', []):
                if sz.get('id') == size_id:
                    target_product = pdoc
                    target_size = sz
                    break
            if target_product:
                break

        if not target_product or not target_size:
            return jsonify({"error": "Size not found"}), 404

        current_stock = safe_int(target_size.get('stock', 0))

        if operation == 'subtract' and current_stock < amount:
            return jsonify({"error": "Not enough stock!"}), 400

        # Update sizes array
        prod_data = target_product.to_dict()
        sizes = prod_data.get('sizes', [])
        for sz in sizes:
            if sz.get('id') == size_id:
                if operation == 'subtract':
                    sz['stock'] = current_stock - amount
                else:
                    sz['stock'] = current_stock + amount
                break

        target_product.reference.update({'sizes': sizes})

        # Record sale
        if operation == 'subtract':
            db.collection('Sales').add({
                'product_id': target_product.id,
                'product_name': prod_data.get('name', ''),
                'article_no': prod_data.get('article_no', ''),
                'size': safe_float(target_size.get('size')),
                'quantity': amount,
                'sold_price': safe_float(sold_price),
                'discount_applied': safe_float(discount_applied),
                'selling_price': safe_float(prod_data.get('selling_price')),
                'mrp': safe_float(prod_data.get('mrp')),
                'sale_date': datetime.datetime.now(datetime.timezone.utc),
                'status': 'SALE'
            })
            
        import threading
        threading.Thread(target=enterprise_heartbeat, daemon=True).start()

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"api_stock_adjust error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/stock/adjust_batch', methods=['POST'])
def api_adjust_stock_batch():
    data = request.json
    updates = data.get('updates', [])
    if not updates:
        return jsonify({"error": "No updates provided"}), 400

    db = get_db()
    import uuid

    try:
        new_mrp = data.get('new_mrp')

        for up in updates:
            amount = safe_int(up.get('amount'))
            if amount <= 0: continue
            is_return = up.get('is_return', False)

            if up.get('is_new'):
                # New size being added to existing product
                product_id = up.get('product_id')
                size = safe_float(up.get('size'))
                prod_doc = db.collection('Products').document(product_id).get()
                if not prod_doc.exists: continue
                prod_data = prod_doc.to_dict()
                sizes = prod_data.get('sizes', [])

                # Check if size already exists
                found = False
                for sz in sizes:
                    if sz.get('size') == size:
                        sz['stock'] += amount
                        found = True
                        break
                if not found:
                    sizes.append({"id": str(uuid.uuid4()), "size": size, "stock": amount})

                prod_doc.reference.update({'sizes': sizes})

                if is_return:
                    refund_px = safe_float(up.get('price'), 0.0)
                    db.collection('Sales').add({
                        'product_id': product_id,
                        'product_name': prod_data.get('name', ''),
                        'article_no': prod_data.get('article_no', ''),
                        'size': size,
                        'quantity': amount,
                        'sold_price': refund_px,
                        'selling_price': safe_float(prod_data.get('selling_price')),
                        'mrp': safe_float(prod_data.get('mrp')),
                        'sale_date': datetime.datetime.now(datetime.timezone.utc),
                        'status': 'RETURNED'
                    })
            else:
                size_id = up.get('size_id')
                # Find product with this size_id
                products_docs = db.collection('Products').stream()
                for pdoc in products_docs:
                    prod_data = pdoc.to_dict()
                    sizes = prod_data.get('sizes', [])
                    for sz in sizes:
                        if sz.get('id') == size_id:
                            sz['stock'] += amount
                            pdoc.reference.update({'sizes': sizes})
                            if is_return:
                                refund_px = safe_float(up.get('price'), 0.0)
                                db.collection('Sales').add({
                                    'product_id': pdoc.id,
                                    'product_name': prod_data.get('name', ''),
                                    'article_no': prod_data.get('article_no', ''),
                                    'size': safe_float(sz.get('size')),
                                    'quantity': amount,
                                    'sold_price': refund_px,
                                    'selling_price': safe_float(prod_data.get('selling_price')),
                                    'mrp': safe_float(prod_data.get('mrp')),
                                    'sale_date': datetime.datetime.now(datetime.timezone.utc),
                                    'status': 'RETURNED'
                                })
                            break

        # Dynamic Price Synchronization
        if new_mrp:
            nm = safe_float(new_mrp)
            if nm > 0:
                # Find the product from updates
                for up in updates:
                    pid = up.get('product_id') or None
                    if pid:
                        prod_doc = db.collection('Products').document(pid).get()
                        if prod_doc.exists:
                            disc = safe_float(prod_doc.to_dict().get('default_discount', 0))
                            new_sp = round(nm - (nm * disc / 100.0), 2)
                            prod_doc.reference.update({'mrp': nm, 'selling_price': new_sp})
                        break

        import threading
        threading.Thread(target=enterprise_heartbeat, daemon=True).start()
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"api_adjust_stock_batch error: {e}")
        return jsonify({"error": str(e)}), 400


@app.route('/api/returns/stats')
def api_returns_stats():
    db = get_db()
    try:
        sales_docs = db.collection('Sales').where(filter=FieldFilter('status', '==', 'RETURNED')).stream()
        total = sum(safe_int(doc.to_dict().get('quantity', 0)) for doc in sales_docs)
        return jsonify({"success": True, "total": total})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/analytics/heatmap')
def api_analytics_heatmap():
    db = get_db()
    try:
        products, _ = fb_get_all_products_with_sizes(db, active_only=True)
        sales_docs = db.collection('Sales').where(filter=FieldFilter('status', '==', 'SALE')).stream()

        size_agg = {}
        # Initialize stock from products
        for p in products:
            for sz in p.get('sizes', []):
                sv = safe_float(sz.get('size'))
                stk = safe_int(sz.get('stock', 0))
                if sv not in size_agg:
                    size_agg[sv] = {"sold": 0, "stock": 0}
                size_agg[sv]["stock"] += stk

        # Aggregate sales
        for sdoc in sales_docs:
            sd = sdoc.to_dict()
            sv = safe_float(sd.get('size'))
            qty = safe_int(sd.get('quantity', 0))
            if sv not in size_agg:
                size_agg[sv] = {"sold": 0, "stock": 0}
            size_agg[sv]["sold"] += qty

        heatmap_data = []
        for s, d in sorted(size_agg.items()):
            heat_level = "cold"
            if d["sold"] > 10 and d["stock"] < 10:
                heat_level = "hot"
            elif d["sold"] > 2:
                heat_level = "warm"
            heatmap_data.append({
                "size": s,
                "total_sold": d["sold"],
                "current_stock": d["stock"],
                "heat_level": heat_level
            })
        return jsonify({"success": True, "data": heatmap_data})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


# ============================================================
# CONSOLIDATED ANALYTICS ENGINE (Replaces complex SQL JOINs)
# ============================================================

def get_consolidated_analytics():
    """Enterprise consolidated analytics – all computed in Python from Firestore docs."""
    global GLOBAL_ANALYTICS_CACHE
    db = get_db_connection()
    if not db: return None

    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)
        week_start = today_start - datetime.timedelta(days=7)

        # Fetch all sales
        all_sales = list(db.collection('Sales').stream())

        daily_pairs = 0; daily_unique_pids = set(); daily_returns = 0
        daily_rev = 0.0; daily_surplus = 0.0; daily_money_returned = 0.0

        weekly_pairs = 0; weekly_rev = 0.0; weekly_surplus = 0.0; weekly_money_returned = 0.0
        total_pairs = 0; total_surplus = 0.0; total_money_returned = 0.0

        date_qty_map = {}
        article_map = {}  # article_no -> {name, qty, revenue, profit}

        for sdoc in all_sales:
            sd = sdoc.to_dict()
            status = sd.get('status', 'SALE')
            qty = safe_int(sd.get('quantity', 0))
            sold_px = safe_float(sd.get('sold_price', 0))
            selling_px = safe_float(sd.get('selling_price', 0))
            pid = sd.get('product_id', '')
            article_no = sd.get('article_no', '')
            pname = sd.get('product_name', '')

            sale_date = sd.get('sale_date')
            if hasattr(sale_date, 'ToDatetime'):
                sale_date = sale_date.ToDatetime()
            elif not isinstance(sale_date, datetime.datetime):
                sale_date = None

            # Revenue and surplus calculations
            rev = sold_px * qty
            surplus = (sold_px - selling_px) * qty
            sign = 1 if status == 'SALE' else -1

            # --- All-time ---
            total_pairs += sign * qty
            total_surplus += sign * surplus
            if status == 'RETURNED':
                total_money_returned += rev

            # --- Weekly ---
            if sale_date and sale_date >= week_start:
                weekly_pairs += sign * qty
                weekly_rev += sign * rev
                weekly_surplus += sign * surplus
                if status == 'RETURNED':
                    weekly_money_returned += rev

            # --- Daily ---
            if sale_date and sale_date >= today_start:
                daily_pairs += sign * qty
                daily_rev += sign * rev
                daily_surplus += sign * surplus
                if status == 'SALE':
                    daily_unique_pids.add(pid)
                if status == 'RETURNED':
                    daily_returns += qty
                    daily_money_returned += rev

            # --- Chart (last 7 days) ---
            if sale_date and sale_date >= week_start:
                day_key = sale_date.strftime('%a')
                date_qty_map[day_key] = date_qty_map.get(day_key, 0) + (sign * qty)

            # --- Article performance ---
            if article_no not in article_map:
                article_map[article_no] = {"name": pname, "qty": 0, "revenue": 0.0, "profit": 0.0}
            article_map[article_no]["qty"] += sign * qty
            article_map[article_no]["revenue"] += sign * rev
            article_map[article_no]["profit"] += sign * surplus

        # Build chart labels using last 7 days in order
        chart_labels = []
        chart_data = []
        for i in range(6, -1, -1):
            d = today_start - datetime.timedelta(days=i)
            label = d.strftime('%a')
            chart_labels.append(label)
            chart_data.append(date_qty_map.get(label, 0))

        # Stock summary from products
        products, _ = fb_get_all_products_with_sizes(db, active_only=True)
        total_stock = 0; total_investment = 0.0; potential_revenue = 0.0
        low_stock_list = []
        all_stock_list = []
        for p in products:
            p_stock = p.get('total_stock', 0)
            sp = safe_float(p.get('selling_price', 0))
            mrp = safe_float(p.get('mrp', 0))
            total_stock += p_stock
            total_investment += sp * p_stock
            potential_revenue += mrp * p_stock
            all_stock_list.append({"article": p['article_no'], "name": p['name'], "stock": p_stock})
            for sz in p.get('sizes', []):
                if safe_int(sz.get('stock', 0)) < 5:
                    low_stock_list.append({
                        "name": p['name'],
                        "article": p['article_no'],
                        "size": sz['size'],
                        "stock": sz['stock']
                    })

        # Total returned pairs
        total_returned = 0
        for sdoc in all_sales:
            sd = sdoc.to_dict()
            if sd.get('status') == 'RETURNED':
                total_returned += safe_int(sd.get('quantity', 0))

        article_profit = [
            {"article_no": art, "qty": v["qty"], "revenue": round(v["revenue"], 2), "profit": max(0, round(v["profit"], 2))}
            for art, v in article_map.items()
        ]

        result = {
            "daily": {
                "pairs": daily_pairs,
                "unique_pairs": len(daily_unique_pids),
                "returns": daily_returns,
                "money_returned": round(daily_money_returned, 2),
                "revenue": round(daily_rev, 2),
                "net_surplus": round(daily_surplus, 2)
            },
            "weekly": {
                "pairs": weekly_pairs,
                "revenue": round(weekly_rev, 2),
                "net_surplus": round(weekly_surplus, 2),
                "money_returned": round(weekly_money_returned, 2)
            },
            "chart": {"labels": chart_labels, "data": chart_data},
            "stock": {
                "total_products": len(products),
                "total_stock": total_stock,
                "total_investment": round(total_investment, 2),
                "potential_revenue": round(potential_revenue, 2),
                "total_returned": total_returned
            },
            "low_stock_list": low_stock_list,
            "all_stock_list": sorted(all_stock_list, key=lambda x: x['stock'], reverse=True),
            "articles": article_profit
        }

        GLOBAL_ANALYTICS_CACHE = result
        save_cache_to_disk()
        return result
    except Exception as e:
        logger.error(f"Consolidated Analytics Fetch Failed: {e}")
        return None


@app.route('/api/sales_advanced')
def api_sales_advanced():
    if GLOBAL_ANALYTICS_CACHE:
        return jsonify(GLOBAL_ANALYTICS_CACHE)
    res = get_consolidated_analytics()
    if res: return jsonify(res)
    return jsonify({"error": "No analytics available"}), 500


def get_consolidated_history():
    """Fetch and return last 200 sales records from Firestore."""
    global GLOBAL_ANALYTICS_CACHE
    db = get_db_connection()
    if not db: return None
    try:
        sales_docs = db.collection('Sales').order_by(
            'sale_date', direction='DESCENDING'
        ).limit(200).stream()

        sales = []
        for sdoc in sales_docs:
            sd = sdoc.to_dict()
            sale_date = sd.get('sale_date')
            if hasattr(sale_date, 'ToDatetime'):
                sale_date = sale_date.ToDatetime()
            
            sales.append({
                "id": sdoc.id,
                "date": sale_date.isoformat() if isinstance(sale_date, datetime.datetime) else "",
                "article": sd.get('article_no', ''),
                "name": sd.get('product_name', ''),
                "size": sd.get('size', ''),
                "qty": sd.get('quantity', 0),
                "mrp": sd.get('mrp', 0),
                "sold_price": sd.get('sold_price', 0),
                "discount": sd.get('discount_applied', 0),
                "status": sd.get('status', 'SALE')
            })

        GLOBAL_ANALYTICS_CACHE['history'] = sales
        save_cache_to_disk()
        return sales
    except Exception as e:
        logger.error(f"Consolidated History Fetch Failed: {e}")
        return None


@app.route('/api/sales_history')
def api_sales_history():
    if GLOBAL_ANALYTICS_CACHE and 'history' in GLOBAL_ANALYTICS_CACHE:
        return jsonify(GLOBAL_ANALYTICS_CACHE['history'])
    res = get_consolidated_history()
    if res: return jsonify(res)
    return jsonify([])


# ============================================================
# BACKGROUND SCHEDULER (WEEKLY METRICS)
# ============================================================
def record_weekly_snapshot():
    db = get_db_connection()
    if not db:
        logger.warning("Scheduler: Firebase connection failed.")
        return

    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        week_start = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc) - datetime.timedelta(days=7)
        today_start = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)

        sales_docs = list(db.collection('Sales').stream())

        total_pairs = 0; total_rev = 0.0; net_prof = 0.0
        for sdoc in sales_docs:
            sd = sdoc.to_dict()
            sale_date = sd.get('sale_date')
            if hasattr(sale_date, 'ToDatetime'):
                sale_date = sale_date.ToDatetime()
            if not isinstance(sale_date, datetime.datetime): continue
            if not (week_start <= sale_date < today_start): continue

            qty = safe_int(sd.get('quantity', 0))
            sold_px = safe_float(sd.get('sold_price', 0))
            selling_px = safe_float(sd.get('selling_price', 0))
            status = sd.get('status', 'SALE')
            sign = 1 if status == 'SALE' else -1

            total_pairs += sign * qty
            total_rev += sign * (sold_px * qty)
            net_prof += sign * ((sold_px - selling_px) * qty)

        # Vault stock & investment
        products, _ = fb_get_all_products_with_sizes(db, active_only=True)
        vault_stock = sum(p.get('total_stock', 0) for p in products)
        total_investment = sum(
            safe_float(p.get('selling_price')) * p.get('total_stock', 0) for p in products
        )

        db.collection('WeeklyMetrics').add({
            'snapshot_date': datetime.datetime.now(datetime.timezone.utc),
            'total_pairs_sold': total_pairs,
            'total_revenue': round(total_rev, 2),
            'net_profit': round(net_prof, 2),
            'current_vault_stock': vault_stock,
            'current_total_investment': round(total_investment, 2)
        })
        logger.info(f"WEEKLY METRICS SAVED: {total_pairs} pairs, Revenue: {total_rev}, Profit: {net_prof}")
    except Exception as e:
        logger.error(f"SCHEDULER LOGIC ERROR: {e}")


def enterprise_heartbeat():
    try:
        logger.info(f"[{datetime.datetime.now()}] ENTERPRISE HEARTBEAT: System Healthy.")
        get_consolidated_analytics()
        get_consolidated_history()
    except Exception as e:
        logger.error(f"Heartbeat Logic Failure: {e}")


scheduler = BackgroundScheduler()
scheduler.add_job(func=record_weekly_snapshot, trigger="cron", day_of_week='mon', hour=0, minute=1)
scheduler.add_job(func=enterprise_heartbeat, trigger="interval", minutes=3)


def startup_checks():
    try:
        import time
        time.sleep(5)
        with app.app_context():
            init_db()
            logger.info("Professional Initialization: Firebase connected successfully.")
            enterprise_heartbeat()
            if not scheduler.running:
                scheduler.start()
                logger.info("Professional Initialization: Background Scheduler active.")
    except Exception as e:
        logger.error(f"FATAL STARTUP LOGIC ERROR: {e}", exc_info=True)


import threading
threading.Thread(target=startup_checks, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port, host='0.0.0.0')
