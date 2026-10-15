import asyncio
import json
import websockets

async def parse_all():
    uri = 'ws://127.0.0.1:9222/devtools/page/7B7F9AD6989751A4193020973931DA9B'
    async with websockets.connect(uri) as ws:
        js = """
        (() => {
            const results = [];
            const cards = document.querySelectorAll('[data-analytics="ContestCardSignupLink"], .contests-list-view, .active-contest-card');
            
            cards.forEach(card => {
                const titleEl = card.querySelector('h4, .contest-item__heading, [class*="heading"]');
                const timeEl = card.querySelector('.contest-item__time, [class*="time"], .end-time');
                const btnEl = card.querySelector('a, button, p[data-automation]');
                const slug = card.getAttribute('data-attr1') || card.getAttribute('data-analytics-slug') || '';
                const status = card.getAttribute('data-attr2') || '';
                
                results.push({
                    title: titleEl ? titleEl.innerText.trim() : '',
                    time: timeEl ? timeEl.innerText.trim() : '',
                    slug: slug,
                    statusAttr: status,
                    actionText: btnEl ? btnEl.innerText.trim() : '',
                    actionHref: btnEl && btnEl.getAttribute('href') ? btnEl.getAttribute('href') : ''
                });
            });

            // Also check hero / carousel items if any
            const heroCards = [];
            document.querySelectorAll('.slick-slide, [class*="banner"], [class*="carousel"], [class*="featured"]').forEach(h => {
                const text = h.innerText.trim();
                if (text && (text.includes('Challenge') || text.includes('Hackathon') || text.includes('Orchestrate'))) {
                    heroCards.push(text);
                }
            });

            return { results, heroCards };
        })()
        """
        msg = {
            'id': 1,
            'method': 'Runtime.evaluate',
            'params': {
                'expression': js,
                'returnByValue': True
            }
        }
        await ws.send(json.dumps(msg))
        resp = await ws.recv()
        res_obj = json.loads(resp)
        print(json.dumps(res_obj.get('result', {}).get('result', {}).get('value', {}), indent=2))

if __name__ == '__main__':
    asyncio.run(parse_all())
