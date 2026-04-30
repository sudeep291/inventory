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

// Function for visual success feedback sequence (Enterprise Auto-Refresh Layer)
function playSuccessSequence(containerId, message, callback) {
    // 📳 HAPTIC FEEDBACK: Premium vibration confirming native action
    if (navigator.vibrate) navigator.vibrate([80, 40, 80]);

    const container = document.getElementById(containerId);
    if (!container) return;
    
    // Auto-Refresh Logic: Let the callback finish fetching logic, then immediately sync the UI
    const executeAutoRefresh = async () => {
        container.innerHTML = `
            <div class="success-trigger">
                <div class="check-icon">✓</div>
                <h2 style="color:#166534; font-weight:700">${message}</h2>
            </div>
        `;
        
        if (callback) await callback();
        
        setTimeout(() => {
            window.location.reload(); // ⚡ Speedy Global Database Sync
        }, 1500); 
    };
    executeAutoRefresh();
}

// Enterprise Global Fetch Wrapper (Zero-Silence Infrastructure)
async function fetchAPI(url, options = {}) {
    // 🛡️ SECURITY: Auto-inject CSRF token for state-changing requests
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (csrfToken && options.method && options.method !== 'GET') {
        if (!options.headers) options.headers = {};
        // If body is FormData, don't set Content-Type (browser handles it)
        if (!(options.body instanceof FormData)) {
            if (!options.headers['Content-Type']) options.headers['Content-Type'] = 'application/json';
        }
        options.headers['X-CSRF-Token'] = csrfToken;
    }

    try {
        const response = await fetch(url, options);
        // Handle no-content responses (204 or empty)
        const contentType = response.headers.get("content-type");
        let data = {};
        if (contentType && contentType.indexOf("application/json") !== -1) {
            data = await response.json();
        }
        
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
    // Cache-buster ensures images and stock are always fresh (fixes stale image after restart)
    const data = await fetchAPI('/api/inventory?_t=' + Date.now());
    if (data) productsCache = data.products;
}

async function loadReturnStats() {
    const data = await fetchAPI('/api/returns/stats');
    if (data && data.success) {
        const counter = document.getElementById('totalReturnCount');
        if (counter) counter.textContent = data.total;
    }
}

/* ==================================
   INDEX.HTML / DASHBOARD
================================== */
async function loadWelcomeDashboard() {
    const renderDashboardData = async () => {
        // Fetch KPI stats
        const data = await fetchAPI('/api/stats');
        if (data) {
            document.getElementById('dashCards').innerHTML = `
                <a href="/overview" class="summary-card" style="text-decoration:none"><h4>Total Products</h4><span class="val">${data.total_products}</span></a>
                <a href="/overview" class="summary-card" style="text-decoration:none"><h4>Total Global Stock</h4><span class="val">${data.total_stock}</span></a>
                <a href="/analytics" class="summary-card" style="text-decoration:none"><h4>Low Stock Alerts</h4><span class="val text-loss">${data.low_stock_alerts}</span></a>
                <a href="/analytics" class="summary-card" style="text-decoration:none"><h4>Best Seller</h4><span class="val text-profit" style="font-size:1.2rem">${data.best_seller}</span></a>
            `;
        }

        // Fetch Low Stock Table
        const salesData = await fetchAPI('/api/sales_advanced');
        if (salesData) {
            let lsHTML = '';
            salesData.low_stock_list.forEach(item => {
                lsHTML += `<tr>
                    <td><strong>${item.article}</strong></td>
                    <td>${item.name}</td>
                    <td><span class="uk-label-mix" style="font-size:1.1rem;">UK</span> <span class="size-mix" style="font-size:1.2rem;">${item.size}</span></td>                    <td class="text-loss" style="font-weight:900; font-size:1.1rem;">${item.stock} left</td>
                </tr>`;
            });
            document.getElementById('lowStockAlerts').innerHTML = lsHTML || '<tr><td colspan="4" class="text-profit">All stock is healthy!</td></tr>';
        }
    };

    // Initial render
    await renderDashboardData();

    // ⚡ Enterprise Live Sync (Background Polling)
    // Synchronizes the dashboard data silently every 30 seconds (Enterprise highly-available standard)
    if (!window.dashSyncActive) {
        window.dashSyncActive = true;
        setInterval(renderDashboardData, 30000); 
    }
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
            sizeHTML += `<span style="background:#f1f5f9; padding:0.4rem 0.7rem; border-radius:6px; font-size:1rem; font-weight:600; color:#1e293b; margin-bottom:0.25rem;"><span class="uk-label-mix">UK</span> <span class="size-mix" style="font-size:1.1rem;">${s.size}</span> : <span class="${s.stock<3?'text-loss':'value-mix'}" style="${s.stock>=3?'font-size:1.1rem':''}">${s.stock}</span></span>`;
        });
        
        const card = document.createElement('div');
        card.className = 'product-card';
        
        let imageSectionHTML = '';
        if (p.image_path) {
            const imgSrc = p.image_path.startsWith('data:') ? p.image_path : '/static/' + p.image_path;
            imageSectionHTML = `
            <div style="position:relative; cursor:pointer; height:200px; overflow:hidden; border-bottom:1px solid var(--border);"
                 onmouseenter="this.querySelector('.cam-overlay').style.opacity='1'; this.querySelector('.del-img-btn').style.opacity='1'"
                 onmouseleave="this.querySelector('.cam-overlay').style.opacity='0'; this.querySelector('.del-img-btn').style.opacity='0'"
                 onclick="triggerImageUpload('${p.id}')">
                <img class="prod-img lazy-img"
                     data-src="${imgSrc}"
                     alt="${p.name}"
                     style="width:100%; height:100%; object-fit:cover; transition:transform 0.4s ease;"
                     onmouseenter="this.style.transform='scale(1.05)'"
                     onmouseleave="this.style.transform='scale(1)'">
                <div class="cam-overlay" style="position:absolute; inset:0; background:rgba(15,23,42,0.65); color:white;
                     display:flex; flex-direction:column; align-items:center; justify-content:center;
                     opacity:0; transition:opacity 0.3s; pointer-events:none;">
                    <span style="font-size:2rem; margin-bottom:0.4rem;">📸</span>
                    <span style="font-size:0.8rem; font-weight:700; letter-spacing:0.5px; text-transform:uppercase;">Update Photo</span>
                </div>
                <button class="del-img-btn" title="Remove Image"
                    style="position:absolute; top:0.5rem; right:0.5rem; background:#dc2626; color:white;
                           border:none; border-radius:50%; width:30px; height:30px; display:flex; align-items:center;
                           justify-content:center; cursor:pointer; opacity:0; transition:opacity 0.3s; z-index:10;
                           box-shadow:0 2px 8px rgba(0,0,0,0.4); font-size:1rem; line-height:1;"
                    onclick="event.stopPropagation(); removeProductImage('${p.id}')">✕</button>
            </div>`;
        } else {
            imageSectionHTML = `
            <div style="position:relative; height:200px;
                 background:linear-gradient(135deg, #fdf8f0, #faf0e0);
                 border-bottom:1px solid #e8d5b7; display:flex; flex-direction:column; align-items:center;
                 justify-content:center; gap:0.6rem;">
                <span style="font-size:2rem;">🖼️</span>
                <div style="text-align:center; margin-bottom:0.25rem;">
                    <div style="font-size:0.82rem; font-weight:700; color:#92400e;">Add Product Photo</div>
                </div>
                <div style="display:flex; gap:0.6rem;">
                    <button onclick="triggerCameraCapture('${p.id}')" title="Open Camera"
                        style="background:#1e293b; color:white; border:none; border-radius:10px;
                               padding:0.5rem 0.9rem; font-size:0.78rem; font-weight:700;
                               cursor:pointer; display:flex; align-items:center; gap:0.35rem;
                               box-shadow:0 2px 8px rgba(0,0,0,0.2);">
                        📸 Camera
                    </button>
                    <button onclick="triggerImageUpload('${p.id}')" title="Open Gallery"
                        style="background:#92400e; color:#fff8ed; border:none; border-radius:10px;
                               padding:0.5rem 0.9rem; font-size:0.78rem; font-weight:700;
                               cursor:pointer; display:flex; align-items:center; gap:0.35rem;
                               box-shadow:0 2px 8px rgba(146,64,14,0.25);">
                        🖼️ Gallery
                    </button>
                </div>
            </div>`;
        }
        
        card.innerHTML = `
            ${imageSectionHTML}
            <div class="prod-info">
                <div class="prod-header">
                    <h3 style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" class="value-mix" title="${p.name}">${p.name}</h3>
                    <span class="badge" style="margin-left:0.5rem">${p.category_name}</span>
                </div>
                <div class="prod-meta"><strong>Art:</strong> <span class="val">${p.article_no}</span></div>
                <div class="prod-meta"><strong>MRP:</strong> <span class="val val-mrp">Rs. ${toMoney(p.mrp)}</span></div>
                <div class="prod-meta"><strong>Base Strategy:</strong> <span class="val val-strategy">${p.default_discount}% Off</span></div>
                <div class="prod-meta" style="margin-bottom:1rem; padding-bottom:0.75rem; border-bottom:1px dashed var(--border);"><strong>Target Sold:</strong> <span class="val val-sold">Rs. ${toMoney(p.selling_price)}</span></div>
                
                <div class="prod-meta"><strong>Total Stock:</strong> <span class="val total-stock-luminous">${p.total_stock}</span></div>
                
                <div style="display:flex; flex-wrap:wrap; gap:0.25rem; border-top:1px solid var(--border); padding-top:1rem; margin-bottom:1rem;">
                    ${sizeHTML || '<span style="color:var(--text-secondary); font-size:0.85rem">No active sizes</span>'}
                </div>
                
                <button class="btn danger outline full-width" style="padding:0.5rem; font-size:0.75rem; background:transparent; color:var(--loss); border:1px solid rgba(239,68,68,0.2); transition:0.2s;" onmouseover="this.style.background='var(--loss)'; this.style.color='white'" onmouseout="this.style.background='transparent'; this.style.color='var(--loss)'" onclick="removeProduct('${p.id}', '${p.name}')">
                    Delete Product
                </button>
            </div>
        `;
        grid.appendChild(card);
        
        const lazyImg = card.querySelector('.lazy-img');
        if (lazyImg) imageObserver.observe(lazyImg);
    });
}

