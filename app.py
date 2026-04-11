from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
import os
import datetime
import decimal
import traceback
import base64
import json
from flask.json.provider import DefaultJSONProvider
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from db import get_db_connection, init_db, release_db_connection
from apscheduler.schedulers.background import BackgroundScheduler
from flask_compress import Compress
from PIL import Image
import io
import bleach
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from cryptography.fernet import Fernet

load_dotenv()

# Enterprise Persistence Layer (Zero-Crash Infrastructure)
GLOBAL_ANALYTICS_CACHE = {} 
BACKUP_FILE = 'static/resilience_backup.vault' # Refactored to vault extension for security

# 🛡️ CRYPTOGRAPHIC VAULT LAYER (AES-128 Protection)
def get_vault_cipher():
    key = os.environ.get('DB_ENCRYPTION_KEY')
    if not key:
        # Auto-generation for local development security (Enterprise Resilience)
        key = Fernet.generate_key().decode()
        print("⚠️ VAULT WARNING: No DB_ENCRYPTION_KEY found. Generated temporary one.")
    return Fernet(key.encode())

def save_cache_to_disk():
    try:
        cipher = get_vault_cipher()
        data_json = json.dumps(GLOBAL_ANALYTICS_CACHE)
        encrypted_data = cipher.encrypt(data_json.encode())
        with open(BACKUP_FILE, 'wb') as f:
            f.write(encrypted_data)
    except Exception as e:
        print(f"VAULT SAVE ERROR: {e}")

def load_cache_from_disk():
    global GLOBAL_ANALYTICS_CACHE
    if os.path.exists(BACKUP_FILE):
        try:
            cipher = get_vault_cipher()
            with open(BACKUP_FILE, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = cipher.decrypt(encrypted_data).decode()
            GLOBAL_ANALYTICS_CACHE = json.loads(decrypted_data)
        except Exception as e:
            print(f"VAULT LOAD ERROR (Wrong Key or Corrupt): {e}")

load_cache_from_disk()

# Professional Stability Helpers (Zero-Crash Vision)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def safe_float(val, default=0.0):
    try: return float(val) if val else default
    except: return default

def safe_int(val, default=0):
    try: return int(val) if val else default
    except: return default

# Custom JSON Encoder for Decimal support (Postgres compatibility)
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)
        
def process_image(image_file, max_size=(600, 600)):
    """Professional Image Optimizer: Resizes and compresses for mobile excellence."""
    try:
        img = Image.open(image_file)
        # Handle transparency (convert PNG to white background for consistent JPEG behavior)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # High-Fidelity downscaling
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save to buffer
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{b64_str}"
    except Exception as e:
        print(f"IMAGE OPTIMIZATION ERROR: {e}")
        return None

def clean_input(text):
    """Enterprise-grade sanitization to prevent XSS/Malware injection"""
    if not text or not isinstance(text, str): return text
    return bleach.clean(text, tags=[], attributes={}, strip=True)

app = Flask(__name__)
app.json = CustomJSONProvider(app)
app.secret_key = os.environ.get('SECRET_KEY', 'enterprise_super_secret_key_999')

# 🛡️ GLOBAL SECURITY HARDENING (SecOps)
# Content Security Policy: Allows internal scripts, styles, and Google Fonts
csp = {
    'default-src': '\'self\'',
    'script-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdn.jsdelivr.net'],
    'style-src': ['\'self\'', '\'unsafe-inline\'', 'https://fonts.googleapis.com'],
    'font-src': ['\'self\'', 'https://fonts.gstatic.com'],
    'img-src': ['\'self\'', 'data:', 'https://via.placeholder.com'],
    'connect-src': '\'self\''
}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 🛡️ ELITE DEFENSIVE SHIELDING (SecOps Level 2)
# CSRF Protection: Forces every command to have a unique cryptographic token
csrf = CSRFProtect(app)

# Session Hardening: Prevents hackers from stealing or leaking login sessions
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True, # Forces secure transfer in production
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=8) # Auto-logout for security
)

# Hardware Permissions Lockdown: Disables unused phone features in the APK
permissions_policy = {
    'geolocation': '()',
    'microphone': '()',
    'camera': '()',
    'payment': '()'
}

