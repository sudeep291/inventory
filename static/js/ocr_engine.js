/**
 * OCR Engine - Enterprise Label Reader v2
 * Fixed for Tesseract.js v5 API
 * Extracts Article No, MRP, Company Name from IS 6721 Indian footwear labels.
 */

let ocrWorker = null;
let ocrReady = false;

/**
 * Pre-load Tesseract.js v5 worker on page load for faster first scan.
 */
async function initOCRWorker() {
    if (ocrWorker && ocrReady) return;
    try {
        // Tesseract.js v5 API: createWorker(lang)
        ocrWorker = await Tesseract.createWorker('eng');
        ocrReady = true;
        console.log('[OCR] Worker ready (v5).');
    } catch (e) {
        console.warn('[OCR] Pre-load failed, will retry on scan.', e);
        ocrWorker = null;
        ocrReady = false;
    }
}

/**
 * Extract label fields using regex patterns for IS 6721 Indian footwear labels.
 */
function extractLabelData(rawText) {
    const text = rawText.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
    const result = { articleNo: null, mrp: null, companyName: null, confidence: 'low' };

    // --- Article No ---
    // IS 6721 labels always have the article number as the FIRST large text
    // Patterns: WG5511, RJ2034, NK-1122, MC3456, A1234
    const articlePatterns = [
        /\b([A-Z]{2,5}-?\d{3,6})\b/,   // e.g. WG5511, RJ-2034
        /\b([A-Z]\d{3,6}[A-Z]?)\b/,    // e.g. A1234, A1234B
    ];
    for (const pat of articlePatterns) {
        const m = text.match(pat);
        if (m) { result.articleNo = m[1].toUpperCase().replace(/\s/g, ''); break; }
    }

    // --- MRP ---
    // Matches: "MRP. ₹234.00", "MRP Rs 234", "MRP234"
    const mrpMatch = text.match(/MRP[.\s]*[₹RsS]*[\s.]*(\d{2,5}(?:\.\d{1,2})?)/i);
    if (mrpMatch) result.mrp = parseFloat(mrpMatch[1]).toFixed(2);

    // --- Company Name ---
    // Matches: "MANUFACTURED BY: WALKAROO INTERNATIONAL PVT LTD"
    const companyMatch = text.match(/MANUFACTURED\s+BY[:\s]+([A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?)/i);
    if (companyMatch) result.companyName = companyMatch[1].trim();

    // --- Confidence ---
    const found = [result.articleNo, result.mrp, result.companyName].filter(Boolean).length;
    result.confidence = found >= 2 ? 'high' : found === 1 ? 'medium' : 'failed';

    return result;
}

/**
 * Run OCR on an image file using Tesseract.js v5
 */
async function runOCRScan(imageFile, onResult, onError) {
    try {
        if (typeof showToast === 'function') showToast('🔍 Reading label, please wait...');

        // Ensure worker is ready
        if (!ocrWorker || !ocrReady) {
            await initOCRWorker();
        }

        if (!ocrWorker) {
            onError('OCR engine failed to start. Please refresh and try again.');
            return;
        }

        // Tesseract.js v5: worker.recognize(image)
        const { data } = await ocrWorker.recognize(imageFile);
        const rawText = data.text || '';

        console.log('[OCR] Raw text extracted:\n', rawText);

        if (rawText.trim().length < 3) {
            onError('Image too blurry or dark. Please use a clear, well-lit photo.');
            return;
        }

        const extracted = extractLabelData(rawText);
        console.log('[OCR] Extracted data:', extracted);

        if (extracted.confidence === 'failed') {
            onError('Could not read label format. Ensure Article No and MRP are visible.');
            return;
        }

        onResult(extracted);

    } catch (e) {
        console.error('[OCR] Error:', e);
        onError('OCR scan failed. Please try again with a clearer image.');
    }
}

/**
 * Verification card — user must confirm before data is applied.
 * Enterprise data integrity: nothing is auto-applied without human approval.
 */
function showOCRConfirmCard(extracted, onConfirm) {
    const existing = document.getElementById('ocrConfirmCard');
    if (existing) existing.remove();

    const confidenceColor = extracted.confidence === 'high' ? '#10b981' : '#f59e0b';
    const confidenceLabel = extracted.confidence === 'high' ? '✅ High Confidence' : '⚠️ Medium Confidence';

    const card = document.createElement('div');
    card.id = 'ocrConfirmCard';
    card.style.cssText = `
        position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
        background:#fff; border-radius:16px; padding:1.5rem; width:90%; max-width:380px;
        box-shadow:0 20px 60px rgba(0,0,0,0.35); z-index:99999;
        border:2px solid #e2e8f0; font-family:'Inter',sans-serif; animation: fadeUp 0.2s ease;
    `;

    card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
            <h3 style="margin:0;color:#1e293b;font-size:1.1rem;">📋 Label Detected</h3>
            <span style="background:${confidenceColor}22;color:${confidenceColor};padding:0.2rem 0.7rem;border-radius:20px;font-size:0.72rem;font-weight:700;">${confidenceLabel}</span>
        </div>
        <div style="background:#f8fafc;border-radius:10px;padding:1rem;margin-bottom:1rem;border:1px solid #e2e8f0;">
            ${extracted.articleNo ? `<div style="display:flex;justify-content:space-between;padding:0.4rem 0;border-bottom:1px solid #e2e8f0;"><span style="color:#64748b;font-size:0.82rem;">Article No</span><strong style="color:#7c3aed;">${extracted.articleNo}</strong></div>` : '<div style="color:#ef4444;font-size:0.8rem;padding:0.3rem 0;">⚠️ Article No not found in image</div>'}
            ${extracted.mrp ? `<div style="display:flex;justify-content:space-between;padding:0.4rem 0;border-bottom:1px dashed #e2e8f0;"><span style="color:#64748b;font-size:0.82rem;">MRP</span><strong style="color:#10b981;">₹${extracted.mrp}</strong></div>` : ''}
            ${extracted.companyName ? `<div style="display:flex;justify-content:space-between;padding:0.4rem 0;"><span style="color:#64748b;font-size:0.82rem;">Company</span><strong style="color:#1e293b;">${extracted.companyName}</strong></div>` : ''}
        </div>
        <p style="color:#94a3b8;font-size:0.75rem;margin-bottom:1rem;">⚠️ Verify data before applying. Wrong entries affect your inventory reports.</p>
        <div style="display:flex;gap:0.75rem;">
            <button onclick="document.getElementById('ocrConfirmCard').remove();" style="flex:1;padding:0.75rem;border:1px solid #e2e8f0;border-radius:8px;background:#fff;color:#64748b;font-weight:600;cursor:pointer;font-size:0.9rem;">Cancel</button>
            <button id="ocrApplyBtn" style="flex:2;padding:0.75rem;border:none;border-radius:8px;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;font-weight:700;cursor:pointer;font-size:0.95rem;">✅ Apply to Form</button>
        </div>
    `;

    document.body.appendChild(card);
    document.getElementById('ocrApplyBtn').onclick = () => {
        card.remove();
        onConfirm(extracted);
    };
}