function triggerCameraCapture(productId) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.capture = 'environment'; // Forces rear camera directly
    input.style.cssText = 'position:fixed; top:-9999px; opacity:0; pointer-events:none;';
    document.body.appendChild(input);

    input.onchange = async (e) => {
        const file = e.target.files[0];
        document.body.removeChild(input);
        if (!file) return;
        showToast('⏳ Uploading photo...');
        const formData = new FormData();
        formData.append('image', file);
        const data = await fetchAPI(`/api/products/${productId}/image`, { method: 'POST', body: formData });
        if (data && data.success) {
            showToast('✅ Photo saved!');
            await loadOverviewTable();
        } else {
            showToast('❌ Upload failed. Try again.');
        }
    };
    input.addEventListener('cancel', () => {
        if (document.body.contains(input)) document.body.removeChild(input);
    });
    input.click();
}

function triggerImageUpload(productId) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    // No capture attribute — allows both camera AND gallery on mobile
    input.style.cssText = 'position:fixed; top:-9999px; opacity:0; pointer-events:none;';

    // Must be in the DOM for browsers to allow the click
    document.body.appendChild(input);

    input.onchange = async (e) => {
        const file = e.target.files[0];
        document.body.removeChild(input); // Clean up immediately
        if (!file) return;

        showToast('⏳ Uploading image...');

        const formData = new FormData();
        formData.append('image', file);
        const data = await fetchAPI(`/api/products/${productId}/image`, { method: 'POST', body: formData });
        if (data && data.success) {
            showToast('✅ Image updated!');
            await loadOverviewTable();
        } else {
            showToast('❌ Upload failed. Try again.');
        }
    };

    // Clean up if user cancels without selecting
    input.addEventListener('cancel', () => {
        if (document.body.contains(input)) document.body.removeChild(input);
    });

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

