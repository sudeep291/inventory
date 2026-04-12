/**
 * OCR Engine - Enterprise Label Reader
 * Extracts Article No, Company Name, and MRP from Indian IS 6721 footwear labels.
 * Uses Tesseract.js (client-side, no API key, no external database).
 */

let ocrWorker = null;

/**
 * Pre-load Tesseract worker for faster first-scan.
 * Call this on page load.
 */
async function initOCRWorker() {
    if (ocrWorker) return; // Already loaded
    try {
        ocrWorker = await Tesseract.createWorker('eng', 1, {
            logger: () => {} // Silent logger
        });
        await ocrWorker.setParameters({
            tessedit_char_whitelist: 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789₹./:, ',
            tessedit_pageseg_mode: '6', // PSM_SINGLE_BLOCK - best for label text
        });
        console.log('[OCR] Worker pre-loaded and ready.');
    } catch (e) {
        console.warn('[OCR] Worker pre-load failed, will retry on scan.', e);
        ocrWorker = null;
    }
}

/**
 * Master regex extraction for IS 6721 Indian Footwear Labels.
 * Extracts: Article No, MRP, Company Name.
 * @param {string} rawText - Raw OCR text from Tesseract
 * @returns {object} - { articleNo, mrp, companyName, confidence }
 */
