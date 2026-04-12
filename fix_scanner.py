import re

with open('templates/inventory.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace opening wrapper
text = re.sub(
    r'<div id="readerWrapper" style="display:none;.*?border:2px solid var\(--primary\);">',
    '<div id="readerWrapper" class="scanner-wrapper-premium" style="display:none;">\n                <div class="scanner-inner">',
    text, flags=re.DOTALL
)

# Replace closing wrapper
text = re.sub(
    r'(<button class="btn danger" onclick="stopBarcodeScanner\(\)".*?</button>\s*</div>\s*)</div>',
    r'\1</div>\n            </div>',
    text, flags=re.DOTALL
)

with open('templates/inventory.html', 'w', encoding='utf-8') as f:
    f.write(text)

with open('templates/add_product.html', 'r', encoding='utf-8') as f:
    text2 = f.read()

text2 = re.sub(
    r'(<button type="button" class="btn danger" onclick="stopBarcodeScannerAdd\(\)".*?</button>\s*</div>\s*)</div>',
    r'\1</div>\n                </div>',
    text2, flags=re.DOTALL
)

with open('templates/add_product.html', 'w', encoding='utf-8') as f:
    f.write(text2)

print("Done")
