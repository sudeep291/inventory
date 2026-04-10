// Global State
let productsCache = [];

function toMoney(amount) { return parseFloat(amount).toFixed(2); }
function getProfitClass(amount) {
    if (amount > 0) return 'text-profit';
    if (amount < 0) return 'text-loss';
    return 'text-neutral';
}

function showToast(message) {
    const toast = document.getElementById("toast");
    if(!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => { toast.classList.remove("show"); }, 3000);
}

// Function for visual success feedback sequence
function playSuccessSequence(containerId, message, callback) {
    const container = document.getElementById(containerId);
    const originalHTML = container.innerHTML;
    container.innerHTML = `
        <div class="success-trigger">
            <div class="check-icon">✓</div>
            <h2 style="color:#166534; font-weight:700">${message}</h2>
        </div>
    `;
    setTimeout(() => {
        container.style.display = 'none';
        container.innerHTML = originalHTML; // restore DOM layout invisibly
        if(callback) callback();
    }, 2000);
}

// Enterprise Global Fetch Wrapper (Zero-Silence Infrastructure)
async function fetchAPI(url, options = {}) {
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        if (!response.ok || data.error) {
            const errorMsg = data.error || `Server Error: ${response.status}`;
            showToast(`Error: ${errorMsg}`);
            return null;
        }
        return data;
    } catch (err) {
        console.error("Network Error:", err);
        showToast("Network connection busy. Please retry.");
        return null;
    }
}

async function fetchProducts() {
    const data = await fetchAPI('/api/inventory');
    if (data) productsCache = data.products;
}

/* ==================================
   INDEX.HTML / DASHBOARD
================================== */
async function loadWelcomeDashboard() {
    const data = await fetchAPI('/api/stats');
    if (!data) return;

    document.getElementById('dashCards').innerHTML = `
        <a href="/overview" class="summary-card" style="text-decoration:none"><h4>Total Products</h4><span class="val">${data.total_products}</span></a>
        <a href="/overview" class="summary-card" style="text-decoration:none"><h4>Total Global Stock</h4><span class="val">${data.total_stock}</span></a>
        <a href="/analytics" class="summary-card" style="text-decoration:none"><h4>Low Stock Alerts</h4><span class="val text-loss">${data.low_stock_alerts}</span></a>
        <a href="/analytics" class="summary-card" style="text-decoration:none"><h4>Best Seller</h4><span class="val text-profit" style="font-size:1.2rem">${data.best_seller}</span></a>
    `;
    
    const salesData = await fetchAPI('/api/sales_advanced');
    if (!salesData) return;
        let lsHTML = '';
        salesData.stock.low_stock.forEach(item => {
            lsHTML += `<tr>
                <td><strong>${item.article}</strong></td>
                <td>${item.name}</td>
                <td>UK ${item.size}</td>
                <td class="text-loss" style="font-weight:bold">${item.stock} left</td>
            </tr>`;
        });
        document.getElementById('lowStockAlerts').innerHTML = lsHTML || '<tr><td colspan="4" class="text-profit">All stock is healthy!</td></tr>';
    } 


