/**
 * OCR Engine - Enterprise Label Reader v3
 * Fixed: Progress toasts, timeout detection, DB existence check, better error messages
 */

let ocrWorker = null;
let ocrReady = false;
let ocrInitializing = false;

/**
 * Initialize Tesseract worker (lazy — only when user first taps Read Label)
 */
async function initOCRWorker() {
    if (ocrWorker && ocrReady) return true;
    if (ocrInitializing) return false;

    ocrInitializing = true;
    if (typeof showToast === 'function') showToast('⏳ Loading OCR engine (first time only)...');

    try {
        ocrWorker = await Tesseract.createWorker('eng', 1, {
            workerPath: 'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/worker.min.js',
            langPath: 'https://tessdata.projectnaptha.com/4.0.0',
            corePath: 'https://cdn.jsdelivr.net/npm/tesseract.js-core@5/tesseract-core.wasm.js',
            logger: (m) => {
                if (m.status === 'recognizing text') {
                    // silent during recognition
                }
                if (m.status === 'loading tesseract core' || m.status === 'loading language traineddata') {
                    if (typeof showToast === 'function') showToast('⚙️ Loading AI model...');
                }
            }
        });
        ocrReady = true;
        ocrInitializing = false;
        if (typeof showToast === 'function') showToast('✅ OCR engine ready!');
        return true;
    } catch (e) {
        console.error('[OCR] Worker init failed:', e);
        ocrWorker = null;
        ocrReady = false;
        ocrInitializing = false;
        return false;
    }
}

/**
 * Extract label data using IS 6721 Indian footwear label patterns
 */
