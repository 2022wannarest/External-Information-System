import yaml
import datetime
import asyncio
import re
from src.gmail_handler import GmailHandler
from src.fb_handler import scrape_fb, ensure_fb_session
from src.drive_handler import DriveHandler
from src.ai_handler import AIHandler
from src.news_handler import NewsHandler

def clean_filename(filename):
    """移除檔名中不合法的字元。"""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

async def main():
    # 載入設定
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    drive = DriveHandler(config['drive']['credentials_file'], config['drive']['token_file'])
    today = datetime.date.today().isoformat()
    
    # --- 解析根資料夾 ID (支援 ID 或 名稱) ---
    root_ids = config['drive']['folder_ids']
    email_root_id = drive.resolve_folder_id(root_ids.get('email', 'Email_Research'))
    fb_root_id = drive.resolve_folder_id(root_ids.get('facebook', 'FB_Scraping'))
    news_root_id = drive.resolve_folder_id(root_ids.get('news', 'News_Research'))
    ai_handler = None
    if config.get('ai', {}).get('use_ai'):
        ai_handler = AIHandler(config['ai']['api_key'])
    
    # 1. Email Processing
    email_config = config.get('email')
    if email_config:
        print("Processing Emails...")
        gmail = GmailHandler(config['drive']['credentials_file'], config['drive']['token_file'])
        
        target_folders = email_config.get('folders', ["INBOX"])
        if isinstance(target_folders, str):
            target_folders = [target_folders]
            
        # 使用解析後的根資料夾 ID
        root_email_folder_id = email_root_id
        
        for label_name in target_folders:
            print(f"  -> Fetching Label: {label_name}")
            subfolder_id = drive.get_or_create_subfolder(root_email_folder_id, label_name)
            
            emails = gmail.get_emails(folder=label_name, days_back=email_config.get('days_back', 1))
            
            for em in emails:
                safe_subject = clean_filename(em['subject'])
                filename = f"{today}_{safe_subject[:50]}.txt"
                
                # --- 重複檢查：如果已存在則跳過 ---
                if drive.file_exists(filename, subfolder_id):
                    print(f"    - Skip (Already Exists): {filename}")
                    continue
                
                final_body = em['body']
                if ai_handler and em['body']:
                    print(f"    -> Using AI to filter: {em['subject']}")
                    final_body = ai_handler.filter_email(em['subject'], em['body'])
                
                content = f"【郵件標題】 {em['subject']}\n"
                content += f"【寄件者】   {em['sender']}\n"
                content += f"【收信時間】 {em['date']}\n"
                content += f"{'='*30}\n\n"
                content += final_body
                
                drive.upload_text(filename, content, subfolder_id)
                print(f"    Uploaded: {filename}")

    # 2. Facebook Scraping
    fb_config = config.get('facebook')
    if fb_config and fb_config.get('pages'):
        print("Processing FB Pages...")
        await ensure_fb_session()
        days_back = fb_config.get('days_back', 3)
        
        for page in fb_config['pages']:
            print(f"Scraping FB: {page['name']}")
            posts = await scrape_fb(page['url'], days_back=days_back)
            if posts:
                # 使用解析後的 FB 根資料夾 ID
                page_folder_id = drive.get_or_create_subfolder(fb_root_id, page['name'])
                
                for p in posts:
                    pt = p.get('post_time')
                    date_str = pt.strftime('%Y-%m-%d') if pt else today
                    short_content = clean_filename(p['content'][:30].strip())
                    filename = f"FB_{date_str}_{short_content}.txt"
                    
                    if drive.file_exists(filename, page_folder_id):
                        print(f"    - Skip Post (Already Exists): {filename}")
                        continue
                    
                    content = f"[發文時間] {pt.strftime('%Y/%m/%d %H:%M') if pt else '時間未知'}\n"
                    content += f"Post Content:\n{p['content']}\n"
                    if p['comments']:
                        content += "\nComments:\n" + "\n".join([f"- {c}" for c in p['comments']])
                    
                    drive.upload_text(filename, content, page_folder_id)
                    print(f"    Uploaded Post: {filename}")

    # 3. News Keywords (關鍵字搜尋)
    news_keywords = config.get('news_keywords')
    if news_keywords:
        print("Processing News Keywords...")
        news_handler = NewsHandler()
        
        for kw in news_keywords:
            print(f"Searching News: {kw}")
            # 使用解析後的 News 根資料夾 ID
            kw_folder_id = drive.get_or_create_subfolder(news_root_id, kw)
            articles = news_handler.get_news(kw)
            if articles:
                for art in articles:
                    safe_title = clean_filename(art['title'])
                    filename = f"News_{today}_{safe_title[:50]}.txt"
                    
                    if drive.file_exists(filename, kw_folder_id):
                        continue
                        
                    content = f"Title: {art['title']}\nURL: {art['url']}\nContent:\n{art['content']}\n"
                    drive.upload_text(filename, content, kw_folder_id)
                    print(f"    Uploaded News: {art['title']}")

if __name__ == "__main__":
    asyncio.run(main())
