import asyncio
import json
import urllib.request
import websockets

async def check_all():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    if not pages:
        print("No HackerRank page found!")
        return
    ws_url = pages[0]['webSocketDebuggerUrl']
    
    async with websockets.connect(ws_url) as ws:
        # Check leaderboard to get current user rank and score
        expr_lb = """
        (async () => {
            const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/leaderboard?offset=0&limit=10');
            return JSON.stringify(await resp.json());
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr_lb, 'awaitPromise': True}}))
        val_lb = json.loads(json.loads(await ws.recv())['result']['result']['value'])
        
        print("--- TOP LEADERBOARD ---")
        for m in val_lb.get('models', []):
            print(f"Rank {m.get('rank')}: {m.get('hacker')} | Score: {m.get('score')} | Time: {m.get('time_taken')}")
            
        # Now let's fetch all challenges list with status
        with open('all_challenges.json', 'r', encoding='utf-8') as f:
            all_c = json.load(f)
            
        print("\n--- CHECKING SUBMISSIONS PER CHALLENGE ---")
        total_score = 0
        unsolved = []
        for m in all_c['models']:
            slug = m['slug']
            expr_sub = f"""
            (async () => {{
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{slug}/submissions');
                return JSON.stringify(await resp.json());
            }})()
            """
            await ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': expr_sub, 'awaitPromise': True}}))
            val_sub = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            subs = val_sub.get('models', [])
            best_score = 0
            best_status = 'Unattempted'
            if subs:
                for s in subs:
                    sc = float(s.get('score', 0))
                    if sc > best_score:
                        best_score = sc
                        best_status = s.get('status')
                    elif best_status == 'Unattempted':
                        best_status = s.get('status')
            total_score += best_score
            max_sc = m.get('max_score')
            if best_score == max_sc:
                print(f"[AC {best_score}/{max_sc}] {m['name']} ({slug})")
            elif best_score > 0:
                print(f"[PARTIAL {best_score}/{max_sc}] {m['name']} ({slug})")
                unsolved.append((slug, m['name'], best_score, max_sc))
            else:
                print(f"[TODO 0/{max_sc}] {m['name']} ({slug}) - Status: {best_status}")
                unsolved.append((slug, m['name'], 0, max_sc))
                
        print(f"\nTOTAL CALCULATED SCORE: {total_score}")

asyncio.run(check_all())