function extractLabelData(rawText) {
    const text = rawText.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
    console.log('[OCR] Raw text:\n', rawText);

    const result = { articleNo: null, mrp: null, companyName: null, confidence: 'low' };

    // Article No: e.g. WG5511, RJ2034, NB-1122
    const articlePatterns = [
        /\b([A-Z]{2,5}-?\d{3,6})\b/,
        /\b([A-Z]\d{4,6})\b/,
    ];
    for (const pat of articlePatterns) {
        const m = text.match(pat);
        if (m) { result.articleNo = m[1].toUpperCase().replace(/\s/g, ''); break; }
    }

    // MRP: e.g. "MRP. ₹234.00", "MRP 234"
    const mrpMatch = text.match(/MRP[^0-9]*(\d{2,5}(?:\.\d{1,2})?)/i);
    if (mrpMatch) result.mrp = parseFloat(mrpMatch[1]).toFixed(2);

    // Company from "MANUFACTURED BY: WALKAROO..."
    const companyMatch = text.match(/MANUFACTURED\s+BY[:\s]+([A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?)/i);
    if (companyMatch) result.companyName = companyMatch[1].trim();

    const found = [result.articleNo, result.mrp, result.companyName].filter(Boolean).length;
    result.confidence = found >= 2 ? 'high' : found === 1 ? 'medium' : 'failed';

    return result;
}

/**
 * Main OCR scan function with timeout and progress
 */
async function runOCRScan(imageFile, onResult, onError) {
    // Initialize worker if not ready
    const ready = await initOCRWorker();
    if (!ready || !ocrWorker) {
        onError('OCR engine could not start. Check your internet connection and try again.');
        return;
    }

    if (typeof showToast === 'function') showToast('🔍 Reading label text...');

    // 45-second timeout guard
    let timedOut = false;
    const timeoutId = setTimeout(() => {
        timedOut = true;
        onError('OCR timed out. Please try a clearer, well-lit photo of the label.');
    }, 45000);

    try {
        const { data } = await ocrWorker.recognize(imageFile);
        clearTimeout(timeoutId);

        if (timedOut) return;

        const rawText = data.text || '';
        if (rawText.trim().length < 3) {
            onError('Image too blurry or dark. Please use a clear photo with good lighting.');
            return;
        }

        const extracted = extractLabelData(rawText);

        if (extracted.confidence === 'failed') {
            onError('Label format not recognized. Ensure Article No and MRP are clearly visible in the photo.');
            return;
        }

        onResult(extracted);
    } catch (e) {
        clearTimeout(timeoutId);
        if (!timedOut) {
            console.error('[OCR] recognize error:', e);
            onError('OCR scan failed. Please try again with a better quality photo.');
        }
    }
}

/**
 * Check if article exists in your Firestore cache
 */
function checkArticleInDB(articleNo) {
    if (typeof productsCache === 'undefined' || !productsCache) return null;
    return productsCache.find(p =>
        p.article_no && p.article_no.toUpperCase() === articleNo.toUpperCase()
    ) || null;
}

/**
 * Verification + DB-check card shown before applying data
 */
function showOCRConfirmCard(extracted, onConfirm, mode) {
    const existing = document.getElementById('ocrConfirmCard');
    if (existing) existing.remove();

    const confidenceColor = extracted.confidence === 'high' ? '#10b981' : '#f59e0b';
    const confidenceLabel = extracted.confidence === 'high' ? '✅ High Confidence' : '⚠️ Medium Confidence';

    // DB check
    let dbStatusHTML = '';
    if (extracted.articleNo) {
        const match = checkArticleInDB(extracted.articleNo);
        if (match) {
            const sizeList = (match.sizes || []).map(s => `UK ${s.size}`).join(', ');
            dbStatusHTML = `
                <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:0.75rem;margin-bottom:0.75rem;">
                    <p style="color:#15803d;font-weight:700;font-size:0.85rem;margin:0;">✅ Found in your inventory!</p>
                    <p style="color:#166534;font-size:0.78rem;margin:0.25rem 0 0;">Sizes: ${sizeList || 'N/A'}</p>
                </div>`;
        } else {
            dbStatusHTML = `
                <div style="background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:0.75rem;margin-bottom:0.75rem;">
                    <p style="color:#92400e;font-weight:700;font-size:0.85rem;margin:0;">⚠️ New article — not in your inventory yet</p>
                    <p style="color:#78350f;font-size:0.78rem;margin:0.25rem 0 0;">You can add it using the form.</p>
                </div>`;
        }
    }

    const card = document.createElement('div');
    card.id = 'ocrConfirmCard';
    card.style.cssText = `
        position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
        background:#fff; border-radius:16px; padding:1.5rem; width:92%; max-width:380px;
        box-shadow:0 20px 60px rgba(0,0,0,0.35); z-index:99999;
        border:2px solid #e2e8f0; font-family:'Inter',sans-serif;
    `;

    card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
            <h3 style="margin:0;color:#1e293b;font-size:1.05rem;">📋 Label Data Extracted</h3>
            <span style="background:${confidenceColor}22;color:${confidenceColor};padding:0.2rem 0.6rem;border-radius:20px;font-size:0.7rem;font-weight:700;">${confidenceLabel}</span>
        </div>
        ${dbStatusHTML}
        <div style="background:#f8fafc;border-radius:10px;padding:0.75rem;margin-bottom:0.75rem;border:1px solid #e2e8f0;">
            ${extracted.articleNo ? `<div style="display:flex;justify-content:space-between;padding:0.35rem 0;border-bottom:1px solid #f1f5f9;"><span style="color:#64748b;font-size:0.8rem;">Article No</span><strong style="color:#7c3aed;">${extracted.articleNo}</strong></div>` : `<div style="color:#ef4444;font-size:0.78rem;padding:0.3rem;">⚠️ Article No not detected</div>`}
            ${extracted.mrp ? `<div style="display:flex;justify-content:space-between;padding:0.35rem 0;border-bottom:1px solid #f1f5f9;"><span style="color:#64748b;font-size:0.8rem;">MRP</span><strong style="color:#10b981;">₹${extracted.mrp}</strong></div>` : ''}
            ${extracted.companyName ? `<div style="display:flex;justify-content:space-between;padding:0.35rem 0;"><span style="color:#64748b;font-size:0.8rem;">Company</span><strong style="color:#1e293b;">${extracted.companyName}</strong></div>` : ''}
        </div>
        <p style="color:#94a3b8;font-size:0.73rem;margin-bottom:1rem;">Verify data before applying — incorrect entries affect your reports.</p>
        <div style="display:flex;gap:0.75rem;">
            <button onclick="document.getElementById('ocrConfirmCard').remove();" style="flex:1;padding:0.7rem;border:1px solid #e2e8f0;border-radius:8px;background:#fff;color:#64748b;font-weight:600;cursor:pointer;font-size:0.88rem;">Cancel</button>
            <button id="ocrApplyBtn" style="flex:2;padding:0.7rem;border:none;border-radius:8px;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;font-weight:700;cursor:pointer;font-size:0.92rem;">✅ Apply to Form</button>
        </div>
    `;

    document.body.appendChild(card);
    document.getElementById('ocrApplyBtn').onclick = () => {
        card.remove();
        onConfirm(extracted);
    };
}