async function removeProduct(productId, productName) {
    if(!confirm(`⚠️ CRITICAL: Are you sure you want to delete ${productName}?\n\nThis will remove it from the active inventory.`)) return;
    const data = await fetchAPI('/api/products/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId })
    });
    if(data && data.success) {
        showToast("Product deleted successfully");
        await loadOverviewTable();
        // Also refresh dashboard stats if visible
        if(document.getElementById('dashCards')) loadWelcomeDashboard();
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

    const prod = productsCache.find(p => 
        p.article_no.toLowerCase() === q || 
        (p.barcode && p.barcode.toLowerCase() === q)
    );
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
    
    const sellImg = document.getElementById('sellResImg');
    if (sellImg) {
        const imgSrc = prod.image_path
            ? (prod.image_path.startsWith('data:') ? prod.image_path : `/static/${prod.image_path}`)
            : null;
        sellImg.dataset.rawSrc = imgSrc || '';
        if (imgSrc) {
            sellImg.src = imgSrc;
            sellImg.style.display = 'block';
            sellImg.onerror = () => { sellImg.removeAttribute('src'); sellImg.style.display = 'none'; };
        } else {
            sellImg.removeAttribute('src');
            sellImg.style.display = 'none';
        }
    }

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
        span.innerHTML = `<span class="uk-label-mix" style="font-size:1.1rem;">UK</span> <span class="size-mix" style="font-size:1.25rem;">${s.size}</span> <span class="value-mix" style="font-size:1rem; margin-left:0.4rem;">(${s.stock} left)</span>`;
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

    const prod = productsCache.find(p => 
        p.article_no.toLowerCase() === q || 
        (p.barcode && p.barcode.toLowerCase() === q)
    );
    const container = document.getElementById('updateResultContainer');
    
    if(!prod) {
        showToast("Article Not Found!");
        container.style.display = 'none';
        return; 
    }
    
    currentUpdateProductId = prod.id;
    const resName = document.getElementById('updateResName');
    resName.textContent = prod.name;
    resName.style.color = '#dc2626'; // Brand Focus: Luminous Red
    resName.style.fontSize = '2.5rem';
    resName.style.fontWeight = '900';
    // Populate Dynamic MRP field (Luminous Input)
    const mrpInput = document.getElementById('updateResCP');
    mrpInput.value = prod.mrp;
    mrpInput.dataset.originalMrp = prod.mrp;
    mrpInput.dataset.discount = prod.default_discount || 0;
    
    document.getElementById('updateResSold').textContent = toMoney(prod.selling_price || (prod.mrp - (prod.mrp * prod.default_discount / 100)));
    
    const updateImg = document.getElementById('updateResImg');
    if (updateImg) {
        const imgSrc = prod.image_path
            ? (prod.image_path.startsWith('data:') ? prod.image_path : `/static/${prod.image_path}`)
            : null;
        updateImg.dataset.rawSrc = imgSrc || '';
        if (imgSrc) {
            updateImg.src = imgSrc;
            updateImg.style.display = 'block';
            updateImg.onerror = () => { updateImg.removeAttribute('src'); updateImg.style.display = 'none'; };
        } else {
            updateImg.removeAttribute('src');
            updateImg.style.display = 'none';
        }
    }
    
    const sizesContainer = document.getElementById('updateResSizes');
    sizesContainer.innerHTML = '';
    prod.sizes.forEach(s => {
        const row = document.createElement('div');
        row.className = 'update-row';
        row.style.display = 'flex'; row.style.justifyContent = 'space-between'; row.style.alignItems = 'center';
        row.style.flexWrap = 'wrap'; row.style.gap = '0.75rem';
        row.style.background = '#ffffff'; row.style.padding = '0.75rem 1rem'; row.style.borderRadius = '8px'; row.style.border = '1px solid #e2e8f0';
        
        row.innerHTML = `
            <div style="display:flex; align-items:center; gap:1rem;">
                <label class="size-return-badge" data-sizeid="${s.id}" title="Click to mark as Return">
                    <input type="checkbox" class="is-return-check" onchange="this.parentElement.classList.toggle('active'); handleRowReturnUI(this.closest('.update-row').querySelector('.batch-update-val')); validateBatchBtn()">
                    <span class="size-badge-num">R | <span class="uk-label-mix" style="font-size:1rem;">UK</span>: <span class="size-mix" style="font-size:1.15rem;">${s.size}</span></span>
                </label>
                <div style="display:flex; flex-direction:column; gap:0.1rem;">
                    <span style="color:#1e293b; font-size:0.95rem; font-weight:700;">Stock: ${s.stock}</span>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem;">
                <input type="number" class="batch-update-price" placeholder="Refund Rs. " step="0.01" style="width:100px; padding:0.5rem; border:1px solid #cbd5e1; border-radius:6px; font-size:0.85rem; display:none;">
                <input type="number" class="batch-update-val" data-sizeid="${s.id}" data-sizename="${s.size}" data-targetsp="${prod.selling_price || (prod.mrp - (prod.mrp * prod.default_discount / 100))}" placeholder="+Qty" min="1" style="width:80px; padding:0.5rem; border:1px solid #cbd5e1; border-radius:6px; outline:none; font-family:'Inter'; transition:all 0.3s; background:#f8fafc" oninput="if(this.value>0) { this.style.backgroundColor='#ecfdf5'; this.style.borderColor='#10b981'; this.style.color='#047857'; } else { this.style.backgroundColor='#f8fafc'; this.style.borderColor='#cbd5e1'; this.style.color='inherit'; }; handleRowReturnUI(this); validateBatchBtn()">
            </div>
        `;
        sizesContainer.appendChild(row);
    });
    
    container.style.display = 'block';
    container.classList.remove('animate-fade-up');
    void container.offsetWidth;
    container.classList.add('animate-fade-up');
    
    validateBatchBtn();
}

