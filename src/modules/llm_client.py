import requests
import json
from src.config.settings import OLLAMA_HOST, LLM_OPTIONS

def call_ollama_api(prompt: str, model_name: str = "qwen2.5-coder:32b", use_think: bool = False) -> str:
    """
    向 Ollama API 发送一个生成请求
    """
    # API 端点
    url = f"{OLLAMA_HOST}/api/generate"
    
    # 请求负载
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,  # 设置为 True 可接收流式响应
        "think": use_think,
        "options": LLM_OPTIONS
    }
    
    headers = {
        'Content-Type': 'application/json',
    }

    response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
    response.raise_for_status()  # 如果响应状态码不是 200，将抛出 HTTPError 异常

    # 解析响应
    result = response.json()
    return result.get('response', 'No response content')
