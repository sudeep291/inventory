from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
import os
import datetime
import decimal
import traceback
from flask.json.provider import DefaultJSONProvider
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from db import get_db_connection, init_db, release_db_connection
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

# Custom JSON Encoder for Decimal support (Postgres compatibility)
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)

app = Flask(__name__)
app.json = CustomJSONProvider(app)
app.secret_key = os.environ.get('SECRET_KEY', 'default-dev-key')
OWNER_PASSWORD = os.environ.get('OWNER_PASSWORD', 'admin123')
UPLOAD_FOLDER = os.path.join('static', 'images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

# ==========================================
# API ENDPOINTS
# ==========================================

@app.route('/api/stats')
def api_stats():
    conn = get_db()
    if not conn: return jsonify({"error": "No DB"}), 500
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
    
    return jsonify({
        "total_products": total_products,
        "total_stock": total_stock,
        "low_stock_alerts": low_stock_alerts,
        "best_seller": best_seller
    })

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
    name = request.json.get('name')
    if not name: return jsonify({"error": "Name required"}), 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Categories (name) VALUES (%s) RETURNING id", (name,))
        new_row = cursor.fetchone()
        new_id = new_row['id']
        conn.commit()
        return jsonify({"id": new_id, "name": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/products', methods=['POST'])
def api_add_product():
    name = request.form.get('name')
    article_no = request.form.get('article_no')
    category_id = request.form.get('category_id')
    gender = request.form.get('gender')
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
        
    mrp = float(mrp)
    default_discount = float(default_discount)
    image_path = None
    if image and image.filename:
        filename = secure_filename(image.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(path)
        image_path = f"images/{filename}"
        
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
        
    filename = secure_filename(image.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image.save(path)
    image_path = f"images/{filename}"
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Products SET image_path = %s WHERE id = %s", (image_path, id))
        conn.commit()
        return jsonify({"success": True, "image_path": image_path})
    except Exception as e:
        conn.rollback()
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
def api_adjust_stock_batch():
    data = request.json
    updates = data.get('updates', [])
    if not updates:
        return jsonify({"error": "No updates provided"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    try:
        for up in updates:
            amount = int(up.get('amount', 0))
            if amount <= 0: continue
            
            if up.get('is_new'):
                product_id = up.get('product_id')
                size = float(up.get('size'))
                
                # Check for accidental duplicates
                cursor.execute("SELECT id FROM ProductSizes WHERE product_id = %s AND size = %s", (product_id, size))
                existing_size = cursor.fetchone()
                if existing_size:
                    cursor.execute("UPDATE ProductSizes SET stock = stock + %s WHERE id = %s", (amount, existing_size['id']))
                else:
                    cursor.execute("INSERT INTO ProductSizes (product_id, size, stock) VALUES (%s, %s, %s)", (product_id, size, amount))
            else:
                size_id = up.get('size_id')
                cursor.execute("UPDATE ProductSizes SET stock = stock + %s WHERE id = %s", (amount, size_id))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400

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
            
        new_stock = row['stock'] + amount if operation == 'add' else row['stock'] - amount
        cursor.execute("UPDATE ProductSizes SET stock = %s WHERE id = %s", (new_stock, size_id))
        
        if operation == 'subtract':
            cursor.execute("""
                INSERT INTO Sales (product_id, size, quantity, sold_price, discount_applied)
                VALUES (%s, %s, %s, %s, %s)
            """, (row['product_id'], row['size'], amount, float(sold_price) if sold_price else 0, float(discount_applied) if discount_applied else 0))
            
        conn.commit()
        return jsonify({"success": True, "new_stock": new_stock})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/sales_advanced')
def api_sales_advanced():
    conn = get_db()
    if not conn: return jsonify({"error": "No DB"}), 500
    cursor = conn.cursor()
    try:
        # Daily Analytics
        cursor.execute("""
            SELECT 
                COALESCE(SUM(s.quantity), 0) as pairs_today,
                COUNT(DISTINCT s.product_id) as unique_pairs_today,
                COALESCE(SUM(s.sold_price * s.quantity), 0) as rev_today,
                COALESCE(SUM(CASE WHEN s.sold_price > p.selling_price THEN (s.sold_price - p.selling_price) * s.quantity ELSE 0 END), 0) as gains_today,
                COALESCE(SUM(CASE WHEN s.sold_price < p.selling_price THEN (p.selling_price - s.sold_price) * s.quantity ELSE 0 END), 0) as losses_today,
                COALESCE(SUM((s.sold_price - p.selling_price) * s.quantity), 0) as net_surplus_today
            FROM Sales s JOIN Products p ON s.product_id = p.id
            WHERE DATE(s.sale_date) = CURRENT_DATE
        """)
        dr = cursor.fetchone()
        daily = {
            "pairs": dr['pairs_today'], 
            "unique_pairs": dr['unique_pairs_today'], 
            "revenue": dr['rev_today'], 
            "profit": max(0, dr['net_surplus_today']),
            "surplus_loss": dr['net_surplus_today'] # Net Surplus Margin
        }
        
        # Weekly Analytics
        cursor.execute("""
            SELECT 
                COALESCE(SUM(s.quantity), 0) as pairs_week,
                COALESCE(SUM(s.sold_price * s.quantity), 0) as rev_week,
                COALESCE(SUM((s.sold_price - p.selling_price) * s.quantity), 0) as net_surplus_week
            FROM Sales s JOIN Products p ON s.product_id = p.id
            WHERE EXTRACT(WEEK FROM s.sale_date) = EXTRACT(WEEK FROM CURRENT_DATE) 
              AND EXTRACT(YEAR FROM s.sale_date) = EXTRACT(YEAR FROM CURRENT_DATE)
        """)
        wr = cursor.fetchone()
        weekly = {
            "pairs": float(wr['pairs_week']), 
            "revenue": float(wr['rev_week']), 
            "profit": float(wr['net_surplus_week'])
        }
        
        # Overall Stock & Asset Analytics (SaaS Intelligence)
        # Total Investment: SUM(Strategy Price * Current Stock)
        # Potential Revenue: SUM(MRP * Current Stock)
        cursor.execute("""
            SELECT 
                COALESCE(SUM(p.selling_price * ps.stock), 0) as total_investment,
                COALESCE(SUM(p.mrp * ps.stock), 0) as potential_revenue,
                COUNT(DISTINCT p.id) as total_variants,
                COALESCE(SUM(ps.stock), 0) as total_pairs
            FROM ProductSizes ps
            JOIN Products p ON ps.product_id = p.id
            WHERE p.is_active = TRUE
        """)
        sr = cursor.fetchone()
        stock_summary = {
            "total_products": sr['total_variants'],
            "total_stock": sr['total_pairs'],
            "total_investment": sr['total_investment'],
            "potential_revenue": sr['potential_revenue']
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
        
        # Article-Based Analytics
        cursor.execute("""
            SELECT p.article_no, 
                   SUM(s.quantity) AS total_qty, 
                   SUM(s.sold_price * s.quantity) AS revenue, 
                   SUM((s.sold_price - p.selling_price) * s.quantity) AS article_surplus
            FROM Sales s JOIN Products p ON s.product_id = p.id
            GROUP BY p.article_no
        """)
        article_profit = [
            {
                "article_no": r['article_no'], 
                "qty": r['total_qty'], 
                "revenue": r['revenue'], 
                "profit": r['article_surplus']
            } 
            for r in cursor.fetchall()
        ]
        
        # 7-Day Chart Trend (Postgres style)
        cursor.execute("""
            SELECT DATE(sale_date) as d, COALESCE(SUM(quantity), 0) as qty
            FROM Sales
            WHERE sale_date >= CURRENT_DATE - INTERVAL '6 days'
            GROUP BY DATE(sale_date)
            ORDER BY d
        """)
        trend_rows = cursor.fetchall()
        chart_labels = [row['d'].strftime('%a') if row['d'] else '?' for row in trend_rows]
        chart_data = [row['qty'] for row in trend_rows]

        return jsonify({
            "daily": daily,
            "weekly": weekly,
            "chart": {"labels": chart_labels, "data": chart_data},
            "stock": stock_summary,
            "low_stock_list": low_stock,
            "all_stock_list": all_stock,
            "articles": article_profit
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/sales_history')
def sales_history():
    return render_template('sales_history.html', active_page='sales_history')

@app.route('/api/sales_history')
def api_sales_history():
    conn = get_db()
    if not conn: return jsonify({"error": "No DB"}), 500
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.sale_date, p.article_no, p.name, s.size, s.quantity, 
               p.mrp, s.sold_price, s.discount_applied
        FROM Sales s
        JOIN Products p ON s.product_id = p.id
        ORDER BY s.sale_date DESC
    """)
    rows = cursor.fetchall()
    sales = []
    for r in rows:
        sales.append({
            "id": r['id'], "date": r['sale_date'].isoformat() if r['sale_date'] else "",
            "article": r['article_no'], "name": r['name'],
            "size": r['size'], "qty": r['quantity'],
            "mrp": r['mrp'],
            "sold_price": r['sold_price'],
            "discount": r['discount_applied']
        })
    return jsonify(sales)

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
        
        cursor.execute("SELECT COALESCE(SUM(quantity), 0) as pairs FROM Sales")
        row = cursor.fetchone()
        total_pairs_sold = row['pairs'] if row and 'pairs' in row else 0
        
        cursor.execute("SELECT COALESCE(SUM(sold_price * quantity), 0) as rev FROM Sales")
        row = cursor.fetchone()
        total_rev = row['rev'] if row and 'rev' in row else 0
        
        cursor.execute("""
            SELECT COALESCE(SUM((s.sold_price - p.selling_price) * s.quantity), 0) as profit
            FROM Sales s JOIN Products p ON s.product_id = p.id
        """)
        row = cursor.fetchone()
        net_prof = row['profit'] if row and 'profit' in row else 0
        
        cursor.execute("SELECT COALESCE(SUM(stock), 0) as vault FROM ProductSizes ps JOIN Products p ON ps.product_id = p.id WHERE p.is_active = TRUE")
        row = cursor.fetchone()
        vault_stock = row['vault'] if row and 'vault' in row else 0
        
        cursor.execute("SELECT COALESCE(SUM(p.selling_price * ps.stock), 0) as investment FROM ProductSizes ps JOIN Products p ON ps.product_id = p.id WHERE p.is_active = TRUE")
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

scheduler = BackgroundScheduler()
# Runs every Monday at 12:01 AM (00:01)
scheduler.add_job(func=record_weekly_snapshot, trigger="cron", day_of_week='mon', hour=0, minute=1)
scheduler.start()

# Initialize DB tables before starting
init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
