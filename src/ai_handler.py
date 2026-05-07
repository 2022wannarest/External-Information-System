import google.generativeai as genai

class AIHandler:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
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

        【郵件標題】 {subject}
        【郵件內容】 {body}
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"[AI 處理失敗]：{str(e)}"

    def analyze_fb_post(self, content, comments):
        """針對 FB 貼文進行深度情報分析。"""
        comments_str = "\n".join(comments[:15]) # 取前 15 則留言
        prompt = f"""
        你是一位專業的商業情報分析師。請針對這篇 Facebook 貼文進行深度分析。
        
        【貼文內容】：
        {content}
        
        【精選留言】：
        {comments_str}
        
        【要求】：
        1. 重點摘要：用 3 個列點說明這篇貼文的核心內容。
        2. 情緒分析：分析發文者與留言區的整體情緒（正面/負面/觀望）。
        3. 關鍵資訊：提取出任何日期、價格、聯絡方式或具體數據。
        4. 行動建議：針對這篇情報，建議讀者應該採取什麼行動或注意什麼。
        
        請用繁體中文回覆，保持專業且簡潔。
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"[AI 分析失敗]：{str(e)}"
