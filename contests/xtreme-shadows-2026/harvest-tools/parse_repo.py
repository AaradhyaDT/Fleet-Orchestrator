import re

with open(r'C:\Users\Aaradhya\.gemini\antigravity\brain\8909590c-aab0-450a-84b7-02184956fb9b\.system_generated\steps\205\content.md', 'r', encoding='utf-8') as f:
    text = f.read()

trees = re.findall(r'/dapingguo8/THUPC2026-final/tree/main/([^"]+)', text)
blobs = re.findall(r'/dapingguo8/THUPC2026-final/blob/main/([^"]+)', text)
print("Trees:", set(trees))
print("Blobs:", set(blobs))