/* ==================================
   OVERVIEW.HTML
================================== */
async function loadOverviewTable() {
    await fetchProducts();
    const grid = document.getElementById('overviewGrid');
    if(!grid) return;
    grid.innerHTML = '';
    
    productsCache.forEach(p => {
        let sizeHTML = '';
        p.sizes.forEach(s => {
            sizeHTML += `<span style="background:#f1f5f9; padding:0.25rem 0.5rem; border-radius:4px; font-size:0.8rem; font-weight:600; color:var(--text-secondary); margin-bottom:0.25rem;">UK ${s.size}: <span class="${s.stock<3?'text-loss':'text-primary'}">${s.stock}</span></span>`;
        });
        
        const card = document.createElement('div');
        card.className = 'product-card';
        
        let imageSectionHTML = '';
        if (p.image_path) {
            imageSectionHTML = `
            <div class="shimmer" style="position:relative; cursor:pointer; height:200px; background:var(--bg-surface); border-bottom:1px solid var(--border);" onmouseenter="this.querySelector('.upload-overlay').style.opacity='1'; this.querySelector('.delete-img-btn').style.opacity='1'" onmouseleave="this.querySelector('.upload-overlay').style.opacity='0'; this.querySelector('.delete-img-btn').style.opacity='0'" onclick="triggerImageUpload(${p.id})">
                <img class="prod-img lazy-img" data-src="/static/${p.image_path}" alt="${p.name}" style="width:100%; height:100%; object-fit:cover;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                
                <div id="fallback-${p.id}" style="display:none; width:100%; height:100%; flex-direction:column; align-items:center; justify-content:center; color:var(--text-secondary);">
                    <span style="font-size:3rem; margin-bottom:0.5rem;">📁</span>
                    <span style="font-weight:600; color:var(--primary)">Open Folder to Upload</span>
                </div>

                <div class="upload-overlay" style="position:absolute; inset:0; background:rgba(15,23,42,0.6); color:white; display:flex; flex-direction:column; align-items:center; justify-content:center; opacity:0; transition:0.3s; font-weight:700;">
                    <span style="font-size:2rem; margin-bottom:0.5rem;">📸</span>
                    Update Photo
                </div>
                
                <button class="delete-img-btn" style="position:absolute; top:0.5rem; right:0.5rem; background:#dc2626; color:white; border:none; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; cursor:pointer; opacity:0; transition:0.3s; z-index:10; box-shadow:0 2px 5px rgba(0,0,0,0.5);" onclick="event.stopPropagation(); removeProductImage(${p.id})" title="Remove Image">
                    <svg style="width:18px; height:18px" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>`;
        } else {
            imageSectionHTML = `
            <div style="position:relative; cursor:pointer; height:200px; background:var(--bg-surface); border-bottom:1px solid var(--border); display:flex; flex-direction:column; align-items:center; justify-content:center; color:var(--text-secondary); transition:background 0.3s;" onmouseenter="this.style.background='var(--border)'" onmouseleave="this.style.background='var(--bg-surface)'" onclick="triggerImageUpload(${p.id})">
                <img class="prod-img" id="img-${p.id}" style="display:none;" src="">
                <span style="font-size:3rem; margin-bottom:0.5rem;">📁</span>
                <span style="font-weight:600; color:var(--primary);">Open Folder to Upload</span>
            </div>`;
        }
        
        card.innerHTML = `
            ${imageSectionHTML}
            <div class="prod-info">
                <div class="prod-header">
                    <h3 style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${p.name}">${p.name}</h3>
                    <span class="badge" style="margin-left:0.5rem">${p.category_name}</span>
                </div>
                <div class="prod-meta"><strong>Art:</strong> <span class="val">${p.article_no}</span></div>
                <div class="prod-meta"><strong>MRP:</strong> <span class="val val-mrp">₹${toMoney(p.mrp)}</span></div>
                <div class="prod-meta"><strong>Base Strategy:</strong> <span class="val val-strategy">${p.default_discount}% Off</span></div>
                <div class="prod-meta" style="margin-bottom:1rem; padding-bottom:0.75rem; border-bottom:1px dashed var(--border);"><strong>Target Sold:</strong> <span class="val val-sold">₹${toMoney(p.selling_price)}</span></div>
                
                <div class="prod-meta"><strong>Total Stock:</strong> <span class="val text-primary" style="font-weight:700">${p.total_stock}</span></div>
                
                <div style="display:flex; flex-wrap:wrap; gap:0.25rem; border-top:1px solid var(--border); padding-top:1rem;">
                    ${sizeHTML || '<span style="color:var(--text-secondary); font-size:0.85rem">No active sizes</span>'}
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

function triggerImageUpload(productId) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if(!file) return;
        
        const imgEl = document.getElementById(`img-${productId}`);
        const originalSrc = imgEl.src;
        imgEl.src = 'https://via.placeholder.com/300x200?text=Uploading...';
        
        const formData = new FormData();
        formData.append('image', file);
        const data = await fetchAPI(`/api/products/${productId}/image`, { method: 'POST', body: formData });
        if(data && data.success) {
            imgEl.src = `/static/${data.image_path}?t=${new Date().getTime()}`;
            showToast("Product Image Updated!");
        } else {
            imgEl.src = originalSrc;
        }
    };
    input.click();
}

async function removeProductImage(productId) {
    if(!confirm("Are you sure you want to remove this product's image?")) return;
    const data = await fetchAPI(`/api/products/${productId}/image/remove`, { method: 'POST' });
    if(data && data.success) {
        showToast("Product image removed successfully!");
        await loadOverviewTable();
    }
}

/* ==================================
   INVENTORY.HTML (SELL)
================================== */
let selectedSellProductMRP = 0;

async function searchSellProduct() {
    if(productsCache.length === 0) await fetchProducts();
    const q = document.getElementById('sellSearchInput').value.trim().toLowerCase();
    if(!q) return;

    const prod = productsCache.find(p => p.article_no.toLowerCase() === q);
    const container = document.getElementById('sellResultContainer');
    
    if(!prod) {
        showToast("Article Not Found!");
        container.style.display = 'none';
        return;
    }
    
    document.getElementById('sellResName').textContent = prod.name;
    document.getElementById('sellResMRP').textContent = toMoney(prod.mrp);
    document.getElementById('sellResBaseDisc').textContent = prod.default_discount; // Show as raw % number
    document.getElementById('sellResSold').textContent = toMoney(prod.selling_price || (prod.mrp - (prod.mrp * prod.default_discount / 100)));
    document.getElementById('sellResImg').src = prod.image_path ? `/static/${prod.image_path}` : 'https://via.placeholder.com/300x200?text=No+Image';
    selectedSellProductMRP = prod.mrp;
    
    // Auto-fill Item Sold For with Default Strategy Price
    const defaultSP = prod.selling_price || (prod.mrp - (prod.mrp * prod.default_discount / 100));
    document.getElementById('sale_sp').value = defaultSP.toFixed(2);
    document.getElementById('sale_discount').value = prod.default_discount;
    
    const sizesContainer = document.getElementById('sellResSizes');
    sizesContainer.innerHTML = '';
    prod.sizes.forEach(s => {
        const span = document.createElement('div');
        span.className = 'exec-size-item';
        span.textContent = `UK ${s.size} (${s.stock} left)`;
        span.onclick = () => {
            document.querySelectorAll('#sellResSizes .exec-size-item').forEach(el=>el.classList.remove('selected'));
            span.classList.add('selected');
            document.getElementById('executeSaleForm').style.display = 'block';
            document.getElementById('sale_size_id').value = s.id;
            calcSalePreview();
        };
        sizesContainer.appendChild(span);
    });
    
    container.style.display = 'block';
    container.classList.remove('animate-fade-up');
    void container.offsetWidth; // Reflow reset
    container.classList.add('animate-fade-up');
    
    document.getElementById('executeSaleForm').style.display = 'none';
}

function calcSaleFromPrice() {
    const qty = parseFloat(document.getElementById('sale_qty').value) || 0;
    const mrp = selectedSellProductMRP || 0;
    const soldPrice = parseFloat(document.getElementById('sale_sp').value) || 0;
    const profitEl = document.getElementById('salePreviewVal');
    
    if(qty <= 0 || mrp <= 0 || soldPrice <= 0) {
        profitEl.textContent = 'Awaiting Input...'; 
        profitEl.className = 'text-neutral'; 
        return;
    }
    
    // Calculate effective discount percentage for strategy indicator
    const discount = ((mrp - soldPrice) / mrp) * 100;
    document.getElementById('sale_discount').value = discount.toFixed(2);
    
    if (discount < 10) {
        profitEl.innerHTML = `🟢 Premium Strat (${discount.toFixed(1)}%)`;
        profitEl.className = 'text-profit';
    } else if (discount <= 25) {
        profitEl.innerHTML = `🟡 Standard Strat (${discount.toFixed(1)}%)`;
        profitEl.className = 'text-neutral';
    } else {
        profitEl.innerHTML = `🔴 Clearance Risk (${discount.toFixed(1)}%)`;
        profitEl.className = 'text-loss';
    }
}

function calcSalePreview() {
    // This is called when Qty changes. It just re-runs the price logic.
    calcSaleFromPrice();
}

async function handleSaleSubmit(e) {
    e.preventDefault();
    const sizeId = document.getElementById('sale_size_id').value;
    const amount = document.getElementById('sale_qty').value;
    const soldPx = document.getElementById('sale_sp').value;
    const discountVal = parseFloat(document.getElementById('sale_discount').value) || 0;
    
    const data = await fetchAPI('/api/stock/adjust', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ size_id: sizeId, amount: parseInt(amount), operation: 'subtract', sold_price: soldPx, discount_applied: discountVal })
    });
    
    if (data && data.success) {
        playSuccessSequence('sellResultContainer', 'Sale Registered Successfully!', async () => {
            document.getElementById('sellSearchInput').value = '';
            await fetchProducts(); 
        });
    }
}

/* ==================================
   UPDATE_STOCK.HTML
================================== */
let batchPayload = [];
let currentUpdateProductId = null; // To track product ID for new sizes

async function searchUpdateProduct() {
    if(productsCache.length === 0) await fetchProducts();
    const q = document.getElementById('updateSearchInput').value.trim().toLowerCase();
    if(!q) return;

    const prod = productsCache.find(p => p.article_no.toLowerCase() === q);
    const container = document.getElementById('updateResultContainer');
    
    if(!prod) {
        showToast("Article Not Found!");
        container.style.display = 'none';
        return; 
    }
    
    currentUpdateProductId = prod.id;
    document.getElementById('updateResName').textContent = prod.name;
    document.getElementById('updateResCP').textContent = toMoney(prod.mrp);
    document.getElementById('updateResSold').textContent = toMoney(prod.selling_price || (prod.mrp - (prod.mrp * prod.default_discount / 100)));
    document.getElementById('updateResImg').src = prod.image_path ? `/static/${prod.image_path}` : 'https://via.placeholder.com/300x200?text=No+Image';
    
    const sizesContainer = document.getElementById('updateResSizes');
    sizesContainer.innerHTML = '';
    prod.sizes.forEach(s => {
        const row = document.createElement('div');
        row.style.display = 'flex'; row.style.justifyContent = 'space-between'; row.style.alignItems = 'center';
        row.style.background = '#ffffff'; row.style.padding = '0.75rem 1rem'; row.style.borderRadius = '8px'; row.style.border = '1px solid #e2e8f0';
        
        row.innerHTML = `
            <div><strong style="margin-right:1rem; color:#1e293b; font-size:1.1rem">UK ${s.size}</strong> <span style="color:#334155; font-size:0.95rem; font-weight:700">Current: ${s.stock}</span></div>
            <input type="number" class="batch-update-val" data-sizeid="${s.id}" data-sizename="${s.size}" placeholder="+Qty" min="1" style="width:80px; padding:0.5rem; border:1px solid #cbd5e1; border-radius:6px; outline:none; font-family:'Inter'; transition:all 0.3s; background:#f8fafc" oninput="if(this.value>0) { this.style.backgroundColor='#ecfdf5'; this.style.borderColor='#10b981'; this.style.color='#047857'; } else { this.style.backgroundColor='#f8fafc'; this.style.borderColor='#cbd5e1'; this.style.color='inherit'; }; validateBatchBtn()">
        `;
        sizesContainer.appendChild(row);
    });
    
    container.style.display = 'block';
    container.classList.remove('animate-fade-up');
    void container.offsetWidth;
    container.classList.add('animate-fade-up');
    
    validateBatchBtn();
}

function addNewUpdateSizeRow() {
    const container = document.getElementById('updateResSizes');
    const row = document.createElement('div');
    row.style.display = 'flex'; row.style.justifyContent = 'space-between'; row.style.alignItems = 'center';
    row.style.background = '#eff6ff'; row.style.padding = '0.75rem 1rem'; row.style.borderRadius = '8px'; row.style.border = '1px solid #3b82f6';
    
    row.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.5rem;">
            <strong style="color:#1d4ed8; font-size:1.1rem">UK</strong> 
            <input type="number" class="new-size-val" placeholder="Size" step="0.5" style="width:65px; padding:0.5rem; border:1px solid #3b82f6; border-radius:6px; font-weight:700">
            <span style="color:#1d4ed8; font-weight:700; margin-left:1rem;">Add Stock:</span>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem;">
            <input type="number" class="batch-update-val is-new-size" placeholder="+Qty" min="1" style="width:80px; padding:0.5rem; border:1px solid #3b82f6; border-radius:6px; font-weight:700" oninput="if(this.value>0) { this.style.backgroundColor='#ecfdf5'; } else { this.style.backgroundColor='white'; }; validateBatchBtn()">
            <button type="button" class="btn danger" style="padding:0.4rem 0.6rem; font-size:0.8rem;" onclick="this.parentElement.parentElement.remove(); validateBatchBtn()">X</button>
        </div>
    `;
    container.appendChild(row);
}

function validateBatchBtn() {
    const inputs = document.querySelectorAll('.batch-update-val');
    let valid = false;
    inputs.forEach(i => {
        if(parseInt(i.value) > 0) {
            if(i.classList.contains('is-new-size')) {
                const sizeInput = i.parentElement.parentElement.querySelector('.new-size-val');
                if(sizeInput && sizeInput.value.trim() !== '') valid = true;
            } else {
                valid = true;
            }
        }
    });
    document.getElementById('btnPreviewBatch').disabled = !valid;
}

function previewBatchUpdate() {
    batchPayload = [];
    let summaryHTML = '';
    const inputs = document.querySelectorAll('.batch-update-val');
    inputs.forEach(i => {
        const val = parseInt(i.value);
        if(val > 0) {
            if(i.classList.contains('is-new-size')) {
                const sizeInput = i.parentElement.parentElement.querySelector('.new-size-val');
                if(!sizeInput || sizeInput.value.trim() === '') return;
                const sizeVal = sizeInput.value.trim();
                batchPayload.push({is_new: true, product_id: currentUpdateProductId, size: sizeVal, amount: val});
                summaryHTML += `<div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;"><span><span class="badge" style="background:#dbeafe; color:#2563eb; margin-right:0.5rem; font-size:0.7rem; padding:0.15rem 0.4rem;">NEW</span>Size UK ${sizeVal}</span> <strong class="text-success">+${val} Pairs</strong></div>`;
            } else {
                batchPayload.push({size_id: i.dataset.sizeid, amount: val});
                summaryHTML += `<div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;"><span>Size UK ${i.dataset.sizename}</span> <strong class="text-success">+${val} Pairs</strong></div>`;
            }
        }
    });
    if(batchPayload.length === 0) return;
    
    document.getElementById('batchSummaryList').innerHTML = summaryHTML;
    document.getElementById('batchConfirmModal').style.display = 'flex';
}

async function executeBatchUpdate() {
    const data = await fetchAPI('/api/stock/adjust_batch', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: batchPayload })
    });
    if (data && data.success) {
        document.getElementById('batchConfirmModal').style.display = 'none';
        playSuccessSequence('updateResultContainer', 'Stock Augmented Safely!', async () => {
            document.getElementById('updateSearchInput').value = '';
            await fetchProducts(); 
        });
    }
}