function extractLabelData(rawText) {
    const text = rawText.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
    const result = { articleNo: null, mrp: null, companyName: null, confidence: 'low' };

    // --- Article No ---
    // Matches common Indian footwear article patterns: WG5511, RJ2034, NK1122, MC-3456
    // Must be: 2-5 uppercase letters + 3-6 digits (with optional hyphen)
    const articlePatterns = [
        /\b([A-Z]{2,5}-?\d{3,6})\b/g,   // Standard: WG5511, RJ-2034
        /\b([A-Z]\d{3,6}[A-Z]?)\b/g,    // Alternate: A1234, A1234B
    ];
    for (const pattern of articlePatterns) {
        const matches = [...text.matchAll(pattern)];
        if (matches.length > 0) {
            // Take the FIRST match - article no is always at the top of IS 6721 labels
            result.articleNo = matches[0][1].toUpperCase().trim();
            break;
        }
    }

    // --- MRP ---
    // Matches: "MRP. ₹234.00", "MRP Rs 234", "MRP 234"
    const mrpMatch = text.match(/MRP[.\s]*[₹Rs.]*\s*(\d+(?:\.\d{1,2})?)/i);
    if (mrpMatch) {
        result.mrp = parseFloat(mrpMatch[1]).toFixed(2);
    }

    // --- Company Name ---
    // Matches: "MANUFACTURED BY: WALKAROO INTERNATIONAL PVT LTD"
    const companyMatch = text.match(/MANUFACTURED\s+BY[:\s]+([A-Z][A-Za-z\s,]+?(?:PVT\.?\s*LTD\.?|LIMITED|INDUSTRIES|FOOTWEAR|INT'?L?\.?)?)/i);
    if (companyMatch) {
        // Extract just the brand name (first 1-2 words before "INTERNATIONAL", "IND", etc.)
        let fullName = companyMatch[1].trim();
        const brandMatch = fullName.match(/^([A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?)/);
        result.companyName = brandMatch ? brandMatch[1].trim() : fullName.split(' ').slice(0,2).join(' ');
    }

    // --- Confidence Assessment ---
    const found = [result.articleNo, result.mrp, result.companyName].filter(Boolean).length;
    if (found === 3) result.confidence = 'high';
    else if (found === 2) result.confidence = 'medium';
    else if (found === 1) result.confidence = 'low';
    else result.confidence = 'failed';

    return result;
}

/**
 * Main OCR scan function.
 * @param {File} imageFile - The image file from the file input
 * @param {function} onResult - Callback with extracted data
 * @param {function} onError - Callback on failure
 */
async function runOCRScan(imageFile, onResult, onError) {
    try {
        showToast('🔍 Reading label...');

        // Ensure worker is ready
        if (!ocrWorker) await initOCRWorker();

        // Run Tesseract OCR
        const { data } = await ocrWorker.recognize(imageFile);
        const rawText = data.text;

        if (!rawText || rawText.trim().length < 5) {
            onError('Could not read text from image. Please use a clear, well-lit photo.');
            return;
        }

        const extracted = extractLabelData(rawText);

        if (extracted.confidence === 'failed') {
            onError('No label data found. Ensure the Article No and MRP are clearly visible.');
            return;
        }

        onResult(extracted);
    } catch (e) {
        console.error('[OCR] Scan failed:', e);
        onError('OCR scan failed. Please try again with a clearer image.');
    }
}

/**
 * Show a confirmation card before applying OCR data.
 * This ensures enterprise data integrity - user must verify before it's applied.
 */
function showOCRConfirmCard(extracted, onConfirm) {
    // Remove any existing confirmation card
    const existing = document.getElementById('ocrConfirmCard');
    if (existing) existing.remove();

    const card = document.createElement('div');
    card.id = 'ocrConfirmCard';
    card.style.cssText = `
        position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
        background:#fff; border-radius:16px; padding:1.5rem; width:90%; max-width:380px;
        box-shadow:0 20px 60px rgba(0,0,0,0.3); z-index:9999;
        border:2px solid #e2e8f0; font-family:'Inter',sans-serif;
    `;

    const confidenceColor = extracted.confidence === 'high' ? '#10b981' : extracted.confidence === 'medium' ? '#f59e0b' : '#ef4444';
    const confidenceLabel = extracted.confidence === 'high' ? '✅ High Confidence' : extracted.confidence === 'medium' ? '⚠️ Medium Confidence' : '⚠️ Low Confidence';

    card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <h3 style="margin:0; color:#1e293b; font-size:1.1rem;">📋 Label Detected</h3>
            <span style="background:${confidenceColor}22; color:${confidenceColor}; padding:0.25rem 0.75rem; border-radius:20px; font-size:0.75rem; font-weight:700;">${confidenceLabel}</span>
        </div>
        <div style="background:#f8fafc; border-radius:10px; padding:1rem; margin-bottom:1rem; border:1px solid #e2e8f0;">
            ${extracted.articleNo ? `<div style="display:flex; justify-content:space-between; padding:0.4rem 0; border-bottom:1px solid #e2e8f0;"><span style="color:#64748b; font-size:0.85rem;">Article No</span><strong style="color:#1e293b;">${extracted.articleNo}</strong></div>` : ''}
            ${extracted.mrp ? `<div style="display:flex; justify-content:space-between; padding:0.4rem 0; border-bottom:1px solid #e2e8f0;"><span style="color:#64748b; font-size:0.85rem;">MRP</span><strong style="color:#10b981;">₹${extracted.mrp}</strong></div>` : ''}
            ${extracted.companyName ? `<div style="display:flex; justify-content:space-between; padding:0.4rem 0;"><span style="color:#64748b; font-size:0.85rem;">Company</span><strong style="color:#1e293b;">${extracted.companyName}</strong></div>` : ''}
        </div>
        <p style="color:#64748b; font-size:0.78rem; margin-bottom:1rem;">Please verify the data above before applying. Incorrect data affects your inventory reports.</p>
        <div style="display:flex; gap:0.75rem;">
            <button onclick="document.getElementById('ocrConfirmCard').remove();" style="flex:1; padding:0.75rem; border:1px solid #e2e8f0; border-radius:8px; background:#fff; color:#64748b; font-weight:600; cursor:pointer;">Cancel</button>
            <button id="ocrApplyBtn" style="flex:2; padding:0.75rem; border:none; border-radius:8px; background:linear-gradient(135deg,#4f46e5,#7c3aed); color:#fff; font-weight:700; cursor:pointer; font-size:0.95rem;">✅ Apply to Form</button>
        </div>
    `;

    document.body.appendChild(card);
    document.getElementById('ocrApplyBtn').onclick = () => {
        card.remove();
        onConfirm(extracted);
    };
}