function handleRowReturnUI(input) {
    if(!input) return;
    const row = input.closest('.update-row');
    if(!row) return;
    const priceInput = row.querySelector('.batch-update-price');
    const returnCheck = row.querySelector('.is-return-check');
    if (priceInput && returnCheck) {
        if (input.value > 0 && returnCheck.checked) {
            priceInput.style.display = 'block';
            if (!priceInput.value) priceInput.value = parseFloat(input.dataset.targetsp).toFixed(2);
        } else {
            priceInput.style.display = 'none';
        }
    }
}

function addNewUpdateSizeRow() {
    const container = document.getElementById('updateResSizes');
    const row = document.createElement('div');
    row.className = 'update-row animate-fade-in';
    row.style.display = 'flex'; row.style.justifyContent = 'space-between'; row.style.alignItems = 'center';
    row.style.flexWrap = 'wrap'; row.style.gap = '0.75rem';
    row.style.background = '#eff6ff'; row.style.padding = '0.75rem 1rem'; row.style.borderRadius = '8px'; row.style.border = '1px solid #3b82f6';
    
    row.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.5rem;">
            <strong class="uk-label-mix" style="font-size:1.1rem">UK</strong> 
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
            const row = i.closest('div').parentElement;
            const isReturn = row.querySelector('.is-return-check')?.checked || false;
            const refundPx = row.querySelector('.batch-update-price')?.value || 0;

            if(i.classList.contains('is-new-size')) {
                const sizeInput = row.querySelector('.new-size-val');
                if(!sizeInput || sizeInput.value.trim() === '') return;
                const sizeVal = sizeInput.value.trim();
                batchPayload.push({is_new: true, product_id: currentUpdateProductId, size: sizeVal, amount: val, is_return: isReturn, price: refundPx});
                summaryHTML += `<div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;"><span>${isReturn ? '<span class="status-badge-returned" style="margin-right:0.5rem">RETURN</span>' : ''}<span class="badge" style="background:#dbeafe; color:#2563eb; margin-right:0.5rem; font-size:0.75rem; padding:0.15rem 0.4rem;">NEW</span>Size <span class="uk-label-mix">UK</span> <span class="size-mix" style="font-size:1.15rem;">${sizeVal}</span></span> <strong class="text-success" style="font-size:1.1rem;">+${val} Pairs</strong></div>`;
            } else {
                batchPayload.push({size_id: i.dataset.sizeid, amount: val, is_return: isReturn, price: refundPx});
                summaryHTML += `<div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;"><span>${isReturn ? '<span class="status-badge-returned" style="margin-right:0.5rem">RETURN</span>' : ''}Size <span class="uk-label-mix">UK</span> <span class="size-mix" style="font-size:1.15rem;">${i.dataset.sizename}</span></span> <strong class="text-success" style="font-size:1.1rem;">+${val} Pairs</strong></div>`;
            }
        }
    });
    if(batchPayload.length === 0) return;
    
    document.getElementById('batchSummaryList').innerHTML = summaryHTML;
    document.getElementById('batchConfirmModal').style.display = 'flex';
}

