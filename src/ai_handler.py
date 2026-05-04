import google.generativeai as genai

class AIHandler:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        # 使用 gemini-2.5-flash 模型
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    def filter_email(self, subject, body):
        """使用 AI 過濾掉郵件中的雜訊，只提取重點。"""
        prompt = f"""
        你是一位專業的資訊整理助手。請幫我閱讀以下郵件內容。
        
        【要求】：
        1. 移除所有不必要的頁尾、安全警語、廣告、格式代碼。
        2. 如果郵件是通知類（如登入成功、帳單通知），請精簡成一句話。
        3. 如果郵件是內容類，請保留完整的郵件內容。
        4. 保持排版簡潔易讀。
        5. 如果這封郵件完全沒有實質內容（純廣告），請回覆「[此郵件無實質內容]」。
        6. 輸出結果

        【郵件標題】 {subject}
        【郵件內容】 {body}
        
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"[AI 處理失敗]：{str(e)}\n\n原始內容：\n{body}"