# Talisman Refinement: High-security headers + Feature Lockdown
talisman = Talisman(
    app, 
    content_security_policy=csp, 
    permissions_policy=permissions_policy,
    force_https=True,
    session_cookie_secure=True
)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Global Error Handler for Debugging Render Deployment
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    print(tb)  # Will show in Render logs
    return jsonify({"error": str(e), "traceback": tb}), 500

# Centralized DB Connection Management
def get_db():
    if 'db' not in g:
        g.db = get_db_connection()
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        release_db_connection(db)

@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and 'logged_in' not in session:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == OWNER_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid password."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# ==========================================
# PAGE ROUTES
# ==========================================

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

@app.route('/admin/factory_reset')
@limiter.limit("3 per minute") # 🛡️ Protection against automated destruction "viruses"
def factory_reset():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    # Security Guard: Require the owner password as a key to execute the wipe
    if request.args.get('confirm') != OWNER_PASSWORD:
        return "ACCESS DENIED: To prevent accidental wipes, you must provide your password as a confirmation key in the URL. Example: /admin/factory_reset?confirm=YOUR_PASSWORD", 403
        
    conn = get_db()
    if not conn: return "Database connection error", 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE Categories, Products, ProductSizes, Sales, WeeklyMetrics RESTART IDENTITY CASCADE;")
        conn.commit()
        
        global GLOBAL_ANALYTICS_CACHE
        GLOBAL_ANALYTICS_CACHE.clear()
        save_cache_to_disk()
        
        return "DATABASE COMPLETELY WIPED TO FACTORY SETTINGS. All practice data has been deleted but the architecture remains. You can now navigate back to the app.", 200
    except Exception as e:
        conn.rollback()
        return f"CRITICAL ERROR DURING WIPE: {e}", 500

# ==========================================
# API ENDPOINTS
# ==========================================

@app.route('/api/stats')
def api_stats():
    global GLOBAL_ANALYTICS_CACHE
    # SWR Strategy for Stats
    if GLOBAL_ANALYTICS_CACHE and 'stats' in GLOBAL_ANALYTICS_CACHE:
        return jsonify(GLOBAL_ANALYTICS_CACHE['stats'])
        
    conn = get_db()
    if not conn: 
        if GLOBAL_ANALYTICS_CACHE and 'stats' in GLOBAL_ANALYTICS_CACHE:
            return jsonify(GLOBAL_ANALYTICS_CACHE['stats'])
        return jsonify({"error": "No DB"}), 500
    cursor = conn.cursor()
    
    # Total Products
    cursor.execute("SELECT COUNT(*) AS total FROM Products WHERE is_active=TRUE")
    total_products = cursor.fetchone()['total']
    
    # Total Current Stock (sum of all sizes of active products)
    cursor.execute("""
        SELECT COALESCE(SUM(ps.stock), 0) AS total_stock FROM ProductSizes ps
        JOIN Products p ON ps.product_id = p.id
        WHERE p.is_active=TRUE
    """)
    total_stock = cursor.fetchone()['total_stock']
    
    # Low stock count
    cursor.execute("""
        SELECT COUNT(*) AS total FROM ProductSizes ps
        JOIN Products p ON ps.product_id = p.id
        WHERE p.is_active=TRUE AND ps.stock < 5
    """)
    low_stock_alerts = cursor.fetchone()['total']
    
    # Best Selling Article (All time)
    cursor.execute("""
        SELECT p.name, p.article_no, SUM(s.quantity) as sold
        FROM Sales s
        JOIN Products p ON s.product_id = p.id
        GROUP BY p.name, p.article_no
        ORDER BY sold DESC
        LIMIT 1
    """)
    best = cursor.fetchone()
    best_seller = f"{best['name']} ({best['article_no']})" if best else "No sales yet"
    
    res = {
        "total_products": total_products,
        "total_stock": total_stock,
        "low_stock_alerts": low_stock_alerts,
        "best_seller": best_seller
    }
    # Link to global cache
    if 'stats' not in GLOBAL_ANALYTICS_CACHE: GLOBAL_ANALYTICS_CACHE['stats'] = {}
    GLOBAL_ANALYTICS_CACHE['stats'] = res
    save_cache_to_disk()
    
    return jsonify(res)