async function executeBatchUpdate() {
    const newMrpVal = document.getElementById('updateResCP').value;
    const data = await fetchAPI('/api/stock/adjust_batch', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: batchPayload, new_mrp: parseFloat(newMrpVal) })
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
    const data = await fetchAPI('/api/inventory?_t=' + Date.now());
    if(data && data.categories) {
        const select = document.getElementById('categorySelect');
        if(!select) return;
        select.innerHTML = '<option value="">Select Category</option>';
        data.categories.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id; opt.textContent = c.name;
            select.appendChild(opt);
        });
    }
}

async function handleCategorySubmit(e) {
    e.preventDefault();
    const name = document.getElementById('catName').value.trim();
    if (!name) return;
    const data = await fetchAPI('/api/categories', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });
    if(data && data.id) { 
        showToast("✅ Category Added!"); 
        document.getElementById('categoryForm').reset(); 
        await loadCategoryDropdown();
        await loadCategoryList();
    }
}

async function loadCategoryList() {
    const container = document.getElementById('categoryListContainer');
    if (!container) return;
    const data = await fetchAPI('/api/categories?_t=' + Date.now());
    if (!data || !Array.isArray(data)) {
        container.innerHTML = '<div style="color:var(--text-secondary); font-size:0.9rem;">No categories found.</div>';
        return;
    }
    if (data.length === 0) {
        container.innerHTML = '<div style="color:var(--text-secondary); font-size:0.9rem; padding:0.5rem 0;">No categories yet. Add one above.</div>';
        return;
    }
    container.innerHTML = data.map(cat => `
        <div style="display:flex; align-items:center; justify-content:space-between; padding:0.75rem 1rem; margin-bottom:0.5rem;
                    background:var(--bg-white, #f8fafc); border:1px solid var(--border, #e2e8f0); border-radius:10px;
                    transition:all 0.2s ease; box-shadow:0 1px 3px rgba(0,0,0,0.04);" id="cat-row-${cat.id}">
            <div style="display:flex; align-items:center; gap:0.6rem;">
                <span style="font-size:1.1rem;">🏷️</span>
                <span style="font-weight:600; color:var(--text-primary, #1e293b); font-size:0.95rem;">${cat.name}</span>
            </div>
            <button onclick="deleteCategory('${cat.id}', '${cat.name.replace(/'/g, '\\&apos;')}')" 
                    style="background:#fee2e2; color:#dc2626; border:none; border-radius:8px; padding:0.4rem 0.75rem;
                           font-size:0.8rem; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:0.3rem;
                           transition:all 0.2s ease;"
                    onmouseover="this.style.background='#dc2626';this.style.color='white';"
                    onmouseout="this.style.background='#fee2e2';this.style.color='#dc2626';"
                    title="Delete Category">
                🗑️ Delete
            </button>
        </div>
    `).join('');
}

