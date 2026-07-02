import time
import requests
import os

class AIClient:
    def __init__(self, deepseek_token=None, hf_token=None):
        self.deepseek_token = deepseek_token
        self.hf_token = hf_token
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        self.hf_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
        self.max_retries = 3
        self.timeout = 40

    def ask(self, prompt, max_tokens=400):
        if self.deepseek_token:
            result = self._ask_deepseek(prompt, max_tokens)
            if result: return result
        if self.hf_token:
            return self._ask_huggingface(prompt, max_tokens)
        return None

    def _ask_deepseek(self, prompt, max_tokens):
        headers = {"Authorization": f"Bearer {self.deepseek_token}", "Content-Type": "application/json"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": "Ты — астролог с 25-летним опытом. Нейтральные обращения."}, {"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.7}
        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.deepseek_url, headers=headers, json=payload, timeout=self.timeout)
                if response.status_code == 200:
                    text = response.json()["choices"][0]["message"]["content"].strip()
                    if text and len(text) > 10: return text
                elif response.status_code == 429: time.sleep(20 * (attempt + 1))
                else:
                    if attempt < self.max_retries - 1: time.sleep(5)
            except: time.sleep(5)
        return None

    def _ask_huggingface(self, prompt, max_tokens):
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.hf_url, headers=headers, json={"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}}, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and data:
                        text = data[0].get("generated_text", "").strip()
                        if text and len(text) > 10: return text
                time.sleep(10 * (attempt + 1))
            except: time.sleep(5)
        return None

    @staticmethod
    def split_message(text, max_length=4000):
        parts = []
        while len(text) > max_length:
            split_pos = max(text.rfind('\n', 0, max_length), text.rfind('. ', 0, max_length), text.rfind(' ', 0, max_length))
            if split_pos == -1: split_pos = max_length
            parts.append(text[:split_pos].strip())
            text = text[split_pos:].strip()
        if text: parts.append(text)
        return parts

# Инициализация
from dotenv import load_dotenv
load_dotenv()
ai_client = AIClient(deepseek_token=os.getenv("DEEPSEEK_TOKEN"), hf_token=os.getenv("HF_TOKEN"))