/* ==================================
   ADD_PRODUCT.HTML
================================== */
async function loadCategoryDropdown() {
    try {
        const res = await fetch('/api/inventory');
        const data = await res.json();
        if(data.error) return;
        const select = document.getElementById('categorySelect');
        if(!select) return;
        
        select.innerHTML = '<option value="">Select Category</option>';
        
        data.categories.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id; opt.textContent = c.name;
            select.appendChild(opt);
        });
    } catch(err){}
}

async function handleCategorySubmit(e) {
    e.preventDefault();
    const name = document.getElementById('catName').value;
    const data = await fetchAPI('/api/categories', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });
    if(data && data.id) { 
        showToast("Category Added"); 
        document.getElementById('categoryForm').reset(); 
        loadCategoryDropdown(); 
    }
}

async function handleProductSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const sizes = [];
    document.querySelectorAll('#sizesContainer > div').forEach(row => {
        sizes.push({
            size: row.querySelector('.size-val').value,
            stock: row.querySelector('.stock-val').value || 0
        });
    });
    formData.append('sizes_json', JSON.stringify(sizes));

    const data = await fetchAPI('/api/products', { method: 'POST', body: formData });
    if(data && data.success) { 
        showToast("Product Created Successfully!"); 
        setTimeout(()=> { window.location.href='/overview'; }, 1000); 
    }
}