async function deleteCategory(categoryId, categoryName) {
    if (!confirm(`⚠️ Delete category "${categoryName}"?\n\nThis will fail if any active products are using it.`)) return;
    const data = await fetchAPI(`/api/categories/${categoryId}`, { method: 'DELETE' });
    if (data && data.success) {
        // Animate row removal
        const row = document.getElementById(`cat-row-${categoryId}`);
        if (row) {
            row.style.transition = 'all 0.3s ease';
            row.style.opacity = '0';
            row.style.transform = 'translateX(20px)';
            setTimeout(() => row.remove(), 300);
        }
        showToast(`✅ "${categoryName}" deleted!`);
        await loadCategoryDropdown();
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
    const endVal = parseFloat(end) || 0;
    const startVal = parseFloat(start) || 0;
    
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const val = progress * (endVal - startVal) + startVal;
        
        // For money: show 2 decimals. For counts: show whole numbers.
        let displayVal = formatMoney ? val.toFixed(2) : Math.floor(val).toLocaleString();
        if (formatMoney) displayVal = 'Rs. ' + parseFloat(displayVal).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        
        obj.innerHTML = displayVal;
        
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            let finalVal = formatMoney
                ? 'Rs. ' + Number(endVal).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                : Number(endVal).toLocaleString();
            obj.innerHTML = finalVal;
        }
    };
    window.requestAnimationFrame(step);
}

/* ==================================
   WHATSAPP DAILY REPORT
================================== */
function shareWhatsAppReport() {
    const btn = document.getElementById('waShareBtn');
    if (btn) {
        btn.textContent = '⏳ Preparing...';
        btn.disabled = true;
    }

    // Read live values already on the page
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-IN', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
    const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

    const get = (id) => document.getElementById(id)?.textContent?.trim() || '—';

    // Daily metrics
    const dPairs    = get('dSold');
    const dUnique   = get('dUnique');
    const dRevenue  = get('dRev');
    const dReturns  = get('dMoneyRet');
    const dVariance = get('dSurplus');

    // Weekly metrics
    const wPairs    = get('ovSales');
    const wRevenue  = get('ovRevenue');
    const wSurplus  = get('wSurplus');

    // Vault
    const vault     = get('ovStock');
    const alerts    = get('sAlert');
    const returned  = get('ovReturns');

    // Top seller (first item in the rank list)
    const topEl = document.querySelector('#topSellersList strong');
    const topSeller = topEl ? topEl.textContent.trim() : '—';

    const msg =
`🏪 *Sri Vijayalakshmi Footwear*
📅 *${dateStr}* | 🕐 ${timeStr}
━━━━━━━━━━━━━━━━━━━━

📦 *TODAY'S PERFORMANCE*
👟 Pairs Sold : *${dPairs}*
🎯 Varieties  : *${dUnique}*
💰 Revenue    : *${dRevenue}*
↩️ Returned   : *${dReturns}*
📊 Vs Target  : *${dVariance}*

━━━━━━━━━━━━━━━━━━━━
📈 *THIS WEEK (Mon–Today)*
👟 Pairs Sold : *${wPairs}*
💰 Revenue    : *${wRevenue}*
📊 Net Surplus: *${wSurplus}*

━━━━━━━━━━━━━━━━━━━━
🏬 *VAULT STATUS*
📦 Total Stock     : *${vault} pairs*
🔴 Low Stock Alerts: *${alerts}*
↩️ Total Returns   : *${returned}*
🔥 Top Seller      : *${topSeller}*

━━━━━━━━━━━━━━━━━━━━
_📲 Sent from Inventory System_`;

    // Restore button
    setTimeout(() => {
        if (btn) {
            btn.innerHTML = `<svg width="22" height="22" viewBox="0 0 32 32" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M16.002 3C9.374 3 4 8.373 4 15c0 2.385.68 4.61 1.855 6.5L4 29l7.703-1.823A12.93 12.93 0 0016.002 28C22.628 28 28 22.627 28 16S22.628 3 16.002 3zm0 2C21.524 5 26 9.477 26 16s-4.476 11-9.998 11c-1.99 0-3.849-.573-5.432-1.56l-.39-.245-4.57 1.08 1.1-4.46-.27-.41A10.96 10.96 0 016 16C6 9.477 10.479 5 16.002 5zm-3.39 5.5c-.2 0-.524.075-.8.373-.275.299-1.05 1.025-1.05 2.5s1.075 2.9 1.225 3.1c.15.2 2.1 3.2 5.1 4.375 2.998 1.175 2.998.783 3.548.733.55-.05 1.774-.724 2.024-1.424.25-.7.25-1.3.175-1.424-.075-.125-.275-.2-.575-.35-.3-.15-1.774-.875-2.05-.975-.274-.1-.474-.15-.674.15-.2.3-.774.975-.949 1.175-.175.2-.35.225-.65.075-.3-.15-1.267-.467-2.414-1.49-.893-.796-1.495-1.778-1.67-2.078-.175-.3-.019-.462.131-.612.136-.134.3-.35.45-.524.15-.175.2-.3.3-.5.1-.2.05-.375-.025-.525-.075-.15-.65-1.625-.9-2.225-.25-.6-.5-.5-.675-.5l-.575-.013z"/></svg> Share Daily Report on WhatsApp`;
            btn.disabled = false;
        }
    }, 2000);

    window.open(`https://wa.me/?text=${encodeURIComponent(msg)}`, '_blank');
}

