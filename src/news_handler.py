import trafilatura
import requests
from bs4 import BeautifulSoup
import urllib.parse

class NewsHandler:
    def get_news(self, keyword, num_results=5):
        print(f"    [News] Searching for: {keyword} on Bing News")
        
        encoded_kw = urllib.parse.quote(keyword)
        url = f"https://www.bing.com/news/search?q={encoded_kw}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        links = []
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Bing News 的標題連結通常在 a.title
                for a in soup.select('a.title')[:num_results]:
                    link = a.get('href')
                    if link and link.startswith('http'):
                        links.append(link)
            print(f"    [News] Found {len(links)} links via Bing")
        except Exception as e:
            print(f"    [News] Bing search failed: {e}")
            return []

        news_data = []
        for link in links:
            print(f"    [News] Fetching: {link}")
            try:
                downloaded = trafilatura.fetch_url(link)
                if downloaded:
                    result = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
                    metadata = trafilatura.extract_metadata(downloaded)
                    title = metadata.title if metadata and metadata.title else "No Title"
                    
                    if result:
                        print(f"    [News] Successfully extracted: {title}")
                        news_data.append({
                            'title': title,
                            'url': link,
                            'content': result
                        })
                    else:
                        print(f"    [News] Extraction failed for {link}")
                else:
                    print(f"    [News] Download failed for {link}")
            except Exception as e:
                print(f"    [News] Error processing {link}: {e}")
        return news_data