@app.route('/api/inventory')
def api_inventory():
    conn = get_db()
    if not conn: return jsonify({"error": "No DB"}), 500
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name FROM Categories")
    categories = [{"id": row['id'], "name": row['name']} for row in cursor.fetchall()]
    
    query = """
    SELECT p.id, p.name, p.article_no, p.category_id, c.name as category_name, p.gender, p.image_path, p.mrp, p.default_discount, p.selling_price
    FROM Products p
    LEFT JOIN Categories c ON p.category_id = c.id
    WHERE p.is_active = TRUE
    """
    cursor.execute(query)
    products = []
    product_map = {}
    for row in cursor.fetchall():
        p = {
            "id": row['id'],
            "name": row['name'],
            "article_no": row['article_no'],
            "category_id": row['category_id'],
            "category_name": row['category_name'],
            "gender": row['gender'],
            "image_path": row['image_path'],
            "mrp": row['mrp'],
            "default_discount": row['default_discount'],
            "selling_price": row['selling_price'],
            "total_stock": 0,
            "sizes": []
        }
        products.append(p)
        product_map[row['id']] = p
        
    cursor.execute("""
        SELECT ps.id, ps.product_id, ps.size, ps.stock 
        FROM ProductSizes ps
        JOIN Products p ON ps.product_id = p.id
        WHERE p.is_active = TRUE
    """)
    for row in cursor.fetchall():
        pid = row['product_id']
        if pid in product_map:
            product_map[pid]['sizes'].append({
                "id": row['id'], "product_id": pid, "size": row['size'], "stock": row['stock']
            })
            product_map[pid]['total_stock'] += row['stock']
            
    for p in products:
        p['sizes'] = sorted(p['sizes'], key=lambda x: x['size'])
        
    return jsonify({"categories": categories, "products": products})

