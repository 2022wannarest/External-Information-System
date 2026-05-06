# src/fb_handler.py
 
import asyncio
import os
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
 
SESSION_PATH = os.path.join(os.path.dirname(__file__), '..', 'fb_session.json')
MAX_SCROLLS = 30 # 調高捲動次數，防止漏抓
 
# --- 調試設定 ---
DEBUG_SAVE_HTML = False 
 
# ── Session 管理 ────────────────────────────────────────────────────────────
 
async def save_fb_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.facebook.com/")
        print("請手動登入 Facebook，登入完成後按 Enter...")
        input()
        await context.storage_state(path=SESSION_PATH)
        print(f"Session 已儲存到 {SESSION_PATH}")
        await browser.close()
 
async def ensure_fb_session():
    t0 = time.perf_counter()
    if not os.path.exists(SESSION_PATH):
        await save_fb_session()
        return
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=SESSION_PATH)
        page = await context.new_page()
        try:
            await page.goto("https://www.facebook.com/", wait_until="commit", timeout=20000)
            if "login" in page.url or "checkpoint" in page.url:
                await browser.close()
                await save_fb_session()
            else:
                print(f"✓ FB Session 有效 (檢查耗時 {time.perf_counter()-t0:.2f}s)")
                await browser.close()
        except: await browser.close()
 
async def safe_text(element) -> str:
    try: return (await element.inner_text()).strip()
    except: return ""

def _clean_comment_text(raw_text: str) -> str:
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    if len(lines) < 2: return raw_text
    name, content_parts = lines[0], []
    noise_patterns = [r'^讚$', r'^回覆$', r'^分享$', r'^\d+$', r'^\d+(週|天|小時|分鐘)$', r'^剛剛$', r'^昨天$', r'^.+週前$', r'^.+天前$']
    for line in lines[1:]:
        if any(re.match(p, line) for p in noise_patterns): continue
        if "最相關" in line or "所有留言" in line: continue
        content_parts.append(line)
    content = " ".join(content_parts)
    return f"{name}: {content}" if content else name
 
def _clean_post_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        keep = {k: v for k, v in params.items() if k in ('story_fbid', 'id', 'v')}
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(keep, doseq=True)))
    except: return url
 
def _extract_story_id(href: str) -> str | None:
    if not href: return None
    m = re.search(r'story_fbid=([^&]+)', href)
    if m: return m.group(1)
    m = re.search(r'/(?:posts|permalink|videos)/[^/?#]+/(\d{10,})/?', href)
    if m: return m.group(1)
    m = re.search(r'/(?:posts|permalink|videos)/([^/?#]+)', href)
    if m: return m.group(1)
    m = re.search(r'(pfbid0[A-Za-z0-9]+)', href)
    if m: return m.group(1)
    return None
 
async def _get_post_urls_from_feed(feed_page, scroll_idx) -> dict:
    story_urls: dict[str, str] = {}
    
    # 掃描所有的文章區塊
    articles = await feed_page.locator('div[role="article"]').all()
    for article in articles:
        # --- 排除發文框、廣告、與建議內容 ---
        inner_text = await article.inner_text()
        noise_keywords = ["在想什麼", "建立貼文", "Create a post", "What's on your mind", "贊助", "Sponsored", "建議為你推薦", "Suggested for you"]
        if any(kw in inner_text for kw in noise_keywords):
            continue

        links = await article.locator('a').all()
        for link in links:
            try: 
                href = await link.evaluate("el => el.href") or ""
                # 篩選出貼文連結
                if 'facebook.com' in href and any(k in href for k in ['posts', 'permalink', 'videos', 'story_fbid']):
                    sid = _extract_story_id(href)
                    if sid and sid not in story_urls:
                        story_urls[sid] = href
            except: continue
    return story_urls
 
