from src.news_handler import NewsHandler

handler = NewsHandler()
keyword = "TSMC stock"
print(f"Testing search for: {keyword}")
results = handler.get_news(keyword, num_results=3)

print(f"Found {len(results)} articles.")
for i, res in enumerate(results):
    print(f"[{i+1}] Title: {res['title']}")
    print(f"    URL: {res['url']}")
