import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from db import get_db_connection, init_db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-dev-key')
OWNER_PASSWORD = os.environ.get('OWNER_PASSWORD', 'admin123')
UPLOAD_FOLDER = os.path.join('static', 'images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
    conn = get_db_connection()
    if not conn: return jsonify({"error": "No DB"}), 500
    cursor = conn.cursor()
    
    # Total Products
    cursor.execute("SELECT COUNT(*) FROM Products WHERE is_active=1")
    total_products = cursor.fetchone()[0]
    
    # Total Current Stock (sum of all sizes of active products)
    cursor.execute("""
        SELECT ISNULL(SUM(ps.stock), 0) FROM ProductSizes ps
        JOIN Products p ON ps.product_id = p.id
        WHERE p.is_active=1
    """)
    total_stock = cursor.fetchone()[0]
    
    # Low stock count
    cursor.execute("""
        SELECT COUNT(*) FROM ProductSizes ps
        JOIN Products p ON ps.product_id = p.id
        WHERE p.is_active=1 AND ps.stock < 5
    """)
    low_stock_alerts = cursor.fetchone()[0]
    
    # Best Selling Article (All time)
    cursor.execute("""
        SELECT TOP 1 p.name, p.article_no, SUM(s.quantity) as sold
        FROM Sales s
        JOIN Products p ON s.product_id = p.id
        GROUP BY p.name, p.article_no
        ORDER BY sold DESC
    """)
    best = cursor.fetchone()
    best_seller = f"{best.name} ({best.article_no})" if best else "No sales yet"
    
    conn.close()
    return jsonify({
        "total_products": total_products,
        "total_stock": total_stock,
        "low_stock_alerts": low_stock_alerts,
        "best_seller": best_seller
    })

@app.route('/api/inventory')
def api_inventory():
    conn = get_db_connection()
    if not conn: return jsonify({"error": "No DB"}), 500
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name FROM Categories")
    categories = [{"id": row.id, "name": row.name} for row in cursor.fetchall()]
    
    query = """
    SELECT p.id, p.name, p.article_no, p.category_id, c.name as category_name, p.gender, p.image_path, p.mrp, p.default_discount, p.selling_price
    FROM Products p
    LEFT JOIN Categories c ON p.category_id = c.id
    WHERE p.is_active = 1
    """
    cursor.execute(query)
    products = []
    product_map = {}
    for row in cursor.fetchall():
        p = {
            "id": row.id,
            "name": row.name,
            "article_no": row.article_no,
            "category_id": row.category_id,
            "category_name": row.category_name,
            "gender": row.gender,
            "image_path": row.image_path,
            "mrp": float(row.mrp) if row.mrp else 0,
            "default_discount": float(row.default_discount) if row.default_discount else 0,
            "selling_price": float(row.selling_price) if row.selling_price else 0,
            "total_stock": 0,
            "sizes": []
        }
        products.append(p)
        product_map[row.id] = p
        
    cursor.execute("""
        SELECT ps.id, ps.product_id, ps.size, ps.stock 
        FROM ProductSizes ps
        JOIN Products p ON ps.product_id = p.id
        WHERE p.is_active=1
    """)
    for row in cursor.fetchall():
        if row.product_id in product_map:
            product_map[row.product_id]['sizes'].append({
                "id": row.id, "product_id": row.product_id, "size": row.size, "stock": row.stock
            })
            product_map[row.product_id]['total_stock'] += row.stock
            
    for p in products:
        p['sizes'] = sorted(p['sizes'], key=lambda x: x['size'])
        
    conn.close()
    return jsonify({"categories": categories, "products": products})

@app.route('/api/categories', methods=['POST'])
def api_add_category():
    name = request.json.get('name')
    if not name: return jsonify({"error": "Name required"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Categories (name) OUTPUT INSERTED.id VALUES (?)", (name,))
        new_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"id": new_id, "name": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally: conn.close()

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
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM Products WHERE article_no = ?", (article_no,))
    if cursor.fetchone():
        conn.close()
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
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (name, article_no, category_id, gender, image_path, mrp, default_discount, selling_price))
        product_id = cursor.fetchone()[0]
        
        for sObj in sizes_data:
            cursor.execute("INSERT INTO ProductSizes (product_id, size, stock) VALUES (?, ?, ?)", 
                           (product_id, float(sObj['size']), int(sObj['stock'])))
            
        conn.commit()
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/products/<int:id>/image', methods=['POST'])
def api_update_product_image(id):
    image = request.files.get('image')
    if not image or not image.filename:
        return jsonify({"error": "No image provided"}), 400
        
    filename = secure_filename(image.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image.save(path)
    image_path = f"images/{filename}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Products SET image_path = ? WHERE id = ?", (image_path, id))
        conn.commit()
        return jsonify({"success": True, "image_path": image_path})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/products/<int:id>/image/remove', methods=['POST'])
def api_remove_product_image(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Products SET image_path = NULL WHERE id = ?", (id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/stock/adjust_batch', methods=['POST'])
def api_adjust_stock_batch():
    data = request.json
    updates = data.get('updates', [])
    if not updates:
        return jsonify({"error": "No updates provided"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for up in updates:
            amount = int(up.get('amount', 0))
            if amount <= 0: continue
            
            if up.get('is_new'):
                product_id = up.get('product_id')
                size = float(up.get('size'))
                
                # Check for accidental duplicates
                cursor.execute("SELECT id FROM ProductSizes WHERE product_id = ? AND size = ?", (product_id, size))
                existing_size = cursor.fetchone()
                if existing_size:
                    cursor.execute("UPDATE ProductSizes SET stock = stock + ? WHERE id = ?", (amount, existing_size.id))
                else:
                    cursor.execute("INSERT INTO ProductSizes (product_id, size, stock) VALUES (?, ?, ?)", (product_id, size, amount))
            else:
                size_id = up.get('size_id')
                cursor.execute("UPDATE ProductSizes SET stock = stock + ? WHERE id = ?", (amount, size_id))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/products/remove', methods=['POST'])
def api_remove_product():
    product_id = request.json.get('product_id')
    if not product_id: return jsonify({"error": "Missing product_id"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Products SET is_active = 0 WHERE id = ?", (product_id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally: conn.close()

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
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT product_id, size, stock FROM ProductSizes WHERE id = ?", (size_id,))
        row = cursor.fetchone()
        if not row: return jsonify({"error": "Size not found"}), 404
            
        if operation == 'subtract' and row.stock < amount:
            return jsonify({"error": "Not enough stock!"}), 400
            
        new_stock = row.stock + amount if operation == 'add' else row.stock - amount
        cursor.execute("UPDATE ProductSizes SET stock = ? WHERE id = ?", (new_stock, size_id))
        
        if operation == 'subtract':
            cursor.execute("""
                INSERT INTO Sales (product_id, size, quantity, sold_price, discount_applied)
                VALUES (?, ?, ?, ?, ?)
            """, (row.product_id, row.size, amount, float(sold_price) if sold_price else 0, float(discount_applied) if discount_applied else 0))
            
        conn.commit()
        return jsonify({"success": True, "new_stock": new_stock})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/sales_advanced')
def api_sales_advanced():
    conn = get_db_connection()
    if not conn: return jsonify({"error": "No DB"}), 500
    cursor = conn.cursor()
    try:
        # Daily Analytics
        cursor.execute("""
            SELECT 
                ISNULL(SUM(s.quantity), 0) as pairs_today,
                COUNT(DISTINCT s.product_id) as unique_pairs_today,
                ISNULL(SUM(s.sold_price * s.quantity), 0) as rev_today,
                ISNULL(SUM(CASE WHEN s.sold_price >= p.selling_price THEN (s.sold_price - p.selling_price) * s.quantity ELSE 0 END), 0) as gains_today,
                ISNULL(SUM(CASE WHEN s.sold_price < p.selling_price THEN (s.sold_price - p.selling_price) * s.quantity ELSE 0 END), 0) as losses_today
            FROM Sales s JOIN Products p ON s.product_id = p.id
            WHERE CAST(s.sale_date AS DATE) = CAST(GETDATE() AS DATE)
        """)
        dr = cursor.fetchone()
        daily = {
            "pairs": dr.pairs_today, 
            "unique_pairs": dr.unique_pairs_today, 
            "revenue": float(dr.rev_today), 
            "profit": float(dr.gains_today),
            "surplus_loss": float(dr.losses_today)
        }
        
        # Weekly Analytics
        cursor.execute("""
            SELECT 
                ISNULL(SUM(s.quantity), 0) as pairs_week,
                COUNT(DISTINCT s.product_id) as unique_pairs_week,
                ISNULL(SUM(s.sold_price * s.quantity), 0) as rev_week,
                ISNULL(SUM(CASE WHEN s.sold_price >= p.selling_price THEN (s.sold_price - p.selling_price) * s.quantity ELSE 0 END), 0) as gains_week,
                ISNULL(SUM(CASE WHEN s.sold_price < p.selling_price THEN (s.sold_price - p.selling_price) * s.quantity ELSE 0 END), 0) as losses_week
            FROM Sales s JOIN Products p ON s.product_id = p.id
            WHERE DATEPART(WEEK, s.sale_date) = DATEPART(WEEK, GETDATE()) AND YEAR(s.sale_date) = YEAR(GETDATE())
        """)
        wr = cursor.fetchone()
        weekly = {
            "pairs": wr.pairs_week, 
            "unique_pairs": wr.unique_pairs_week, 
            "revenue": float(wr.rev_week), 
            "profit": float(wr.gains_week),
            "surplus_loss": float(wr.losses_week)
        }     
        # Stock Analytics
        cursor.execute("SELECT COUNT(*) FROM Products WHERE is_active=1")
        total_p = cursor.fetchone()[0]
        
        cursor.execute("SELECT ISNULL(SUM(stock),0) FROM ProductSizes ps JOIN Products p ON ps.product_id=p.id WHERE p.is_active=1")
        total_s = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT p.name, p.article_no, ps.size, ps.stock 
            FROM ProductSizes ps JOIN Products p ON ps.product_id = p.id 
            WHERE p.is_active=1 AND ps.stock < 5
        """)
        low_stock = [{"name": r.name, "article": r.article_no, "size": r.size, "stock": r.stock} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT p.article_no, p.name, ISNULL(SUM(ps.stock),0) as total_stock
            FROM Products p LEFT JOIN ProductSizes ps ON p.id = ps.product_id
            WHERE p.is_active=1
            GROUP BY p.article_no, p.name
            ORDER BY total_stock DESC
        """)
        all_stock = [{"article": r.article_no, "name": r.name, "stock": r.total_stock} for r in cursor.fetchall()]
        
        # Article-Based Analytics
        cursor.execute("""
            SELECT p.article_no, 
                   SUM(s.quantity) AS total_qty, 
                   SUM(p.mrp * s.quantity) AS total_mrp, 
                   SUM(s.sold_price * s.quantity) AS revenue, 
                   AVG(s.discount_applied) AS avg_discount
            FROM Sales s JOIN Products p ON s.product_id = p.id
            GROUP BY p.article_no
        """)
        article_profit = [
            {
                "article_no": r.article_no, 
                "qty": r.total_qty, 
                "revenue": float(r.revenue) if r.revenue else 0, 
                "profit": float(r.avg_discount) if r.avg_discount is not None else 0
            } 
            for r in cursor.fetchall()
        ]
        
        # 7-Day Chart Trend
        cursor.execute("""
            SELECT CAST(sale_date AS DATE) as d, ISNULL(SUM(quantity), 0)
            FROM Sales
            WHERE sale_date >= DATEADD(day, -6, CAST(GETDATE() AS DATE))
            GROUP BY CAST(sale_date AS DATE)
            ORDER BY d
        """)
        trend_rows = cursor.fetchall()
        chart_labels = [row.d.strftime('%a') if row.d else '?' for row in trend_rows]
        chart_data = [row[1] for row in trend_rows]

        return jsonify({
            "daily": daily,
            "weekly": weekly,
            "chart": {"labels": chart_labels, "data": chart_data},
            "stock": {"total_products": total_p, "total_stock": total_s, "low_stock": low_stock, "all_stock": all_stock},
            "articles": article_profit
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/sales_history')
def sales_history():
    return render_template('sales_history.html', active_page='sales_history')

@app.route('/api/sales_history')
def api_sales_history():
    conn = get_db_connection()
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
            "id": r.id, "date": r.sale_date.isoformat() if r.sale_date else "",
            "article": r.article_no, "name": r.name,
            "size": r.size, "qty": r.quantity,
            "mrp": float(r.mrp) if r.mrp is not None else 0,
            "sold_price": float(r.sold_price) if r.sold_price is not None else 0,
            "discount": float(r.discount_applied) if r.discount_applied is not None else 0
        })
    conn.close()
    return jsonify(sales)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000, host='0.0.0.0')
