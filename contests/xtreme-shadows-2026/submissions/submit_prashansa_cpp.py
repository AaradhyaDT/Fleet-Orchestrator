import asyncio
import json
import urllib.request
import websockets

async def submit_exact_cpp():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    
    code = '''#include <iostream>

using namespace std;

void solve() {
    int n, k, x;
    cin >> n >> k >> x;

    if (x != 1) {
        cout << "YES\\n" << n << "\\n";
        for (int i = 0; i < n; i++) cout << 1 << " ";
        cout << "\\n";
    } else if (n % 2 == 0 && k >= 2) {
        cout << "YES\\n" << n / 2 << "\\n";
        for (int i = 0; i < n / 2; i++) cout << 2 << " ";
        cout << "\\n";
    } else if (n % 2 != 0 && k >= 3) {
        cout << "YES\\n" << n / 2 << "\\n";
        cout << 3 << " ";
        for (int i = 0; i < (n / 2) - 1; i++) cout << 2 << " ";
        cout << "\\n";
    } else {
        cout << "NO\\n";
    }
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    int t;
    cin >> t;
    while (t--) {
        solve();
    }
    return 0;
}
'''
    async with websockets.connect(ws_url) as ws:
        payload = {
            "code": code,
            "language": "cpp20",
            "contest_slug": "xtreme-shadows-2026"
        }
        js_code = f"""
        (async () => {{
            const csrf = document.querySelector('meta[name="csrf-token"]').content;
            const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/prashansas-forbidden-integer/submissions', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrf
                }},
                body: JSON.stringify({json.dumps(payload)})
            }});
            return JSON.stringify(await res.json());
        }})()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'awaitPromise': True}}))
        res = json.loads(await ws.recv())
        init_res = json.loads(res['result']['result']['value'])
        print("Submission response:", init_res)
        sub_id = init_res['model']['id']
        
        # Poll submissions
        for _ in range(15):
            await asyncio.sleep(2)
            sub_expr = f'''
            (async () => {{
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/prashansas-forbidden-integer/submissions/{sub_id}');
                return JSON.stringify(await resp.json());
            }})()
            '''
            await ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': sub_expr, 'awaitPromise': True}}))
            val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            sub = val.get('model', {})
            print(f"Latest submission: id={sub.get('id')}, status={sub.get('status')}, score={sub.get('score')}")
            if sub.get('status') != 'Processing':
                break

asyncio.run(submit_exact_cpp())
