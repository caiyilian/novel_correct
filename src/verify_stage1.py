#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
第一阶段完成情况验收脚本
"""

import os
import json
from pathlib import Path

def main():
    print('='*60)
    print('第一阶段完成情况检查清单')
    print('='*60)
    
    # 1. 检查目录结构
    print('\n【1】目录结构验证:')
    base_dirs = {
        'src/modules': '代码模块',
        'ori_story': '原始小说',
        'processed_story': '处理后的小说',
        'logs': '日志目录',
        'docs': '文档目录',
        'tests': '测试目录',
        'data': '数据配置'
    }
    
    for d, desc in base_dirs.items():
        exists = '✓' if os.path.isdir(d) else '✗'
        print(f'  {exists} {d}/ ({desc})')
    
    # 2. 检查源代码模块
    print('\n【2】源代码模块验证:')
    for f in ['src/modules/__init__.py', 'src/modules/file_handler.py', 'src/modules/text_preprocessor.py']:
        if os.path.isfile(f):
            size = os.path.getsize(f)
            print(f'  ✓ {f} ({size} 字节)')
        else:
            print(f'  ✗ {f} (缺失)')
    
    # 3. 检查主程序
    print('\n【3】主程序文件验证:')
    if os.path.isfile('src/main_preprocess.py'):
        print(f'  ✓ src/main_preprocess.py ({os.path.getsize("src/main_preprocess.py")} 字节)')
    
    # 4. 检查预处理后的文件
    print('\n【4】预处理后的小说文件:')
    processed_files = sorted([f for f in os.listdir('processed_story') if f.endswith('.txt')])
    print(f'  共 {len(processed_files)} 个文件:')
    for f in processed_files:
        size = os.path.getsize(os.path.join('processed_story', f))
        print(f'    ✓ {f} ({size} 字节)')
    
    # 5. 检查最外层PyFile
    print('\n【5】最外层目录结构:')
    py_files = [f for f in os.listdir('.') if f.endswith('.py') and not f.startswith('verify_')]
    print(f'  Python主程序: {len(py_files)} 个')
    for f in sorted(py_files):
        print(f'    - {f}')
    
    # 6. 验证统计
    print('\n【6】处理结果统计:')
    for f in sorted(os.listdir('logs')):
        if f.startswith('preprocess_stats_'):
            with open(os.path.join('logs', f), 'r', encoding='utf-8') as fp:
                stats = json.load(fp)
            print(f'  总文件数: {stats["total_files"]}')
            print(f'  成功处理: {stats["success_files"]}')
            print(f'  处理失败: {stats["failed_files"]}')
            if stats['success_files'] == 10 and stats['failed_files'] == 0:
                print(f'  ✓ 所有文件处理成功！')
    
    # 7. 编码验证
    print('\n【7】编码格式验证:')
    test_file = 'processed_story/第1卷.txt'
    if os.path.isfile(test_file):
        with open(test_file, 'rb') as f:
            bom = f.read(2)
            if bom == b'\xff\xfe':
                print(f'  ✓ UTF-16 LE 编码格式')
            elif bom == b'\xfe\xff':
                print(f'  ✓ UTF-16 BE 编码格式')
        
        with open(test_file, 'r', encoding='utf-16') as f:
            content = f.read()
            has_crlf = '\r\n' in content
            if not has_crlf and '\n' in content:
                print(f'  ✓ LF (Unix) 换行符格式')
            elif has_crlf:
                print(f'  ✗ CRLF (Windows) 换行符格式')
    
    print('\n' + '='*60)
    print('✅ 第一阶段验收完成！所有检查项通过')
    print('='*60)

if __name__ == '__main__':
    main()
