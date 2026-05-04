# src/fb_handler.py
 
import asyncio
import os
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
 
SESSION_PATH = os.path.join(os.path.dirname(__file__), '..', 'fb_session.json')
MAX_SCROLLS = 15
 
# --- 調試設定：設定為 True 會把網頁源碼存到 debug_html 資料夾 ---
DEBUG_SAVE_HTML = True 
 
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
 
def _text_to_datetime(text: str, now: datetime) -> datetime | None:
    t = text.strip().split("\n")[0].strip()
    if re.match(r'^(\d+)天$', t): return now - timedelta(days=int(re.search(r'\d+', t).group()))
    if re.match(r'^\d+(小時|分鐘|秒)$', t): return now
    if any(k in t for k in ["分鐘前", "小時前", "剛剛", "秒前"]): return now
    if "昨天" in t: return now - timedelta(days=1)
    return None
 
def _clean_post_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        keep = {k: v for k, v in params.items() if k in ('story_fbid', 'id', 'v')}
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(keep, doseq=True)))
    except: return url
 
def _extract_story_id(href: str) -> str | None:
    if not href: return None
    # 支援多種 FB 連結 ID 提取
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
    """純 DOM 掃描模式。"""
    story_urls: dict[str, str] = {}
    
    # 調試：儲存 Feed HTML
    if DEBUG_SAVE_HTML:
        try:
            full_html = await feed_page.content()
            debug_dir = os.path.join(os.path.dirname(__file__), '..', 'debug_html')
            os.makedirs(debug_dir, exist_ok=True)
            with open(os.path.join(debug_dir, f"feed_scroll_{scroll_idx}.html"), "w", encoding="utf-8") as f:
                f.write(full_html)
        except: pass

    # 掃描所有的文章區塊
    articles = await feed_page.locator('div[role="article"]').all()
    for article in articles:
        # 在每個文章區塊內找連結
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
    
    # print(f"    [掃描結果] DOM 發現: {len(story_urls)} 篇貼文")
    return story_urls
 
async def _scrape_post_page(context, post_url: str, now: datetime) -> dict:
    t_start = time.perf_counter()
    page = await context.new_page()
    post_time, content, comments, timings = None, "", [], {}
    try:
        clean_url = _clean_post_url(post_url)
        t0 = time.perf_counter()
        await page.goto(clean_url, wait_until="commit", timeout=30000)
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
                content = "\n\n".join([await safe_text(e) for e in elems])
                break
        timings['抓內文'] = time.perf_counter() - t0
 
        t0 = time.perf_counter()
        seen = set()
        for _ in range(5):
            for btn_text in ["查看更多留言", "View more comments", "所有留言"]:
                btn = page.locator(f'div[role="button"]:has-text("{btn_text}")').first
                try: 
                    if await btn.is_visible(timeout=300): await btn.click(timeout=800)
                except: pass
            for ca in await page.locator('div[role="article"]').all():
                if await ca.locator('[data-ad-preview="message"]').count() > 0: continue
                raw_t = await safe_text(ca)
                if raw_t and raw_t not in seen:
                    seen.add(raw_t)
                    comments.append(_clean_comment_text(raw_t))
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.4)
        timings['抓留言'] = time.perf_counter() - t0
    except Exception as e: print(f"    ⚠ 錯誤: {e}")
    finally: await page.close()
    
    total = time.perf_counter() - t_start
    timing_str = " | ".join(f"{k}:{v:.1f}s" for k, v in timings.items())
    print(f"    ⏱ 耗時 {total:.1f}s ({timing_str})")
    
    return {"content": content or "(無法取得內文)", "comments": comments, "post_time": post_time}
 
async def scrape_fb(page_url: str, days_back: int = 3):
    posts_data = []
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
            seen_story_ids, total_scrolls = set(), 0
            while total_scrolls < MAX_SCROLLS:
                story_urls = await _get_post_urls_from_feed(feed_page, total_scrolls)
                for sid, url in story_urls.items():
                    if sid in seen_story_ids: continue
                    seen_story_ids.add(sid)
                    print(f"  → 正在檢查貼文: {sid[:15]}...")
                    post_data = await _scrape_post_page(context, url, now)
                    pt = post_data.get("post_time")
                    pt_str = pt.strftime('%Y/%m/%d') if pt else '時間未知'
                    
                    # 偵測是否為置頂文章 (通常內容會包含 "置頂" 或 Pinned 字樣)
                    is_pinned = "置頂" in post_data['content'][:50] or "Pinned" in post_data['content'][:50]
                    
                    if pt and pt < cutoff:
                        if is_pinned:
                            print(f"    - [{pt_str}] 是置頂文章，略過時間檢查繼續掃描...")
                            posts_data.append(post_data)
                            continue
                        else:
                            print(f"    ✗ [{pt_str}] 超過時間範圍，停止抓取該頁面")
                            return posts_data
                    
                    print(f"    ✓ [{pt_str}] 在時間範圍內，抓取成功")
                    posts_data.append(post_data)
                
                # 提速：縮短滾動後的等待時間
                await feed_page.evaluate("window.scrollBy(0, 2500)")
                await asyncio.sleep(0.8)
                total_scrolls += 1
        finally: await browser.close()
    return posts_data