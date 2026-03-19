"""
完整的LLM Prompt测试框架
测试"大上下文+仅修改核心区域"的方案

特点：
1. 多个测试用例
2. 完整记录所有Prompt和返回结果
3. 可视化对比结果
4. 相似度分析，判断是否出现幻觉
"""

import requests
import json
import re
import difflib
from pathlib import Path
from datetime import datetime

# Ollama 服务地址
OLLAMA_HOST = "http://172.31.102.189:11434"
MODEL = "qwen2.5-coder:14b"


def test_ollama_generate(my_prompt):
    """向 Ollama API 发送一个生成请求"""
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": MODEL,
        "prompt": my_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 32700
        }
    }
    headers = {
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=120)
        response.raise_for_status()
        result = response.json()
        return result.get('response', 'No response content')
    except Exception as e:
        return f"ERROR: {str(e)}"


def smart_clean(need_correct: str, llm_output: str) -> str:
    """
    智能清理大模型输出
    1. 去除 markdown 代码块包裹符号
    2. 根据原始输入(need_correct)的首尾空白字符习惯，调整输出(llm_output)
    """
    llm_output = llm_output.strip()

    # 去除 markdown 代码块
    match = re.search(r'^```(?:\w+)?\s*\n(.*?)\n\s*```$', llm_output, re.DOTALL)
    if match:
        cleaned = match.group(1)
    else:
        cleaned = llm_output.replace("```", "")

    # 智能调整首尾空白
    original_leading_ws = need_correct[:len(need_correct) - len(need_correct.lstrip())]
    original_trailing_ws = need_correct[len(need_correct.rstrip()):]

    content = cleaned.strip()
    final_result = original_leading_ws + content + original_trailing_ws
    
    return final_result


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.results = []
        self.log_dir = Path("test_results_detailed")
        self.log_dir.mkdir(exist_ok=True)
        
    def run_test(self, test_name: str, total_story: str, need_correct: str, expected_res: str):
        """
        运行一个测试用例
        
        Args:
            test_name: 测试名称
            total_story: 原始文本片段（作为上下文）
            need_correct: 需要修正的内容（核心区域）
            expected_res: 期待的输出结果
        """
        print(f"\n{'='*80}")
        print(f"🧪 测试: {test_name}")
        print(f"{'='*80}")
        
        # 数据清洗（按照示例中的处理方式）
        total_story = re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', total_story))
        need_correct = re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', need_correct))
        expected_res = re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', expected_res))
        
        print(f"📊 数据规模: total_story={len(total_story)} chars, need_correct={len(need_correct)} chars")
        
        # 生成Prompt
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
        
        # 调用API
        print("🔄 正在调用Ollama API...")
        result = test_ollama_generate(my_prompt)
        result = smart_clean(need_correct, result)
        result = re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', result))
        
        # 对比结果
        print("\n📋 对比结果:")
        print("-" * 80)
        
        # 计算相似度
        matcher = difflib.SequenceMatcher(None, expected_res, result)
        ratio = matcher.ratio()
        
        # 生成diff
        diff_lines = list(difflib.unified_diff(
            expected_res.splitlines(keepends=True),
            result.splitlines(keepends=True),
            fromfile='expected',
            tofile='actual',
            lineterm=''
        ))
        
        has_changes = any(line.startswith('- ') or line.startswith('+ ') for line in diff_lines)
        
        # 判断是否通过
        SIMILARITY_THRESHOLD = 0.95
        if not has_changes:
            status = "✅ PASS"
            verdict = "表现完美：实际输出与期待输出完全一致"
        elif ratio >= SIMILARITY_THRESHOLD:
            status = "⚠️ PASS (轻微差异)"
            verdict = f"表现良好：相似度{ratio:.4f}，可能只是轻微修正"
        else:
            status = "❌ FAIL"
            verdict = f"表现不佳：相似度{ratio:.4f}，可能出现幻觉或截断错误"
        
        print(f"状态: {status}")
        print(f"相似度: {ratio:.4f}")
        print(f"评判: {verdict}")
        
        # 保存结果
        test_result = {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'data_size': {
                'total_story': len(total_story),
                'need_correct': len(need_correct)
            },
            'status': status,
            'similarity': ratio,
            'has_changes': has_changes,
            'prompt': my_prompt,
            'response': result,
            'expected': expected_res,
            'diff': ''.join(diff_lines) if diff_lines else "No differences"
        }
        
        self.results.append(test_result)
        
        # 保存文件
        self._save_test_results(test_name, test_result)
        
        # 如果不通过，显示diff
        if has_changes:
            print("\n📊 差异详情:")
            print("-" * 80)
            for line in diff_lines[:30]:
                print(line.rstrip())
            if len(diff_lines) > 30:
                print(f"... (共 {len(diff_lines)} 行)")
        
        return status, ratio
    
    def _save_test_results(self, test_name: str, test_result: dict):
        """保存单个测试的详细结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存JSON结果
        json_file = self.log_dir / f"{test_name}_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({k: v for k, v in test_result.items() if k != 'diff'}, 
                     f, ensure_ascii=False, indent=2)
        
        # 保存Prompt
        prompt_file = self.log_dir / f"{test_name}_prompt_{timestamp}.txt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(test_result['prompt'])
        
        # 保存实际返回
        response_file = self.log_dir / f"{test_name}_response_{timestamp}.txt"
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(test_result['response'])
        
        # 保存期待的返回
        expected_file = self.log_dir / f"{test_name}_expected_{timestamp}.txt"
        with open(expected_file, 'w', encoding='utf-8') as f:
            f.write(test_result['expected'])
        
        # 保存diff
        diff_file = self.log_dir / f"{test_name}_diff_{timestamp}.txt"
        with open(diff_file, 'w', encoding='utf-8') as f:
            f.write(test_result['diff'])
    
    def print_summary(self):
        """打印总结"""
        print(f"\n\n{'='*80}")
        print("📈 测试总结")
        print(f"{'='*80}")
        
        total = len(self.results)
        pass_count = sum(1 for r in self.results if "PASS" in r['status'])
        fail_count = total - pass_count
        
        avg_similarity = sum(r['similarity'] for r in self.results) / total if total > 0 else 0
        
        print(f"总测试数: {total}")
        print(f"通过: {pass_count}")
        print(f"失败: {fail_count}")
        print(f"平均相似度: {avg_similarity:.4f}")
        
        print("\n测试详情:")
        for i, result in enumerate(self.results, 1):
            print(f"  {i}. {result['test_name']}: {result['status']} (相似度: {result['similarity']:.4f})")
        
        print(f"\n结果已保存到: {self.log_dir.absolute()}")


def main():
    runner = TestRunner()
    
    # 测试1：原始示例（已通过）
    print("\n" + "="*80)
    print("🚀 开始测试")
    print("="*80)
    
    runner.run_test(
        test_name="test_01_original_example",
        total_story="""「不管哪一行的生意都不好做呢。」 
