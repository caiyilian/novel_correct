import requests
import json
import re
import difflib

# Ollama 服务地址
OLLAMA_HOST = "http://172.31.102.189:11434"
MODEL = "qwen2.5-coder:14b"
def test_ollama_generate(my_prompt):
    """
    向 Ollama API 发送一个生成请求
    """
    # API 端点
    url = f"{OLLAMA_HOST}/api/generate"
    # 请求负载
    payload = {
        "model": MODEL,
        "prompt": my_prompt,
        "stream": False,  # 设置为 True 可接收流式响应
        "options": {
            "temperature": 0.0,
            "num_predict": 32700
        }
    }
    headers = {
        'Content-Type': 'application/json',
    }

    response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
    response.raise_for_status()  # 如果响应状态码不是 200，将抛出 HTTPError 异常

    # 解析响应
    result = response.json()
    return result.get('response', 'No response content')
    

if __name__ == "__main__":
    # 我的prompt
    total_story = """然而，罗伦斯从未曾参加过他们的祭典。很遗憾，外人是不允许参加的。 
    「嗨!辛苦了。」 
    罗伦斯朝正在帕斯罗村的麦田一角把麦子往马车上堆的农夫打招呼。马车上的麦穗十分保满.看来可以让购买麦子期货的人们松一口气吧。 
    「喔?」 
    [请问叶勒在哪里啊?」 
    「喔!叶勒在那儿。有没有看到很多人聚集在那边?他就在那块麦田里。叶勒今年都雇用年轻人来种田，因为他们比较不得要领，今年应该是他们田里的某个人会是『赫萝』吧·」 
    农夫晒得黝黑的脸上堆满了笑容说道。那是绝对不会出现在商人脸上，只有没心机的 人才会露出的笑容。"""
    total_story = re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', total_story))
    need_correct = """辛苦了。」 
    罗伦斯朝正在帕斯罗村的麦田一角把麦子往马车上堆的农夫打招呼。马车上的麦穗十分保满.看来可以让购买麦子期货的人们松一口气吧。 
    「喔?」 
    [请问叶勒在哪里啊?」 
    「喔!叶勒在那儿。有没有看到很"""
    need_correct = re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', need_correct))
    my_prompt = f"""### 强制执行规则（100%遵守，禁止任何偏离）
    1.  小说人物对话的唯一合法包裹符号，是成对的全角直角引号「」，其他任何括号、引号均不合法。
    2.  我会发给你两个片段，一个是**原始小说片段**，一个是从**原始小说片段**中间截取的**修正待检查内容**
    2.  仅检查并修正**待检查内容**中「」的使用错误（比如用[、【、"等替代「的错误），或者缺少的情况就要补上，多余的情况就要删去。
    3.  **原始小说片段**包含了修正待检查内容，还包含了两侧的**非修正待检查内容**，**非修正待检查内容**只是作为上下文给你一个完整语境参考，以及防止截取片段把对话截断的时候让你产生误解
    4.  **绝对禁止**续写或者补全句子。如果**修正待检查内容**在句子中间断开，你的输出也必须在完全相同的地方断开。
    5.  **绝对禁止**输出任何解释性文字、前缀或后缀。只输出修正后的文本本身。
    6.  最终返回修正后的**修正待检查内容**,不要输出其他额外内容。

    ---

    **原始小说片段** (仅供参考语境，不要输出):
    ```
    {total_story}
    ```

    ---

    **修正待检查内容** (请直接修正此内容，保持原有截断):
    ```
    {need_correct}
    ```
"""
    
    my_prompt = re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', my_prompt))
    # 期待的回复内容是
    expected_res = """辛苦了。」 
    罗伦斯朝正在帕斯罗村的麦田一角把麦子往马车上堆的农夫打招呼。马车上的麦穗十分饱满.看来可以让购买麦子期货的人们松一口气吧。 
    「喔?」 
    「请问叶勒在哪里啊?」 
    「喔!叶勒在那儿。有没有看到很"""
    expected_res = re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', expected_res))
    


    result = test_ollama_generate(my_prompt)
    print("期待的回复是:\n",expected_res)
    print("-" * 20)
    print("实际回复是:\n",result)
    print("-" * 20)

    # 使用 difflib 进行比较
    print("差异对比:")
    diff = list(difflib.ndiff(expected_res.splitlines(keepends=True), result.splitlines(keepends=True)))
    # 检查是否有差异行（以 - 或 + 开头，忽略 ? 辅助行）
    changes = [line for line in diff if line.startswith('- ') or line.startswith('+ ')]
    
    if not changes:
        print("\n" + "="*40)
        print("✅ 测试通过：实际输出与期待输出完全一致！")
        print("="*40)
    else:
        # 计算相似度
        matcher = difflib.SequenceMatcher(None, expected_res, result)
        ratio = matcher.ratio()
        
        # 定义一个阈值，比如 0.95，如果高于这个值，认为是轻微修改（如错别字修正）
        SIMILARITY_THRESHOLD = 0.95
        
        print("\n" + "="*40)
        if ratio >= SIMILARITY_THRESHOLD:
            print(f"⚠️ 测试通过（但有轻微修改）：相似度 {ratio:.4f}")
            print("说明：模型可能修正了错别字或标点，这在允许范围内。")
        else:
            print(f"❌ 测试失败：相似度 {ratio:.4f} (低于阈值 {SIMILARITY_THRESHOLD})")
            print("说明：差异过大，可能包含幻觉、续写或截断错误。")
            
        print("-" * 40)
        print("详细差异对比：")
        print("  - 开头：期望有但实际缺失的内容")
        print("  + 开头：实际输出多余的内容")
        print("="*40)
        print(''.join(diff))
