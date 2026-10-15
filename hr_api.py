import asyncio
import json
import urllib.request
import websockets

def get_hr_ws_url():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    if not pages:
        raise RuntimeError("No HackerRank page found in open Chrome tabs")
    return pages[0]['webSocketDebuggerUrl']

async def evaluate_js(expr: str):
    ws_url = get_hr_ws_url()
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        msg = {
            'id': 1,
            'method': 'Runtime.evaluate',
            'params': {
                'expression': expr,
                'awaitPromise': True,
                'returnByValue': True
            }
        }
        await ws.send(json.dumps(msg))
        raw = await ws.recv()
        data = json.loads(raw)
        if 'error' in data:
            raise RuntimeError(f"CDP error: {data['error']}")
        result = data.get('result', {})
        if 'exceptionDetails' in result:
            raise RuntimeError(f"JS exception: {result['exceptionDetails']}")
        return result.get('result', {}).get('value')

async def fetch_hr_api(endpoint: str):
    expr = f"""
    (async () => {{
        const resp = await fetch('{endpoint}');
        return await resp.text();
    }})()
    """
    text = await evaluate_js(expr)
    return json.loads(text)

async def post_submission(contest_slug: str, challenge_slug: str, code: str, language: str = 'python3'):
    payload = {
        'code': code,
        'language': language,
        'contest_slug': contest_slug
    }
    payload_json = json.dumps(payload)
    expr = f"""
    (async () => {{
        const csrf = document.querySelector('meta[name="csrf-token"]').content;
        const resp = await fetch('https://www.hackerrank.com/rest/contests/{contest_slug}/challenges/{challenge_slug}/submissions', {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrf
            }},
            body: JSON.stringify({payload_json})
        }});
        return await resp.text();
    }})()
    """
    for post_attempt in range(5):
        res_text = await evaluate_js(expr)
        try:
            res_json = json.loads(res_text)
            if isinstance(res_json, dict) and 'model' in res_json and isinstance(res_json['model'], dict):
                sub_id = res_json['model']['id']
                print(f"Submitted {challenge_slug} ({language}). Submission ID: {sub_id}")
                break
            else:
                print(f"Submission not accepted (attempt {post_attempt+1}): {res_json}. Waiting 20s...")
                await asyncio.sleep(20)
        except Exception as e:
            print(f"Error parsing response: {e}. Waiting 20s...")
            await asyncio.sleep(20)
    else:
        print("All submission attempts failed.")
        return {}
    
    # Poll for result
    for attempt in range(25):
        await asyncio.sleep(2)
        status_data = await fetch_hr_api(f"https://www.hackerrank.com/rest/contests/{contest_slug}/challenges/{challenge_slug}/submissions/{sub_id}")
        m = status_data.get('model', {})
        status = m.get('status')
        score = m.get('score')
        print(f"[{attempt+1}] Status: {status} | Score: {score}")
        if status not in ['Processing', 'Queued']:
            return m
    return m