/* ==================================
   ANALYTICS.HTML
================================== */
function animateValue(obj, start, end, duration, formatMoney = false) {
    if(!obj) return;
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const val = progress * (end - start) + start;
        obj.innerHTML = formatMoney ? '₹' + Math.floor(val).toLocaleString() : Math.floor(val).toLocaleString();
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            obj.innerHTML = formatMoney ? '₹' + Number(end).toLocaleString() : Number(end).toLocaleString();
        }
    };
    window.requestAnimationFrame(step);
}

async function loadAdvancedAnalytics() {
    const data = await fetchAPI('/api/sales_advanced');
    if (!data) return;
        if(data.error) return;

        // 1. Daily
        animateValue(document.getElementById('dSold'), 0, data.daily.pairs, 1000);
        if (document.getElementById('dUnique')) {
            animateValue(document.getElementById('dUnique'), 0, data.daily.unique_pairs, 1000);
        }
        animateValue(document.getElementById('dRev'), 0, data.daily.revenue, 1000, true);
        animateValue(document.getElementById('dProf'), 0, data.daily.profit, 1000, true);
        if (document.getElementById('dSurplus')) {
            animateValue(document.getElementById('dSurplus'), 0, data.daily.surplus_loss, 1000, true);
        }

        // 2. Weekly
        animateValue(document.getElementById('wSold'), 0, data.weekly.pairs, 1000);
        animateValue(document.getElementById('wProf'), 0, data.weekly.profit, 1000, true);

        // Calculate Overall for Hero & Profit Matrix
        let tRev = 0, tProf = 0, tLoss = 0, tPairs = 0;
        data.articles.forEach(r => {
            tPairs += r.qty;
            tRev += r.revenue;
            if(r.profit > 0) tProf += r.profit;
            if(r.profit < 0) tLoss += Math.abs(r.profit);
        });

        // Hero (The "Accurate SaaS Equations")
        animateValue(document.getElementById('ovSales'), 0, data.weekly.pairs, 1500);
        animateValue(document.getElementById('ovRevenue'), 0, data.weekly.revenue, 1500, true);
        animateValue(document.getElementById('ovStock'), 0, data.stock.total_stock, 1500);

        // Comparison Intelligence Logic
        const compRevEl = document.getElementById('compareRevenue');
        if (compRevEl && data.weekly.last_week_revenue !== undefined) {
            const current = data.weekly.revenue;
            const last = data.weekly.last_week_revenue;
            const diff = current - last;
            const icon = document.getElementById('compareIcon');
            const text = document.getElementById('compareText');
            
            if (last === 0) {
                compRevEl.className = 'badge-compare flat';
                icon.innerHTML = '●';
                text.innerHTML = `New Week Started`;
            } else if (diff >= 0) {
                compRevEl.className = 'badge-compare up';
                icon.innerHTML = '↑';
                text.innerHTML = `+₹${toMoney(diff)} vs Last Week`;
            } else {
                compRevEl.className = 'badge-compare down';
                icon.innerHTML = '↓';
                text.innerHTML = `-₹${toMoney(Math.abs(diff))} vs Last Week`;
            }
        }

        // Matrix
        animateValue(document.getElementById('plProf'), 0, tProf, 1200, true);
        animateValue(document.getElementById('plLoss'), 0, tLoss, 1200, true);

        // Stock Status
        animateValue(document.getElementById('sCurr'), 0, data.stock.total_stock, 1000);
        animateValue(document.getElementById('sAlert'), 0, data.low_stock_list.length, 1000);

        // Progress Bars Render
        let stockHTML = '';
        data.all_stock_list.forEach(item => {
            const width = Math.min((item.stock / 20) * 100, 100); 
            const color = item.stock < 5 ? '#ef4444' : (item.stock < 10 ? '#f59e0b' : '#22c55e');
            stockHTML += `
                <div style="margin-bottom:0.5rem;">
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; font-weight:600; color:#1e293b;">
                        <span>${item.article} - ${item.name}</span>
                        <span style="color:${color}">${item.stock} left</span>
                    </div>
                    <div class="progress-container">
                        <div class="progress-bar" style="width:0%; background:${color}" data-target="${width}%"></div>
                    </div>
                </div>`;
        });
        document.getElementById('stockBarsList').innerHTML = stockHTML;
        // Trigger CSS transform for bars
        setTimeout(() => {
            document.querySelectorAll('.progress-bar').forEach(b => b.style.width = b.getAttribute('data-target'));
        }, 100);

        // Sorting for Top/Low Performers
        let sortedArticles = [...data.articles].sort((a,b) => b.qty - a.qty);
        let top5 = sortedArticles.slice(0, 5);
        let bot5 = sortedArticles.slice(-5).reverse();

        function renderList(targetId, arr) {
            let html = '';
            arr.forEach((r, idx) => {
                let badgeClass = (idx===0) ? 'rank-1' : ((idx===1) ? 'rank-2' : ((idx===2)?'rank-3':'rank-other'));
                html += `
                <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.4); padding:0.75rem; border-radius:8px;">
                    <div style="display:flex; align-items:center;">
                        <span class="rank-badge ${badgeClass}">${idx+1}</span>
                        <div style="display:flex; flex-direction:column;">
                            <strong style="color:#78350f; font-size:0.9rem;">${r.article_no}</strong>
                            <span class="${r.profit >= 0 ? 'text-profit' : 'text-loss'}" style="font-size:0.75rem; font-weight:700;">
                                ${r.profit >= 0 ? '+' : ''}${toMoney(r.profit)}
                            </span>
                        </div>
                    </div>
                    <strong style="color:#92400e; font-size:1rem;">${r.qty} pairs</strong>
                </div>`;
            });
            document.getElementById(targetId).innerHTML = html || '<span style="color:#78350f; font-size:0.8rem;">No data available.</span>';
        }
        
        renderList('topSellersList', top5);
        renderList('lowPerformersList', bot5);

        // Chart.js Configuration
        if(window.salesChartInstance) window.salesChartInstance.destroy();
        const ctx = document.getElementById('weeklyChart').getContext('2d');
        window.salesChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.chart.labels,
                datasets: [{
                    label: 'Pairs Sold',
                    data: data.chart.data,
                    borderColor: '#7c3aed',
                    backgroundColor: 'rgba(124, 58, 237, 0.1)',
                    borderWidth: 3,
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#7c3aed',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)', drawBorder:false }, ticks:{ color:'#6b7280', font:{family:'Inter'} } },
                    x: { grid: { display: false, drawBorder:false }, ticks:{ color:'#6b7280', font:{family:'Inter'} } }
                },
                animation: { duration: 1500, easing: 'easeOutQuart' }
            }
        });

    } 

