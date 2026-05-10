import trafilatura
import requests
import re
from bs4 import BeautifulSoup
import urllib.parse
import xml.etree.ElementTree as ET

# 嘗試引入 googlenewsdecoder,沒裝就停用 google 模式
try:
    from googlenewsdecoder import gnewsdecoder
    HAS_DECODER = True
except ImportError:
    HAS_DECODER = False


class NewsHandler:
    def __init__(self, search_engine: str = "google"):
        """
        Args:
            search_engine: "google" 或 "bing"
        """
        self.search_engine = (search_engine or "google").lower()
        if self.search_engine not in ("google", "bing"):
            print(f"[NewsHandler] 未知的 search_engine '{search_engine}',改用 google")
            self.search_engine = "google"

        if self.search_engine == "google" and not HAS_DECODER:
            print("[NewsHandler] 警告: 你選了 google 但沒裝 googlenewsdecoder")
            print("[NewsHandler] 請執行: pip install googlenewsdecoder")
            print("[NewsHandler] 暫時改用 bing")
            self.search_engine = "bing"

        print(f"[NewsHandler] 使用搜尋引擎: {self.search_engine}")

    def _clean_content(self, text: str) -> str:
        """根據關鍵字與模式刪除無關的推薦新聞內容。"""
        if not text: return ""
        
        # 定義固定截斷關鍵字
        stop_keywords = [
            "延伸閱讀", 
            "相關新聞", 
            "更多新聞", 
            "【更多新聞】",
            "看更多", 
            "Yahoo奇摩新聞", 
            "點我看更多",
            "延伸新聞",
            "追蹤更多",
            "其他人也在看"
        ]

        # 定義動態截斷模式 (Regex)
        stop_patterns = [
            r"更多.*報導",
            r"更多.*新聞",
            r"延伸閱讀.*",
            r"[\d\s]*週前",
            r"[\d\s]*天前"
        ]
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 1. 檢查固定關鍵字
            if any(kw in line for kw in stop_keywords):
                break
            
            # 2. 檢查動態模式 (Regex)
            if any(re.search(pat, line) for pat in stop_patterns):
                break

            cleaned_lines.append(line)
            
        return "\n".join(cleaned_lines).strip()

    # ─── Bing 搜尋 (你原本的程式) ─────────────────────────────
    
    def _search_bing(self, keyword: str, num_results: int, session) -> list:
        encoded_kw = urllib.parse.quote(keyword)
        url = f"https://www.bing.com/news/search?q={encoded_kw}"

        links = []
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 多種備用 Selector 確保抓得到連結
                selectors = ['a.title', 'div.news-card a', 'a[data-m]', 'div.caption a']
                for sel in selectors:
                    for a in soup.select(sel):
                        link = a.get('href')
                        if link and link.startswith('http') and 'google.com' not in link:
                            if link not in links:
                                links.append(link)
                        if len(links) >= num_results: break
                    if links: break # 只要其中一個 Selector 抓到就停止
                    
            print(f"    [News] Found {len(links)} links via Bing")
        except Exception as e:
            print(f"    [News] Bing search failed: {e}")
        return links

    # ─── Google News 搜尋 ────────────────────────────────────
    
    def _resolve_google_url(self, google_url: str) -> str | None:
        """用 googlenewsdecoder 解出真實新聞 URL"""
        try:
            result = gnewsdecoder(google_url, interval=1)
            if result.get('status') and result.get('decoded_url'):
                return result['decoded_url']
        except Exception as e:
            print(f"    [News] URL decode error: {e}")
        return None

    def _search_google(self, keyword: str, num_results: int, session) -> list:
        """從 Google News RSS 搜尋並解出真實 URL"""
        encoded_kw = urllib.parse.quote(keyword)
        url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded_kw}"
            f"&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        )
        
        google_urls = []
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                items = root.findall('.//item')
                for item in items[:num_results]:
                    link_elem = item.find('link')
                    if link_elem is not None and link_elem.text:
                        google_urls.append(link_elem.text.strip())
            print(f"    [News] Found {len(google_urls)} google news links")
        except Exception as e:
            print(f"    [News] Google News search failed: {e}")
            return []

        real_urls = []
        for gu in google_urls:
            real = self._resolve_google_url(gu)
            if real and real not in real_urls:
                real_urls.append(real)
        
        print(f"    [News] Decoded {len(real_urls)} real URLs")
        return real_urls

    # ─── 主入口 ─────────────────────────────────────────────
    
    def get_news(self, keyword, num_results=20):
        # 優化搜尋關鍵字，將 "and" 換成空格
        clean_keyword = keyword.replace(" and ", " ").replace(" AND ", " ")
        print(f"    [News] Searching for: {clean_keyword} on {self.search_engine.upper()}")
        
        # 建立一個 Session 並設置更真實的標頭
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        
        # 根據設定挑搜尋引擎
        if self.search_engine == "google":
            links = self._search_google(clean_keyword, num_results, session)
        else:
            links = self._search_bing(clean_keyword, num_results, session)
        
        if not links:
            return []

        # ── 抓內文 (兩種引擎共用) ──
        news_data = []
        for link in links:
            print(f"    [News] Fetching: {link}")
            try:
                # 改用手動 Fetch 以繞過 403 錯誤
                resp = session.get(link, timeout=15, allow_redirects=True)
                final_link = resp.url  # 跟丟 redirect 後的最終網址
                
                if resp.status_code == 200:
                    downloaded = resp.text
                    result = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
                    metadata = trafilatura.extract_metadata(downloaded)
                    title = metadata.title if metadata and metadata.title else "No Title"
                    
                    if result:
                        cleaned_result = self._clean_content(result)
                        print(f"    [News] Successfully extracted: {title}")
                        news_data.append({
                            'title': title,
                            'url': final_link,
                            'content': cleaned_result
                        })
                    else:
                        print(f"    [News] Extraction failed for {link}")
                else:
                    print(f"    [News] Download failed (Status: {resp.status_code}) for {link}")
            except Exception as e:
                print(f"    [News] Error processing {link}: {e}")
        return news_data