罗伦斯苦笑，把蜂蜜糖丢人口中。 
当罗伦斯来到宽广的麦田时，西边的天空已经泛起比麦穗还要美丽的金黄色。远方鸟儿小小的身影赶着回家，处处传来的青蛙鸣，彷佛在宣告自己即将人眠似的。 
几乎所有麦田都已完成收割，应该这几天就会举办祭典。快的话，或许后天就会举办了。 
在罗伦斯眼前延伸开来的这片麦田，是这个区域中以高收割量而自豪的帕斯罗村麦田。收割量越高，村民的生活也就越富裕。再加上管理这一带的亚伦多伯爵是个附近无人不知的怪人，他身为贵族却喜欢下田耕作，因此自然愿意赞助祭典，每年都会在祭典上饮酒欢唱，好不热闹。 
然而，罗伦斯从未曾参加过他们的祭典。很遗憾，外人是不允许参加的。 
「嗨!辛苦了。」 
罗伦斯朝正在帕斯罗村的麦田一角把麦子往马车上堆的农夫打招呼。马车上的麦穗十分饱满.看来可以让购买麦子期货的人们松一口气吧。 
「喔?」 
[请问叶勒在哪里啊?」 
「喔!叶勒在那儿。有没有看到很多人聚集在那边?他就在那块麦田里。叶勒今年都雇用年轻人来种田，因为他们比较不得要领，今年应该是他们田里的某个人会是『赫萝』吧·」 
农夫晒得黝黑的脸上堆满了笑容说道。那是绝对不会出现在商人脸上，只有没心机的人才会露出的笑容。 
罗伦斯以营业用笑容向农夫答谢后，驾着马车朝叶勒的方向前去· 
如农夫所说，确实有很多人聚集在那里，人人都朝麦田中央叫喊着· 
他们对进行最后工作的人叫喊。不过，他们并非在斥骂工作延迟。斥骂本身其实已是祭典的活动之一。 
罗伦斯悠哉地慢慢靠近，终于听见了他们叫喊的内容。 
「有狼喔!有狼!」 
「快看!狼就躺在那边!」 
「是谁?是谁?最后会是谁抓到狼呢?」 
人人脸上展露像是喝了酒似的爽朗笑容.高声叫喊着。就算罗伦斯在人墙后方停下马车.也完全没有人发现他。 
狼是丰收之神的化身。据村民所说.丰收之神就藏在最后割下的麦子里，传说丰收之神会跑进割下最后一束麦子的人体内。 
「最后一束了!」 
「小心不要割过头!」""",
        need_correct="""生意都不好做呢。」 
罗伦斯苦笑，把蜂蜜糖丢人口中。 
当罗伦斯来到宽广的麦田时，西边的天空已经泛起比麦穗还要美丽的金黄色。远方鸟儿小小的身影赶着回家，处处传来的青蛙鸣，彷佛在宣告自己即将人眠似的。 
几乎所有麦田都已完成收割，应该这几天就会举办祭典。快的话，或许后天就会举办了。 
在罗伦斯眼前延伸开来的这片麦田，是这个区域中以高收割量而自豪的帕斯罗村麦田。收割量越高，村民的生活也就越富裕。再加上管理这一带的亚伦多伯爵是个附近无人不知的怪人，他身为贵族却喜欢下田耕作，因此自然愿意赞助祭典，每年都会在祭典上饮酒欢唱，好不热闹。 
然而，罗伦斯从未曾参加过他们的祭典。很遗憾，外人是不允许参加的。 
「嗨!辛苦了。」 
罗伦斯朝正在帕斯罗村的麦田一角把麦子往马车上堆的农夫打招呼。马车上的麦穗十分饱满.看来可以让购买麦子期货的人们松一口气吧。 
「喔?」 
[请问叶勒在哪里啊?」 
「喔!叶勒在那儿。有没有看到很多人聚集在那边?他就在那块麦田里。叶勒今年都雇用年轻人来种田，因为他们比较不得要领，今年应该是他们田里的某个人会是『赫萝』吧·」 
农夫晒得黝黑的脸上堆满了笑容说道。那是绝对不会出现在商人脸上，只有没心机的人才会露出的笑容。""",
        expected_res="""生意都不好做呢。」 
罗伦斯苦笑，把蜂蜜糖丢人口中。 
当罗伦斯来到宽广的麦田时，西边的天空已经泛起比麦穗还要美丽的金黄色。远方鸟儿小小的身影赶着回家，处处传来的青蛙鸣，彷佛在宣告自己即将人眠似的。 
几乎所有麦田都已完成收割，应该这几天就会举办祭典。快的话，或许后天就会举办了。 
在罗伦斯眼前延伸开来的这片麦田，是这个区域中以高收割量而自豪的帕斯罗村麦田。收割量越高，村民的生活也就越富裕。再加上管理这一带的亚伦多伯爵是个附近无人不知的怪人，他身为贵族却喜欢下田耕作，因此自然愿意赞助祭典，每年都会在祭典上饮酒欢唱，好不热闹。 
然而，罗伦斯从未曾参加过他们的祭典。很遗憾，外人是不允许参加的。 
「嗨!辛苦了。」 
罗伦斯朝正在帕斯罗村的麦田一角把麦子往马车上堆的农夫打招呼。马车上的麦穗十分饱满.看来可以让购买麦子期货的人们松一口气吧。 
「喔?」 
「请问叶勒在哪里啊?」 
「喔!叶勒在那儿。有没有看到很多人聚集在那边?他就在那块麦田里。叶勒今年都雇用年轻人来种田，因为他们比较不得要领，今年应该是他们田里的某个人会是『赫萝』吧·」 
农夫晒得黝黑的脸上堆满了笑容说道。那是绝对不会出现在商人脸上，只有没心机的人才会露出的笑容。"""
    )
    
    # 测试2：只修改一个对话符号的错误
    runner.run_test(
        test_name="test_02_single_bracket_error",
        total_story="""罗伦斯听完后，若有所思地点了点头。
"你的生意似乎很成功啊。」
「是的，虽然有时候也会遇到一些麻烦事。」
赫萝笑了笑，转身看向远处的麦田。""",
        need_correct=""""你的生意似乎很成功啊。」
「是的，虽然有时候也会遇到一些麻烦事。」""",
        expected_res="""「你的生意似乎很成功啊。」
「是的，虽然有时候也会遇到一些麻烦事。」"""
    )
    
    # 测试3：多个对话符号的错误
    runner.run_test(
        test_name="test_03_multiple_bracket_errors",
        total_story="""商人和狼在路上行走。
[我们得找个地方休息一下。』
『好的，前面有一个小镇。]
他们继续前进。""",
        need_correct="""[我们得找个地方休息一下。』
『好的，前面有一个小镇。]""",
        expected_res="""「我们得找个地方休息一下。」
「好的，前面有一个小镇。」"""
    )
    
    # 打印总结
    runner.print_summary()


if __name__ == "__main__":
    main()
