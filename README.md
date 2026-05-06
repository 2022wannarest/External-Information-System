# 自動化外部研究資訊累積系統 (Research Automation System)

這個系統旨在自動化收集外部資訊，包括電子郵件、Facebook 社群觀點及新聞。所有結果將自動上傳至您的 Google Drive 指定資料夾。

## 專案結構
- `main.py`: 主程式，負責調用各個模組。
- `config.yaml`: 所有的關鍵字、FB 帳號及 Google Drive 資料夾 ID 都在此設定。
- `src/`: 包含各個功能模組（Drive, Gmail, FB, News）。
- `requirements.txt`: 專案所需的 Python 函式庫。

## 設定步驟

### 1. Google API 憑證申請流程
關鍵在於透過 Google Cloud Console 完成專案建立與權限核發。以下為標準化操作步驟：

#### 第一階段：建立雲端專案與啟用服務
1.  **進入控制台**：前往 [Google Cloud Console](https://console.cloud.google.com/) 並登入您的 Google 帳號。
2.  **建立專案**：點擊左上角的專案選單，選擇 「新增專案」，輸入專案名稱（如：`Research-Automation`）後點擊建立。
3.  **啟用 API**：
    *   點選左側選單的 「API 和服務」 > 「程式庫」。
    *   搜尋並分別 **啟用** 「Google Drive API」 與 「Gmail API」。

#### 第二階段：設定 OAuth 同意畫面 (初次設定必做)
這是為了告訴 Google 誰在調用權限：
1.  點擊左側 「API 和服務」 > 「OAuth 同意畫面」。
2.  左側「目標對象」使用者類型選擇 「外部 (External)」 並點擊建立。
3.  填寫 「應用程式名稱」 與 「開發者聯絡資訊」（填您的 Email 即可），其餘選填，最後點擊儲存並繼續。
4.  **重要步驟（測試人員）**：
    *   在同一頁面找到 「測試使用者」 區塊。
    *   點擊 「+ ADD USERS」，輸入您自己的 Gmail（如：`a200001451@gmail.com`）。
    *   *註：若未加入測試人員，執行程式時會出現 403 access_denied 錯誤。*

#### 第三階段：建立 OAuth 2.0 憑證 (取得金鑰)
1.  點擊左側選單的 「API 和服務」 >「憑證」。
2.  點擊上方 「+ 建立憑證」，選擇 「OAuth 用戶端 ID」。
3.  應用程式類型：務必選擇 「**電腦版應用程式 (Desktop App)**」。
4.  名稱可自訂（如：`My-Automation-Client`），點擊建立。
5.  **下載 JSON**：在彈出的視窗中點擊 「下載 JSON」。

#### 第四階段：部署至 Python 專案
1.  **重新命名**：將下載的長檔名 JSON 檔案重新命名為 `credentials.json`。
2.  **放置路徑**：將此檔案放入您的專案根目錄，確保與 `main.py` 在同一層級。
3.  **執行授權**：
    *   在終端機執行 `python main.py`。
    *   瀏覽器會自動開啟，登入帳號後若看到「Google 尚未驗證此應用程式」，請點擊 「進階」 > 「前往...（不安全）」。
    *   勾選所有權限框（Drive 與 Gmail），按繼續。
4.  **產生 Token**：完成後，專案目錄會自動產生 `token.json` 與 `token_gmail.json`，未來執行程式就不再需要重新登入。

### 2. 安裝依賴項
在終端機執行：
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 配置 config.yaml
請修改 `config.yaml`：
- `folder_ids`: 填入您的 Google Drive 資料夾 ID（從網址列取得）。
- `facebook_pages`: 增加或修改想要追蹤的 FB 頁面。
- `news_keywords`: 增加想要搜尋的新聞關鍵字。

### 4. AI 智慧過濾設定 (選用)
本系統支援使用 Google Gemini AI 來對 Email 進行二次過濾，移除垃圾資訊並自動摘要。
1.  **取得 API Key**：前往 [Google AI Studio](https://aistudio.google.com/app/apikey) 點擊 「Create API key」。
2.  **配置 config.yaml**：
    *   `use_ai`: 設定為 `true` 開啟功能，設為 `false` 則關閉。
    *   `api_key`: 貼上您申請到的金鑰。
3.  **效果**：開啟後，系統會自動移除郵件中的安全警語、廣告頁尾，並將通知類郵件（如登入通知、帳單）濃縮成精簡重點，讓雲端硬碟的檔案更易讀。

## 🕒 自動化執行設定 (每天定時執行)

本專案支援 Windows 與 macOS 的自動排程。建議設定在每天早上 09:00 執行。

### 1. Windows 系統 (工作排程器)
- **方法 A (自動設定)**：執行 `python setup_scheduler.py` 即可自動建立任務。
- **方法 B (手動設定)**：
  1. 開啟「工作排程器」，建立基本任務。
  2. 程式或指令碼填入：`cmd.exe`
  3. 新增引數填入：`/k "C:\路徑\到\專案\run_daily.bat"`
  4. 「開始於」填入：`C:\路徑\到\專案` (務必填寫，否則會閃退)

### 2. macOS 系統 (Crontab)
1. 賦予權限：`chmod +x run_daily.sh`
2. 開啟排程設定：`crontab -e`
3. 加入以下內容 (每天 09:00 執行)：
   ```bash
   0 9 * * * /絕對路徑/到/您的資料夾/run_daily.sh
   ```

---

## 🛠️ 常見問題與偵錯 (Troubleshooting)
- **閃退問題**：若 Windows 排程執行時閃退，請檢查 `run_daily.bat` 的編碼是否為 ANSI，或檢查排程器中的「開始於」路徑是否正確。
- **FB 抓取失敗**：請檢查 `fb_session.json` 是否過期，若過期請刪除該檔案並重新執行 `main.py` 進行登入。
- **Google 授權錯誤**：若出現 403 錯誤，請確認您已在 Google Cloud Console 中將您的 Email 加入「測試使用者」。


## 更換帳號與資料夾指南

如果您需要更換抓取的信箱、存檔的雲端硬碟或 Facebook 帳號，請參考以下步驟：

### 1. 更換 Google 帳號 (Gmail & Drive)
若要換成另一個 Google 帳號來讀信或存檔到不同人的雲端硬碟：
*   **步驟**：
    1. 刪除專案根目錄下的 `token.json`。
    2. 執行 `python main.py`。
    3. 在自動彈出的瀏覽器視窗中，選擇並登入您的**新 Google 帳號**，並點擊「允許」授權。
*   **原理**：`token.json` 是您個人的授權鑰匙，刪除它會強制程式要求您重新登入。

### 2. 更換 Facebook 帳號
若要更換爬取貼文的身分：
*   **步驟**：
    1. 刪除專案根目錄下的 `fb_session.json`。
    2. 執行 `python main.py`。
    3. 程式會彈出一個瀏覽器視窗，請在該視窗中**手動登入您的新 FB 帳號**。
    4. 登入成功後關閉視窗，程式會自動更新 Session 資訊。

### 3. 更換儲存的雲端資料夾
若不換帳號，只是想存到不同的資料夾：
*   **步驟**：
    1. 在 Google Drive 進入新資料夾，從網址列最後面複製那串亂碼（Folder ID）。
    2. 修改 `config.yaml` 中的 `drive -> folder_ids` 區塊，替換對應的 ID。
*   **注意**：請確保您目前登入的 Google 帳號對該資料夾有「編輯」權限。

### 4. 關於 `credentials.json`
*   **這通常不需要更換**。它代表的是「這個應用程式的身分」。
*   除非您要在 Google Cloud Console 建立一個全新的「專案」，才需要下載新的 `credentials.json` 取代舊的。
