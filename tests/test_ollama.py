import requests
import json

# Ollama 服务地址
OLLAMA_HOST = "http://127.0.0.1:11434"
MODEL = "qwen3:32b"
def test_ollama_generate():
    """
    向 Ollama API 发送一个生成请求，用于测试连接和模型。
    """
    # API 端点
    url = f"{OLLAMA_HOST}/api/generate"
    # 请求负载
    payload = {
        "model": MODEL,
        "prompt": "请给我将一个简短地笑话",
        "stream": False,  # 设置为 True 可接收流式响应
        "think": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 32700
        }
    }
    headers = {
        'Content-Type': 'application/json',
    }

    try:
        print(f"正在尝试连接到 Ollama 服务 ({OLLAMA_HOST})...")
        print(f"目标模型: {MODEL}")
        print("-" * 40)

        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        response.raise_for_status()  # 如果响应状态码不是 200，将抛出 HTTPError 异常

        # 解析响应
        result = response.json()

        print("✅ 连接成功！")
        print(f"响应状态码: {response.status_code}")
        print(f"模型实际响应: {result.get('model')}")
        print("\n生成的回复内容：")
        print(result.get('response', 'No response content'))
        print(f"\n总推理耗时: {result.get('total_duration', 0) / 1e9:.2f} 秒")
        print(f"提示词处理耗时: {result.get('prompt_eval_duration', 0) / 1e9:.2f} 秒")
        print(f"回复生成耗时: {result.get('eval_duration', 0) / 1e9:.2f} 秒")

    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败: 无法连接到服务器 {OLLAMA_HOST}。")
        print("请检查：")
        print("  1. Ollama 服务是否已启动 (`ollama serve`)。")
        print("  2. 主机地址和端口 (11434) 是否正确。")
        print("  3. 防火墙或网络设置是否允许连接。")
    except requests.exceptions.Timeout:
        print("❌ 连接超时: 服务器在指定时间内未响应。")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 错误: {e}")
        if response.status_code == 404:
            print("  提示: 请确保模型 `qwen2.5-coder:32b` 已通过 `ollama pull qwen2.5-coder:32b` 下载到本地。")
    except json.JSONDecodeError:
        print("❌ 错误: 无法解析服务器的响应为 JSON。")
        print(f"原始响应文本: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ 发生未知错误: {type(e).__name__} - {e}")

if __name__ == "__main__":
    test_ollama_generate()
