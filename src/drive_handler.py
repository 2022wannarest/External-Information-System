import os
import io
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']

class DriveHandler:
    def __init__(self, credentials_path, token_path):
        self.creds = None
        if os.path.exists(token_path):
            self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(self.creds.to_json())
        
        self.service = build('drive', 'v3', credentials=self.creds)

    def resolve_folder_id(self, identifier):
        """根據名稱或 ID 取得資料夾 ID，若不存在則建立。"""
        # 如果看起來已經是 ID (通常是 25 字元以上的英數組合且沒有空格)
        if len(identifier) > 25 and " " not in identifier:
            return identifier
        
        # 否則，視為名稱並搜尋/建立
        query = f"name = '{identifier}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
        else:
            print(f"    [雲端設定] 找不到資料夾 '{identifier}'，正在為您自動建立...")
            file_metadata = {
                'name': identifier,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')

    def file_exists(self, filename, folder_id):
        """檢查指定資料夾中是否存在同名檔案。"""
        query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        return len(results.get('files', [])) > 0

    def delete_file_by_name(self, filename, folder_id):
        """在指定資料夾中搜尋並刪除同名檔案。"""
        query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        for f in files:
            try:
                self.service.files().delete(fileId=f['id']).execute()
                print(f"    - 已刪除雲端舊檔案: {filename}")
            except: pass

    def get_or_create_subfolder(self, parent_id, folder_name):
        """在指定的父資料夾下尋找或建立子資料夾。"""
        query = f"name = '{folder_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')

    def upload_text(self, filename, content, folder_id, mimetype='text/plain'):
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        fh = io.BytesIO(content.encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype=mimetype)
        file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