@app.route('/api/categories', methods=['POST'])
def api_add_category():
    name = clean_input(request.json.get('name', '').strip())
    if not name: return jsonify({"error": "Name required"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Category Guard: Prevent duplicates (case-insensitive)
        cursor.execute("SELECT id FROM Categories WHERE LOWER(name) = LOWER(%s)", (name,))
        if cursor.fetchone():
            return jsonify({"error": f"Category '{name}' already exists!"}), 400
            
        cursor.execute("INSERT INTO Categories (name) VALUES (%s) RETURNING id", (name,))
        new_row = cursor.fetchone()
        new_id = new_row['id']
        conn.commit()
        return jsonify({"id": new_id, "name": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/products', methods=['POST'])
def api_add_product():
    name = clean_input(request.form.get('name'))
    article_no = clean_input(request.form.get('article_no'))
    category_id = request.form.get('category_id')
    gender = clean_input(request.form.get('gender'))
    sizes_json = request.form.get('sizes_json')  # Needs JSON parsing
    mrp = request.form.get('mrp')
    default_discount = request.form.get('default_discount')
    image = request.files.get('image')
    
    if not all([name, article_no, category_id, sizes_json, mrp, default_discount]):
        return jsonify({"error": "Missing required fields"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM Products WHERE article_no = %s", (article_no,))
    if cursor.fetchone():
        return jsonify({"error": "Article number already exists!"}), 400
        
    mrp = safe_float(mrp)
    default_discount = safe_float(default_discount)
    image_path = None
    if image and image.filename:
        if not allowed_file(image.filename):
            return jsonify({"error": "Invalid file type. Only JPG, PNG, WEBP allowed."}), 400
        
        # Optimized Base64 Conversion
        image_path = process_image(image)
        
    try:
        import json
        sizes_data = json.loads(sizes_json)
        
        selling_price = mrp - (mrp * default_discount / 100)

        cursor.execute("""
            INSERT INTO Products (name, article_no, category_id, gender, image_path, mrp, default_discount, selling_price, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id
        """, (name, article_no, category_id, gender, image_path, mrp, default_discount, selling_price))
        new_p = cursor.fetchone()
        product_id = new_p['id']
        
        for sObj in sizes_data:
            cursor.execute("INSERT INTO ProductSizes (product_id, size, stock) VALUES (%s, %s, %s)", 
                           (product_id, float(sObj['size']), int(sObj['stock'])))
            
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/products/<int:id>/image', methods=['POST'])
def api_update_product_image(id):
    image = request.files.get('image')
    if not image or not image.filename:
        return jsonify({"error": "No image provided"}), 400
        
    if not allowed_file(image.filename):
        return jsonify({"error": "Invalid file type. Only JPG, PNG, WEBP allowed."}), 400
        
    try:
        # Optimized Base64 Conversion
        image_data_uri = process_image(image)
        if not image_data_uri:
             return jsonify({"error": "Failed to process image"}), 400
            
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE Products SET image_path = %s WHERE id = %s", (image_data_uri, id))
        conn.commit()
        return jsonify({"success": True, "image_path": image_data_uri})
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/products/<int:id>/image/remove', methods=['POST'])
def api_remove_product_image(id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Products SET image_path = NULL WHERE id = %s", (id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/stock/adjust_batch', methods=['POST'])
@limiter.limit("20 per minute") # 🛡️ Protection against automated injection attacks
def api_adjust_stock_batch():
    data = request.json
    updates = data.get('updates', [])
    if not updates:
        return jsonify({"error": "No updates provided"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    try:
        new_mrp = data.get('new_mrp')
        product_to_update = None
        
        for up in updates:
            amount = safe_int(up.get('amount'))
            if amount <= 0: continue
            
            is_return = up.get('is_return', False)
            
            if up.get('is_new'):
                product_id = up.get('product_id')
                product_to_update = product_id
                size = safe_float(up.get('size'))
                
                # Atomic UPSERT Logic (Professional Integrity)
                cursor.execute("""
                    INSERT INTO ProductSizes (product_id, size, stock)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (product_id, size) DO UPDATE SET stock = ProductSizes.stock + EXCLUDED.stock
                    RETURNING id
                """, (product_id, size, amount))
                res = cursor.fetchone()
                # If it's a return of a new size (rare but possible)
                if is_return:
                    refund_px = safe_float(up.get('price'), 0.0)
                    cursor.execute("""
                        INSERT INTO Sales (product_id, size, quantity, sold_price, status)
                        VALUES (%s, %s, %s, %s, 'RETURNED')
                    """, (product_id, size, amount, refund_px))
            else:
                size_id = up.get('size_id')
                cursor.execute("UPDATE ProductSizes SET stock = stock + %s WHERE id = %s RETURNING product_id, size", (amount, size_id))
                row = cursor.fetchone()
                if row: product_to_update = row['product_id']
                
                if is_return and row:
                    refund_px = safe_float(up.get('price'), 0.0)
                    cursor.execute("""
                        INSERT INTO Sales (product_id, size, quantity, sold_price, status)
                        VALUES (%s, %s, %s, %s, 'RETURNED')
                    """, (row['product_id'], row['size'], amount, refund_px))
        
        # Dynamic Price Synchronization Logic
        if new_mrp and product_to_update:
            nm = safe_float(new_mrp)
            if nm > 0:
                cursor.execute("SELECT default_discount FROM Products WHERE id = %s", (product_to_update,))
                p_row = cursor.fetchone()
                if p_row:
                    disc = float(p_row['default_discount'])
                    new_sp = nm - (nm * disc / 100.0)
                    cursor.execute("UPDATE Products SET mrp = %s, selling_price = %s WHERE id = %s", (nm, new_sp, product_to_update))

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/returns/stats')
def api_returns_stats():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COALESCE(SUM(quantity), 0) as total FROM Sales WHERE status = 'RETURNED'")
        row = cursor.fetchone()
        return jsonify({"success": True, "total": row['total']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/products/remove', methods=['POST'])
def api_remove_product():
    product_id = request.json.get('product_id')
    if not product_id: return jsonify({"error": "Missing product_id"}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Products SET is_active = FALSE WHERE id = %s", (product_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
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
        
    amount = int(amount)
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT product_id, size, stock FROM ProductSizes WHERE id = %s", (size_id,))
        row = cursor.fetchone()
        if not row: return jsonify({"error": "Size not found"}), 404
            
        if operation == 'subtract' and row['stock'] < amount:
            return jsonify({"error": "Not enough stock!"}), 400
            
        # Atomic Update (Professional Resilience)
        if operation == 'subtract':
            cursor.execute("UPDATE ProductSizes SET stock = stock - %s WHERE id = %s AND stock >= %s", (amount, size_id, amount))
        else:
            cursor.execute("UPDATE ProductSizes SET stock = stock + %s WHERE id = %s", (amount, size_id))
            
        if cursor.rowcount == 0:
            return jsonify({"error": "Stock mismatch or not enough stock!"}), 400
            
        if operation == 'subtract':
            cursor.execute("""
                INSERT INTO Sales (product_id, size, quantity, sold_price, discount_applied)
                VALUES (%s, %s, %s, %s, %s)
            """, (row['product_id'], row['size'], amount, float(sold_price) if sold_price else 0, float(discount_applied) if discount_applied else 0))
            
        conn.commit()
        # Intelligent Cache Invalidation: Refresh history & analytics on sale (Enterprise Tier)
        import threading
        if 'enterprise_heartbeat' in globals():
            threading.Thread(target=enterprise_heartbeat, daemon=True).start()
            
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/sales_advanced')
def get_consolidated_analytics():
    """Enterprise-level consolidated analytics engine"""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        # Enterprise Analytics Suite: Fully Return-Aware Financial Calculation
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN s.status = 'SALE' THEN s.quantity ELSE -s.quantity END), 0) as pairs_today,
                COUNT(DISTINCT CASE WHEN s.status = 'SALE' THEN s.product_id END) as unique_pairs_today,
                COALESCE(SUM(CASE WHEN s.status = 'RETURNED' THEN s.quantity ELSE 0 END), 0) as returns_today,
                ROUND(COALESCE(SUM(CASE WHEN s.status = 'SALE' THEN s.sold_price * s.quantity ELSE -(s.sold_price * s.quantity) END), 0), 2) as rev_today,
                -- 🛡️ Net Surplus Performance: Correctly neutralizes gains/losses on return
                ROUND(COALESCE(SUM(CASE 
                    WHEN s.status = 'SALE' THEN (s.sold_price - p.selling_price) * s.quantity 
                    ELSE -((s.sold_price - p.selling_price) * s.quantity) 
                END), 0), 2) as net_surplus_today,
                -- Explicit Tracking of Money Returned
                ROUND(COALESCE(SUM(CASE WHEN s.status = 'RETURNED' THEN s.sold_price * s.quantity ELSE 0 END), 0), 2) as money_returned_today
            FROM Sales s JOIN Products p ON s.product_id = p.id
            WHERE DATE(s.sale_date) = CURRENT_DATE
        """)
        dr = cursor.fetchone()
        daily = {
            "pairs": float(dr['pairs_today']), 
            "unique_pairs": dr['unique_pairs_today'],
            "returns": int(dr['returns_today']),
            "money_returned": float(dr['money_returned_today']),
            "revenue": float(dr['rev_today']), 
            "net_surplus": float(dr['net_surplus_today'])
        }
        
        # Weekly Analytics: Synchronized with Daily Accuracy
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN s.status = 'SALE' THEN s.quantity ELSE -s.quantity END), 0) as pairs_week,
                ROUND(COALESCE(SUM(CASE WHEN s.status = 'SALE' THEN s.sold_price * s.quantity ELSE -(s.sold_price * s.quantity) END), 0), 2) as rev_week,
                ROUND(COALESCE(SUM(CASE 
                    WHEN s.status = 'SALE' THEN (s.sold_price - p.selling_price) * s.quantity 
                    ELSE -((s.sold_price - p.selling_price) * s.quantity) 
                END), 0), 2) as net_surplus_week,
                ROUND(COALESCE(SUM(CASE WHEN s.status = 'RETURNED' THEN s.sold_price * s.quantity ELSE 0 END), 0), 2) as money_returned_week
            FROM Sales s JOIN Products p ON s.product_id = p.id
            WHERE s.sale_date >= CURRENT_DATE - INTERVAL '7 days'
        """)
        wr = cursor.fetchone()
        weekly = {
            "pairs": float(wr['pairs_week']), 
            "revenue": float(wr['rev_week']), 
            "net_surplus": float(wr['net_surplus_week']),
            "money_returned": float(wr['money_returned_week'])
        }

        # Overall Analytical Ledger (Total Life-To-Date)
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN s.status = 'SALE' THEN s.quantity ELSE -s.quantity END), 0) as pairs_total,
                ROUND(COALESCE(SUM(CASE 
                    WHEN s.status = 'SALE' THEN (s.sold_price - p.selling_price) * s.quantity 
                    ELSE -((s.sold_price - p.selling_price) * s.quantity) 
                END), 0), 2) as net_surplus_total,
                ROUND(COALESCE(SUM(CASE WHEN s.status = 'RETURNED' THEN s.sold_price * s.quantity ELSE 0 END), 0), 2) as money_returned_total
            FROM Sales s JOIN Products p ON s.product_id = p.id
        """)
        tr = cursor.fetchone()
        
        # Vault Inventory Assessment (Real-Time Valuation)
        cursor.execute("SELECT COALESCE(SUM(stock), 0) as vault_stock FROM ProductSizes")
        sr_vault = cursor.fetchone()
        
        overall = {
            "pairs": float(tr['pairs_total']),
            "net_surplus": float(tr['net_surplus_total']),
            "money_returned": float(tr['money_returned_total']),
            "vault_stock": int(sr_vault['vault_stock'])
        }
        
        cursor.execute("""
            SELECT 
                ROUND(COALESCE(SUM(p.selling_price * ps.stock), 0), 2) as total_investment,
                ROUND(COALESCE(SUM(p.mrp * ps.stock), 0), 2) as potential_revenue,
                COUNT(DISTINCT p.id) as total_variants,
                COALESCE(SUM(ps.stock), 0) as total_pairs
            FROM ProductSizes ps
            JOIN Products p ON ps.product_id = p.id
            WHERE p.is_active = TRUE
        """)
        sr = cursor.fetchone()
        
        cursor.execute("SELECT COALESCE(SUM(quantity), 0) as ret_total FROM Sales WHERE status = 'RETURNED'")
        rr = cursor.fetchone()
        
        stock_summary = {
            "total_products": sr['total_variants'],
            "total_stock": sr['total_pairs'],
            "total_investment": sr['total_investment'],
            "potential_revenue": sr['potential_revenue'],
            "total_returned": rr['ret_total']
        }
        
        cursor.execute("""
            SELECT p.name, p.article_no, ps.size, ps.stock 
            FROM ProductSizes ps JOIN Products p ON ps.product_id = p.id 
            WHERE p.is_active=TRUE AND ps.stock < 5
        """)
        low_stock = [{"name": r['name'], "article": r['article_no'], "size": r['size'], "stock": r['stock']} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT p.article_no, p.name, COALESCE(SUM(ps.stock),0) as total_stock
            FROM Products p LEFT JOIN ProductSizes ps ON p.id = ps.product_id
            WHERE p.is_active=TRUE
            GROUP BY p.article_no, p.name
            ORDER BY total_stock DESC
        """)
        all_stock = [{"article": r['article_no'], "name": r['name'], "stock": r['total_stock']} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT p.article_no, p.name, 
                   SUM(CASE WHEN s.status = 'SALE' THEN s.quantity ELSE -s.quantity END) AS total_qty, 
                   ROUND(SUM(CASE WHEN s.status = 'SALE' THEN s.sold_price * s.quantity ELSE -(s.sold_price * s.quantity) END), 2) AS revenue, 
                   ROUND(SUM(CASE WHEN s.status = 'SALE' THEN (s.sold_price - p.selling_price) * s.quantity ELSE -((s.sold_price - p.selling_price) * s.quantity) END), 2) AS article_surplus
            FROM Sales s JOIN Products p ON s.product_id = p.id
            GROUP BY p.article_no, p.name
        """)
        article_profit = [
            {"article_no": r['article_no'], "qty": r['total_qty'], "revenue": r['revenue'], "profit": max(0, r['article_surplus'])} 
            for r in cursor.fetchall()
        ]
        
        cursor.execute("""
            SELECT DATE(sale_date) as d, COALESCE(SUM(CASE WHEN status = 'SALE' THEN quantity ELSE -quantity END), 0) as qty
            FROM Sales WHERE sale_date >= CURRENT_DATE - INTERVAL '6 days'
            GROUP BY DATE(sale_date) ORDER BY d
        """)
        trend_rows = cursor.fetchall()
        chart_labels = [row['d'].strftime('%a') if row['d'] else '?' for row in trend_rows]
        chart_data = [row['qty'] for row in trend_rows]

        result = {
            "daily": daily, "weekly": weekly,
            "chart": {"labels": chart_labels, "data": chart_data},
            "stock": stock_summary, "low_stock_list": low_stock,
            "all_stock_list": all_stock, "articles": article_profit
        }
        
        global GLOBAL_ANALYTICS_CACHE
        GLOBAL_ANALYTICS_CACHE = result
        save_cache_to_disk()
        return result
    except Exception as e:
        print("Consolidated Analytics Fetch Failed:", e)
        return None
    finally:
        release_db_connection(conn)

@app.route('/api/sales_advanced')
def api_sales_advanced():
    # Attempt SWR Return
    if GLOBAL_ANALYTICS_CACHE:
        return jsonify(GLOBAL_ANALYTICS_CACHE)
    
    # Try Fresh Fetch if Cache Empty
    res = get_consolidated_analytics()
    if res: return jsonify(res)
    return jsonify({"error": "No analytics available"}), 500

@app.route('/sales_history')
def sales_history():
    return render_template('sales_history.html', active_page='sales_history')

def get_consolidated_history():
    """Enterprise-level consolidated history engine"""
    global GLOBAL_ANALYTICS_CACHE
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.sale_date, p.article_no, p.name, s.size, s.quantity, 
                   p.mrp, s.sold_price, s.discount_applied, s.status
            FROM Sales s
            JOIN Products p ON s.product_id = p.id
            ORDER BY s.sale_date DESC
            LIMIT 200
        """)
        rows = cursor.fetchall()
        sales = []
        for r in rows:
            sales.append({
                "id": r['id'], "date": r['sale_date'].isoformat() if r['sale_date'] else "",
                "article": r['article_no'], "name": r['name'],
                "size": r['size'], "qty": r['quantity'],
                "mrp": r['mrp'], "sold_price": r['sold_price'],
                "discount": r['discount_applied'],
                "status": r['status']
            })
        
        # Integrate into global cache
        if 'history' not in GLOBAL_ANALYTICS_CACHE: GLOBAL_ANALYTICS_CACHE['history'] = []
        GLOBAL_ANALYTICS_CACHE['history'] = sales
        save_cache_to_disk()
        return sales
    except Exception as e:
        print("Consolidated History Fetch Failed:", e)
        return None
    finally:
        release_db_connection(conn)

@app.route('/api/sales_history')
def api_sales_history():
    # Attempt SWR Return
    if GLOBAL_ANALYTICS_CACHE and 'history' in GLOBAL_ANALYTICS_CACHE:
        return jsonify(GLOBAL_ANALYTICS_CACHE['history'])
    
    # Try Fresh Fetch if Cache Empty
    res = get_consolidated_history()
    if res: return jsonify(res)
    return jsonify([])

# ==========================================
# BACKGROUND SCHEDULER (WEEKLY METRICS)
# ==========================================
def record_weekly_snapshot():
    conn = get_db_connection()
    if not conn:
        print("Scheduler: DB connection failed.")
        return
        
    try:
        cursor = conn.cursor()
        
        # Net Accounting: Subtract quantity for RETURN status
        cursor.execute("SELECT COALESCE(SUM(CASE WHEN status='SALE' THEN quantity WHEN status='RETURNED' THEN -quantity ELSE 0 END), 0) as pairs FROM Sales WHERE sale_date >= CURRENT_DATE - INTERVAL '7 days' AND sale_date < CURRENT_DATE")
        row = cursor.fetchone()
        total_pairs_sold = row['pairs'] if row and 'pairs' in row else 0
        
        # Net Revenue: Subtract sold_price * quantity for RETURN status
        cursor.execute("SELECT ROUND(COALESCE(SUM(CASE WHEN status='SALE' THEN sold_price * quantity WHEN status='RETURNED' THEN -(sold_price * quantity) ELSE 0 END), 0), 2) as rev FROM Sales WHERE sale_date >= CURRENT_DATE - INTERVAL '7 days' AND sale_date < CURRENT_DATE")
        row = cursor.fetchone()
        total_rev = row['rev'] if row and 'rev' in row else 0
        
        cursor.execute("""
            SELECT ROUND(COALESCE(SUM(CASE WHEN s.status='SALE' THEN (s.sold_price - p.selling_price) * s.quantity WHEN s.status='RETURNED' THEN -((s.sold_price - p.selling_price) * s.quantity) ELSE 0 END), 0), 2) as profit
            FROM Sales s JOIN Products p ON s.product_id = p.id
            WHERE s.sale_date >= CURRENT_DATE - INTERVAL '7 days' AND s.sale_date < CURRENT_DATE AND s.status IN ('SALE', 'RETURNED')
        """)
        row = cursor.fetchone()
        net_prof = row['profit'] if row and 'profit' in row else 0
        
        cursor.execute("SELECT COALESCE(SUM(stock), 0) as vault FROM ProductSizes ps JOIN Products p ON ps.product_id = p.id WHERE p.is_active = TRUE")
        row = cursor.fetchone()
        vault_stock = row['vault'] if row and 'vault' in row else 0
        
        cursor.execute("SELECT ROUND(COALESCE(SUM(p.selling_price * ps.stock), 0), 2) as investment FROM ProductSizes ps JOIN Products p ON ps.product_id = p.id WHERE p.is_active = TRUE")
        row = cursor.fetchone()
        total_investment = row['investment'] if row and 'investment' in row else 0
        
        cursor.execute("""
            INSERT INTO WeeklyMetrics (total_pairs_sold, total_revenue, net_profit, current_vault_stock, current_total_investment)
            VALUES (%s, %s, %s, %s, %s)
        """, (total_pairs_sold, total_rev, net_prof, vault_stock, total_investment))
        
        conn.commit()
        print(f"[{datetime.datetime.now()}] WEEKLY METRICS SAVED: {total_pairs_sold} pairs, Revenue: {total_rev}, Profit: {net_prof}")
        
    except Exception as e:
        print("SCHEDULER LOGIC ERROR:", e)
        conn.rollback()
    finally:
        release_db_connection(conn)

# Enterprise Heartbeat & Cache Refresh (Zero-Crash Architecture)
def enterprise_heartbeat():
    try:
        print(f"[{datetime.datetime.now()}] ENTERPRISE HEARTBEAT: System Healthy.")
        # Auto-refresh analytics & history every heartbeat cycle
        get_consolidated_analytics()
        get_consolidated_history()
    except Exception as e:
        print(f"Heartbeat Logic Failure: {e}")

scheduler = BackgroundScheduler()
# 1. Weekly Snapshot (Monday Morning)
scheduler.add_job(func=record_weekly_snapshot, trigger="cron", day_of_week='mon', hour=0, minute=1)
# 2. Enterprise Heartbeat (Keep-Alive + Cache Refresh) every 3 minutes
scheduler.add_job(func=enterprise_heartbeat, trigger="interval", minutes=3)

# Safe Startup Block (Professional Resilience)
def startup_checks():
    try:
        init_db()
        print("Professional Initialization: DB migrated successfully.")
        # Trigger immediate cache warm-up
        enterprise_heartbeat()
        if not scheduler.running:
            scheduler.start()
            print("Professional Initialization: Background Scheduler active.")
    except Exception as e:
        print(f"Startup Logic Error: {e}")

# Use daemon thread to initialize in background so first request wins immediately
import threading
threading.Thread(target=startup_checks, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