async function loadAdvancedAnalytics() {
    const data = await fetchAPI('/api/sales_advanced');
    if (!data) return;
        if(data.error) return;

        // 1. Daily Analytics (Return-Aware Performance)
        animateValue(document.getElementById('dSold'), 0, data.daily.pairs, 1000);
        if (document.getElementById('dUnique')) {
            animateValue(document.getElementById('dUnique'), 0, data.daily.unique_pairs, 1000);
        }
        animateValue(document.getElementById('dRev'), 0, data.daily.revenue, 1000, true);
        
        const moneyTodayEl = document.getElementById('dMoneyRet');
        if (moneyTodayEl) animateValue(moneyTodayEl, 0, data.daily.money_returned, 1000, true);
        
        if (document.getElementById('dSurplus')) {
            animateValue(document.getElementById('dSurplus'), 0, data.daily.net_surplus, 1000, true);
        }

        // 2. Weekly Performance (Return-Aware Performance)
        animateValue(document.getElementById('wSold'), 0, data.weekly.pairs, 1000);
        const wSurpEl = document.getElementById('wSurplus');
        if (wSurpEl) animateValue(wSurpEl, 0, data.weekly.net_surplus, 1000, true);

        // Calculate Overall for Hero & Profit Matrix
        let tRev = 0, tProf = 0, tLoss = 0, tPairs = 0;
        data.articles.forEach(r => {
            tPairs += r.qty;
            tRev += r.revenue;
            if(r.profit > 0) tProf += r.profit;
            if(r.profit < 0) tLoss += Math.abs(r.profit);
        });

        // Hero Analytics (Synchronized with Overall Database)
        animateValue(document.getElementById('ovSales'), 0, data.weekly.pairs, 1500);
        animateValue(document.getElementById('ovRevenue'), 0, data.weekly.revenue, 1500, true);
        animateValue(document.getElementById('ovStock'), 0, (data.overall ? data.overall.vault_stock : data.stock.total_stock), 1500);
        animateValue(document.getElementById('ovReturns'), 0, data.stock.total_returned, 1500);

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
                text.innerHTML = `+Rs. ${toMoney(diff)} vs Last Week`;
            } else {
                compRevEl.className = 'badge-compare down';
                icon.innerHTML = '↓';
                text.innerHTML = `-Rs. ${toMoney(Math.abs(diff))} vs Last Week`;
            }
        }

        // Profit Matrix (Net System Performance)
        const plProfEl = document.getElementById('plProf');
        if (plProfEl) animateValue(plProfEl, 0, (data.overall ? data.overall.net_surplus : 0), 1200, true);
        
        const plRetEl = document.getElementById('plReturned');
        if (plRetEl) animateValue(plRetEl, 0, (data.overall ? data.overall.money_returned : 0), 1200, true);

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

        // Sorting for Top/Low Performers — by quantity sold
        let sortedArticles = [...data.articles].sort((a,b) => b.qty - a.qty);
        let top5 = sortedArticles.slice(0, 5);
        let bot5 = sortedArticles.filter(r => r.qty > 0).slice(-5).reverse();

        function renderList(targetId, arr) {
            let html = '';
            arr.forEach((r, idx) => {
                let badgeClass = (idx===0) ? 'rank-1' : ((idx===1) ? 'rank-2' : ((idx===2)?'rank-3':'rank-other'));
                // strategy_var: positive = sold above target, negative = sold below target
                const sv = r.strategy_var || 0;
                const svLabel = sv >= 0
                    ? `<span class="text-profit" style="font-size:0.75rem; font-weight:700;">+Rs. ${toMoney(sv)} above target</span>`
                    : `<span class="text-loss" style="font-size:0.75rem; font-weight:700;">Rs. ${toMoney(Math.abs(sv))} below target</span>`;
                html += `
                <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.4); padding:0.75rem; border-radius:8px;">
                    <div style="display:flex; align-items:center;">
                        <span class="rank-badge ${badgeClass}">${idx+1}</span>
                        <div style="display:flex; flex-direction:column;">
                            <strong style="color:#78350f; font-size:0.9rem;">${r.article_no} — ${r.name || ''}</strong>
                            ${svLabel}
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
        
        loadSizeHeatmap();

    } 

async function loadSizeHeatmap() {
    const grid = document.getElementById('sizeHeatmapGrid');
    if (!grid) return;
    
    const res = await fetchAPI('/api/analytics/heatmap');
    if (!res || !res.success || !res.data) {
        grid.innerHTML = '<span style="color:#0f766e; font-size:0.9rem;">No heatmap data available.</span>';
        return;
    }
    
    let html = '';
    res.data.forEach(item => {
        const hClass = `heat-${item.heat_level}`;
        html += `
        <div class="heatmap-box ${hClass}">
            <div class="sz"><span class="uk-label-mix" style="font-size:1.1rem;">UK</span> <span class="size-mix" style="font-size:1.25rem;">${item.size}</span></div>
            <div class="stats">${item.total_sold} Sold <br> ${item.current_stock} Left</div>
        </div>`;
    });
    
    grid.innerHTML = html || '<span style="color:#0f766e; font-size:0.9rem;">No sizes detected in database.</span>';
} 

/* ==================================
   IMAGE LIGHTBOX LOGIC
================================== */
function openProductLightbox(imgId) {
    // imgId is 'sell' or 'update' — finds the stored raw image src
    const imgEl = document.getElementById(imgId === 'sell' ? 'sellResImg' : 'updateResImg');
    if (!imgEl) return;
    const src = imgEl.dataset.rawSrc || imgEl.getAttribute('src');
    if (!src || src === '' || src === window.location.href) { showToast('No image available for this product.'); return; }
    openLightbox(src);
}

function openLightbox(src) {
    if (!src || src === '' || src === window.location.href) { showToast('No image available.'); return; }
    const lb = document.getElementById('imageLightbox');
    const content = document.getElementById('lightboxContent');
    if (!lb || !content) return;
    
    // Force image to be fully visible
    content.style.opacity = '1';
    content.style.visibility = 'visible';
    content.style.display = 'block';
    content.src = src;
    
    lb.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    // Close on Escape key
    document.onkeydown = (e) => { if (e.key === 'Escape') closeLightbox(); };
}

function closeLightbox() {
    const lb = document.getElementById('imageLightbox');
    if (!lb) return;
    
    const content = document.getElementById('lightboxContent');
    if (content) content.removeAttribute('src');
    
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
                img.addEventListener('load', () => {
                    img.classList.add('img-loaded');
                    img.style.display = 'block';
                    if (img.nextElementSibling && img.nextElementSibling.classList.contains('fallback-icon')) {
                        img.nextElementSibling.style.display = 'none';
                    }
                });
                img.addEventListener('error', () => {
                    img.classList.add('img-loaded'); // ensure opacity is 1 so display:none toggles nicely
                    img.style.display = 'none';
                    if (img.nextElementSibling && img.nextElementSibling.classList.contains('fallback-icon')) {
                        img.nextElementSibling.style.display = 'flex';
                    }
                });
                // ALWAYS set src after attaching listeners to prevent cache race conditions
                img.src = encodeURI(src);
                img.removeAttribute('data-src');
            }
            observer.unobserve(img);
        }
    });
}, { rootMargin: '100px 0px', threshold: 0.01 });

function optimizeImage(img) {
    if (!img) return;
    img.addEventListener('load', () => img.classList.add('img-loaded'));
    img.addEventListener('error', () => img.classList.add('img-loaded'));
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


/**
 * Enterprise Pricing Engine: Calculates real-time Selling Price based on MRP and Article Strategy.
 */
function resyncUpdateSold() {
    const mrpInput = document.getElementById('updateResCP');
    const soldSpan = document.getElementById('updateResSold');
    
    const mrp = parseFloat(mrpInput.value) || 0;
    const disc = parseFloat(mrpInput.dataset.discount) || 0;
    
    if (mrp > 0) {
        const newSold = mrp - (mrp * disc / 100);
        soldSpan.textContent = 'Rs. ' + newSold.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    } else {
        soldSpan.textContent = 'Rs. 0.00';
    }
}

