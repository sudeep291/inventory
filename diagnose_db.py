"""Full Firestore DB diagnostic - every collection, every operation."""
import requests
import json as jsonlib

base = 'http://127.0.0.1:5000'
s = requests.Session()
PASS = 'admin1983'
ERRORS = []

def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    if not condition:
        ERRORS.append(name + ': ' + detail)
    msg = '  [' + status + '] ' + name
    if detail:
        msg += ' -- ' + str(detail)
    print(msg)

print('\n' + '='*60)
print('FIREBASE FIRESTORE FULL DIAGNOSTIC')
print('='*60)

# 1. LOGIN
print('\n[1] AUTH')
r = s.post(base + '/login', data={'password': PASS})
check('Owner login', r.status_code == 200)

# 2. FIRESTORE CONNECTION
print('\n[2] FIRESTORE CONNECTION')
r = s.get(base + '/ping')
check('App is alive /ping', r.status_code == 200 and r.text == 'SYSTEM_HEALTHY')
r = s.get(base + '/api/inventory')
check('Firestore reads OK', r.status_code == 200, r.text[:80] if r.status_code != 200 else '')
inv = r.json() if r.status_code == 200 else {}
check('Response has categories key', 'categories' in inv)
check('Response has products key', 'products' in inv)

# 3. WRITE CATEGORY
print('\n[3] WRITE: Category')
r = s.post(base + '/api/categories', json={'name': 'DiagnosticCategory'})
check('Add category', r.status_code == 200, r.text[:80] if r.status_code != 200 else '')
cat_data = r.json() if r.status_code == 200 else {}
cat_id = cat_data.get('id')
check('Category has ID', bool(cat_id))

# 4. WRITE PRODUCT
print('\n[4] WRITE: Product')
sizes = jsonlib.dumps([{'size': 7, 'stock': 20}, {'size': 8, 'stock': 15}, {'size': 9, 'stock': 5}])
r = s.post(base + '/api/products', data={
    'name': 'DiagnosticShoe', 'article_no': 'DIAG-001',
    'category_id': cat_id, 'gender': 'Men',
    'mrp': '2000', 'default_discount': '10', 'sizes_json': sizes
})
check('Add product', r.status_code == 200, r.text[:80] if r.status_code != 200 else '')

# 5. READ AND VERIFY
print('\n[5] READ: Product verification')
r = s.get(base + '/api/inventory')
inv2 = r.json()
prods = inv2.get('products', [])
test_prod = next((p for p in prods if p.get('article_no') == 'DIAG-001'), None)
check('Product found in inventory', test_prod is not None)
if test_prod:
    check('Product has 3 sizes', len(test_prod.get('sizes', [])) == 3)
    check('Total stock = 40', test_prod.get('total_stock') == 40)
    check('MRP correct 2000', float(test_prod.get('mrp', 0)) == 2000.0)
    check('Selling price correct 1800', float(test_prod.get('selling_price', 0)) == 1800.0)
    check('Category name populated', bool(test_prod.get('category_name')))

# 6. SELL / STOCK SUBTRACT
print('\n[6] WRITE: Sell stock')
if test_prod and test_prod.get('sizes'):
    size_id = test_prod['sizes'][0]['id']
    r = s.post(base + '/api/stock/adjust', json={
        'size_id': size_id, 'amount': 3,
        'operation': 'subtract', 'sold_price': 1750, 'discount_applied': 5
    })
    check('Sell 3 pairs', r.status_code == 200, r.text[:80] if r.status_code != 200 else '')

    r = s.get(base + '/api/inventory')
    updated = next((p for p in r.json()['products'] if p['article_no'] == 'DIAG-001'), None)
    if updated:
        new_stock = updated['sizes'][0]['stock']
        check('Stock reduced 20 to 17', new_stock == 17, 'Got ' + str(new_stock))
        check('Total stock now 37', updated['total_stock'] == 37, 'Got ' + str(updated['total_stock']))

# 7. DUPLICATE PROTECTION
print('\n[7] INTEGRITY: Duplicate protection')
r = s.post(base + '/api/products', data={
    'name': 'Dupe', 'article_no': 'DIAG-001',
    'category_id': cat_id, 'gender': 'Men',
    'mrp': '500', 'default_discount': '5', 'sizes_json': sizes
})
check('Duplicate article_no rejected', r.status_code == 400, 'Got ' + str(r.status_code))
r = s.post(base + '/api/categories', json={'name': 'DiagnosticCategory'})
check('Duplicate category rejected', r.status_code == 400, 'Got ' + str(r.status_code))

# 8. ANALYTICS
print('\\n[8] ANALYTICS ENGINE')
import time
time.sleep(2) # Allow cache invalidation thread to run
r = s.get(base + '/api/sales_advanced')
check('Analytics endpoint OK', r.status_code == 200, r.text[:80] if r.status_code != 200 else '')
if r.status_code == 200:
    d = r.json()
    check('Has daily key', 'daily' in d)
    check('Has weekly key', 'weekly' in d)
    check('Has chart key', 'chart' in d)
    check('Has stock key', 'stock' in d)
    check('Has articles key', 'articles' in d)
    rev = d.get('daily', {}).get('revenue', 0)
    check('Daily revenue > 0 (sale recorded)', rev > 0, 'Got ' + str(rev))

# 9. HEATMAP
print('\n[9] HEATMAP')
r = s.get(base + '/api/analytics/heatmap')
check('Heatmap OK', r.status_code == 200)
if r.status_code == 200:
    hd = r.json()
    check('Heatmap success flag', hd.get('success') == True)
    check('Heatmap has data', len(hd.get('data', [])) > 0)

# 10. SALES HISTORY
print('\n[10] SALES HISTORY')
r = s.get(base + '/api/sales_history')
check('Sales history OK', r.status_code == 200)
if r.status_code == 200:
    hist = r.json()
    check('At least 1 sale recorded', len(hist) >= 1, 'Got ' + str(len(hist)) + ' records')
    if hist:
        sale = hist[0]
        check('Sale has article', bool(sale.get('article')))
        check('Sale has sold_price', sale.get('sold_price', 0) > 0)
        check('Sale has status', bool(sale.get('status')))

# 11. STATS WIDGET
print('\n[11] STATS WIDGET')
r = s.get(base + '/api/stats')
check('Stats OK', r.status_code == 200)
if r.status_code == 200:
    st = r.json()
    check('total_products >= 1', st.get('total_products', 0) >= 1)
    check('total_stock >= 1', st.get('total_stock', 0) >= 1)
    check('best_seller not empty', bool(st.get('best_seller')))

# 12. RETURNS
print('\n[12] RETURNS STATS')
r = s.get(base + '/api/returns/stats')
check('Returns stats OK', r.status_code == 200)

# 13. CLEANUP
print('\\n[13] CLEANUP')
# r = s.get(base + '/admin/factory_reset?confirm=admin1983')
# check('Factory reset cleanup', r.status_code == 200)

# SUMMARY
print('\n' + '='*60)
if ERRORS:
    print('RESULT: ' + str(len(ERRORS)) + ' ISSUE(S) FOUND:')
    for e in ERRORS:
        print('  FAIL: ' + e)
else:
    print('RESULT: ALL CHECKS PASSED -- Firestore DB is fully working!')
print('='*60 + '\n')
