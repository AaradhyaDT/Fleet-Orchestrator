import urllib.request
import json

tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
for i, t in enumerate(tabs):
    if t.get('type') == 'page':
        print(f"{i}: {t.get('title')} -> {t.get('url')}")
