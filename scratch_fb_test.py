import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.facebook.com/profile.php?id=61578106860333")
        await page.wait_for_selector('div[role="main"]', timeout=10000)
        
        # Scroll
        for _ in range(2):
            await page.mouse.wheel(0, 1500)
            await asyncio.sleep(2)
            
        print("Clicking see more...")
        # find all see more
        locators = await page.get_by_role("button", name="查看更多").all()
        for loc in locators:
            try:
                await loc.click(timeout=1000)
                await asyncio.sleep(1)
                print("Clicked one!")
            except Exception as e:
                print(e)
                
        articles = await page.query_selector_all('div[role="article"]')
        print(f"Found {len(articles)} articles")
        for i, art in enumerate(articles[:3]):
            print(f"--- Article {i} ---")
            msg = await art.query_selector('div[data-ad-preview="message"]')
            if msg:
                print("Msg:", await msg.inner_text())
            else:
                print("No message preview div")
                divs = await art.query_selector_all('div[dir="auto"]')
                for d in divs:
                    text = await d.inner_text()
                    if len(text) > 20:
                        print("Fallback div:", text[:100])
                        break
        await browser.close()

asyncio.run(test())
