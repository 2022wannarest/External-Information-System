import os
import base64
import re
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class GmailHandler:
    def __init__(self, credentials_path, token_path):
        self.creds = None
        gmail_token_path = token_path.replace('.json', '_gmail.json')
        
        if os.path.exists(gmail_token_path):
            self.creds = Credentials.from_authorized_user_file(gmail_token_path, SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            with open(gmail_token_path, 'w') as token:
                token.write(self.creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=self.creds)

    def _extract_body_with_links(self, payload):
        """抓取內文，如果遇到 HTML 則將連結轉換為 [名稱: 網址] 格式。"""
        parts = payload.get('parts', [])
        
        # 優先尋找 text/plain
        plain_text = ""
        html_text = ""
        
        if not parts:
            data = payload.get('body', {}).get('data', "")
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            return ""

        for part in parts:
            mime = part.get('mimeType')
            data = part.get('body', {}).get('data', "")
            if mime == 'text/plain' and data:
                plain_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            elif mime == 'text/html' and data:
                html_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            elif 'parts' in part:
                res = self._extract_body_with_links(part)
                if res: return res

        # 如果有 HTML 版，我們用它來提取連結，因為 plain 版通常沒連結
        if html_text:
            soup = BeautifulSoup(html_text, 'html.parser')
            # 移除不必要標籤
            for script in soup(["script", "style"]):
                script.extract()
            
            # 將 <a> 標籤轉換為 [名稱: 網址] 格式
            for a in soup.find_all('a'):
                link_text = a.get_text().strip()
                href = a.get('href', '')
                if href and link_text:
                    a.replace_with(f" [{link_text}: {href}] ")
            
            return soup.get_text(separator='\n')
        
        return plain_text

    def _clean_email_content(self, text):
        """過濾掉常見的郵件噪音和頁尾警語。"""
        if not text: return ""
        
        # 移除 HTML 殘留轉義字元
        text = re.sub(r'&[a-z0-9#]+;', ' ', text, flags=re.IGNORECASE)
        
        lines = text.split('\n')
        cleaned_lines = []
        
        noise_keywords = [
            "親愛的客戶", "敬上", "系統自動發信", "請勿直接回覆",
            "小心保管您的帳號密碼", "非您本人登入", "客服專線",
            "強化資訊安全", "最近登入紀錄", "不使用個人相關資料",
            "身份證字號", "變更密碼", "字元應包含", "特殊符號"
        ]
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 2: continue
            
            if any(k in line for k in noise_keywords):
                continue
            
            # 排除 CSS/代碼殘留
            if '{' in line or '}' in line or '<' in line or '>' in line or 'margin:' in line.lower():
                continue

            cleaned_lines.append(line)
            
        return '\n'.join(cleaned_lines)

    def get_emails(self, folder="INBOX", days_back=1):
        date_threshold = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
        # 這裡加入 label 過濾條件
        query = f"label:{folder} after:{date_threshold}"
        
        results = self.service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        
        email_data = []
        for msg in messages:
            m = self.service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = m.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            
            # 使用連結優化版的抓取
            body = self._extract_body_with_links(payload)
            if body:
                body = self._clean_email_content(body)
            
            email_data.append({
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body,
                'id': msg['id']
            })
        return email_data
