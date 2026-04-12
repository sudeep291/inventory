import requests, time
base = 'http://127.0.0.1:5000'
s = requests.Session()
s.post(base + '/login', data={'password': 'admin1983'})

s.post(base + '/api/categories', json={'name': 'TestCat1'})
cat_id = s.get(base + '/api/inventory').json()['categories'][0]['id']

s.post(base + '/api/products', data={
    'name': 'TestProd1', 'article_no': 'TEST-002', 'category_id': cat_id, 'gender': 'Men',
    'mrp': 1000, 'sizes_json': '[{"size": 7, "stock": 10}]'
})
prods = s.get(base + '/api/inventory').json()['products']
target = next((p for p in prods if p['article_no'] == 'TEST-002'), None)
if target:
    size_id = target['sizes'][0]['id']

    s.post(base + '/api/stock/adjust', json={
        'size_id': size_id, 'amount': 1, 'operation': 'subtract',
        'sold_price': 500, 'discount_applied': 0
    })

    time.sleep(2)
    adv = s.get(base + '/api/sales_advanced').json()
    print('Daily revenue:', adv.get('daily', {}).get('revenue'))
    hist = s.get(base + '/api/sales_history').json()
    print('History 0 date:', hist[0].get('sale_date') if hist else None)