async def _scrape_post_page(context, post_url: str, now: datetime) -> dict:
    t_start = time.perf_counter()
    page = await context.new_page()
    post_time, content, comments, timings = None, "", [], {}
    try:
        clean_url = _clean_post_url(post_url)
        t0 = time.perf_counter()
        await page.goto(clean_url, wait_until="commit", timeout=30000)
        
        # 強制視窗置頂並停頓 2 秒
        await page.bring_to_front()
        await asyncio.sleep(2)

        try: await page.wait_for_load_state("load", timeout=8000)
        except: pass
        timings['載入'] = time.perf_counter() - t0
 
        t0 = time.perf_counter()
        html_str = await page.content()
        all_ts = re.findall(r'"creation_time":\s*(\d+)', html_str)
        if all_ts: post_time = datetime.fromtimestamp(int(all_ts[0]))
        timings['解析時間'] = time.perf_counter() - t0
 
        t0 = time.perf_counter()
        for btn_text in ["查看更多", "See more", "顯示更多"]:
            try:
                btns = await page.locator(f'div[role="button"]:has-text("{btn_text}")').all()
                for btn in btns:
                    if await btn.is_visible(timeout=200): await btn.click(timeout=1000)
            except: pass
        timings['展開'] = time.perf_counter() - t0
        
        t0 = time.perf_counter()
        for sel in ['[data-ad-comet-preview="message"]', 'div[data-ad-preview="message"]']:
            elems = await page.locator(sel).all()
            if elems:
                # 只抓取第一個元素，避免抓到頁面下方的「推薦貼文」或「相關內容」
                content = await safe_text(elems[0])
                # 過濾開頭雜訊
                if content.startswith("最幸福的事～"):
                    content = content[len("最幸福的事～"):].strip()
                break
        timings['抓內文'] = time.perf_counter() - t0
 
        t0 = time.perf_counter()
        seen = set()
        for ca in await page.locator('div[role="article"]').all():
            if await ca.locator('[data-ad-preview="message"]').count() > 0: continue
            raw_t = await safe_text(ca)
            if raw_t and raw_t not in seen:
                seen.add(raw_t)
                comments.append(_clean_comment_text(raw_t))
        timings['抓留言'] = time.perf_counter() - t0
    except Exception as e: print(f"    ⚠ 錯誤: {e}")
    finally: await page.close()
    
    total = time.perf_counter() - t_start
    timing_str = " | ".join(f"{k}:{v:.1f}s" for k, v in timings.items())
    print(f"    ⏱ 耗時 {total:.1f}s ({timing_str})")
    return {"content": content or "(無法取得內文)", "comments": comments, "post_time": post_time}
 
async def scrape_fb(page_url: str, days_back: int = 3):
    async with async_playwright() as p:
        # 改回 headless=False，讓視窗彈出，這樣抓取較穩定
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900}, 
            storage_state=SESSION_PATH,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        feed_page = await context.new_page()
        now, cutoff = datetime.now(), datetime.now() - timedelta(days=days_back)
        try:
            print(f"開始爬取: {page_url} (截止日期: {cutoff.strftime('%Y/%m/%d')})")
            await feed_page.goto(page_url, wait_until="commit", timeout=30000)
            await asyncio.sleep(3)
            seen_story_ids, total_scrolls, fail_count = set(), 0, 0
            
            while total_scrolls < MAX_SCROLLS:
                story_urls = await _get_post_urls_from_feed(feed_page, total_scrolls)
                for sid, url in story_urls.items():
                    if sid in seen_story_ids: continue
                    seen_story_ids.add(sid)
                    print(f"  → 正在檢查貼文: {sid[:15]}...")
                    post_data = await _scrape_post_page(context, url, now)
                    pt = post_data.get("post_time")
                    pt_str = pt.strftime('%Y/%m/%d') if pt else '時間未知'
                    
                    is_pinned = "置頂" in post_data['content'][:50] or "Pinned" in post_data['content'][:50]
                    
                    if pt and pt < cutoff:
                        if is_pinned:
                            # 即使是置頂，如果太舊（例如超過 30 天）就略過，這通常是不相關的舊公告
                            if pt < (now - timedelta(days=30)):
                                print(f"    - [{pt_str}] 置頂文章過舊，跳過")
                                continue
                            print(f"    - [{pt_str}] 是置頂文章，略過日期檢查")
                            yield post_data
                            continue
                        else:
                            fail_count += 1
                            print(f"    [!] [{pt_str}] 超過日期範圍 (連續第 {fail_count} 篇)")
                            if fail_count >= 2: # 依要求改為 2 篇
                                print(f"    ✗ 連續 2 篇超過範圍，停止本頁爬取")
                                return 
                            continue
                    
                    fail_count = 0 # 抓到正常的，重置計數
                    print(f"    ✓ [{pt_str}] 在時間範圍內，抓取成功")
                    yield post_data
                
                await feed_page.evaluate("window.scrollBy(0, 3000)")
                await asyncio.sleep(1.2) # 稍微增加等待時間，減少漏抓
                total_scrolls += 1
        finally: await browser.close()