/* ==================================
   IMAGE LIGHTBOX LOGIC
================================== */
function openLightbox(src) {
    const lb = document.getElementById('imageLightbox');
    const content = document.getElementById('lightboxContent');
    if (!lb || !content) return;
    
    content.src = src;
    lb.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // Lock scroll
}

function closeLightbox() {
    const lb = document.getElementById('imageLightbox');
    if (!lb) return;
    
    lb.style.display = 'none';
    document.body.style.overflow = ''; // Unlock scroll
}


/* ==================================
   IMAGE OPTIMIZATION ENGINE
======================== */
const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const img = entry.target;
            const src = img.getAttribute('data-src');
            if (src) {
                img.src = src;
                img.removeAttribute('data-src');
                img.onload = () => img.classList.add('img-loaded');
            }
            observer.unobserve(img);
        }
    });
}, { rootMargin: '100px 0px', threshold: 0.01 });

function optimizeImage(img) {
    if (!img) return;
    img.onload = () => img.classList.add('img-loaded');
    // If image is already complete (cached)
    if (img.complete) img.classList.add('img-loaded');
}

// Re-initialize optimized loading on static pages
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('img[loading="lazy"]').forEach(img => {
        optimizeImage(img);
    });
});

/* ==================================
   MOBILE PWA & UI LOGIC
======================== */
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js').then(reg => {
            console.log('SW Registered');
        }).catch(err => console.log('SW Reg Failed:', err));
    });
}

function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    if (menu) menu.classList.toggle('active');
}
