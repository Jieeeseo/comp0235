import re
import sys
import numpy as np
from scipy.stats import gmean

def get_hhr_results(hhr_file):
    """
    Robustly parses HHSearch .hhr file to extract the best hit info.
    """
    best_hit = "None"
    best_evalue = "0"
    best_score = "0"
    
    try:
        with open(hhr_file, 'r') as f:
            lines = f.readlines()
            
        hit_line = None
        
        # 1. 定位表头
        # 表头通常包含: No Hit Prob E-value P-value Score ...
        for i, line in enumerate(lines):
            if "No Hit" in line and "Prob" in line:
                # 表头的下一行就是 Best Hit (No 1)
                if i + 1 < len(lines):
                    hit_line = lines[i+1]
                break
        
        if hit_line:
            # 策略：即使描述文本里有空格，后面的数值列依然遵循特定的数字模式
            # Prob (0-100), E-value (sci), P-value (sci), Score (float)
            
            # 使用 split() 获取第二列作为 ID (通常是可靠的，除非 ID 本身带空格)
            parts = hit_line.strip().split()
            if len(parts) > 1:
                best_hit = parts[1]
            
            # 使用更宽容的正则提取数值
            # 改进点：允许 \d+ (整数) 和 \d+\.\d+ (小数)，防止 100 或 0 导致匹配失败
            # 捕获组: 1=Prob, 2=E-value, 3=P-value, 4=Score
            # 模式解释：
            #   \s+  至少一个空格
            #   (\d+(?:\.\d+)?)  匹配 Prob (整数或小数)
            #   \s+
            #   ([0-9.]+[Ee]?[-+]?\d*) 匹配 E-value
            #   \s+
            #   ([0-9.]+[Ee]?[-+]?\d*) 匹配 P-value
            #   \s+
            #   (\d+(?:\.\d+)?) 匹配 Score
            
            regex_pattern = r'\s+(\d+(?:\.\d+)?)\s+([0-9.]+[Ee]?[-+]?\d*)\s+([0-9.]+[Ee]?[-+]?\d*)\s+(\d+(?:\.\d+)?)'
            match = re.search(regex_pattern, hit_line)
            
            if match:
                best_evalue = match.group(2)
                best_score = match.group(4)
            else:
                # 如果正则失败，打印警告，不要默默失败
                print(f"Warning: Regex failed to match metrics in file {hhr_file}. Line: {hit_line.strip()}")

    except Exception as e:
        print(f"Error parsing HHR {hhr_file}: {e}")
        
    return {
        "best_hit": best_hit,
        "best_evalue": best_evalue,
        "best_score": best_score
    }

def get_score_statistics(hhr_file):
    """
    Calculates Mean, Std, and GMean of the scores of all hits with E-value < 1.e-5
    """
    good_scores = []
    
    try:
        with open(hhr_file, 'r') as f:
            lines = f.readlines()
            
        start_parsing = False
        
        # 同样的宽容正则，确保能抓取到任何格式的数字
        # 我们主要关心 Group 2 (E-value) 和 Group 4 (Score)
        metric_pattern = re.compile(r'\s+(\d+(?:\.\d+)?)\s+([0-9.]+[Ee]?[-+]?\d*)\s+([0-9.]+[Ee]?[-+]?\d*)\s+(\d+(?:\.\d+)?)')

        for line in lines:
            # 找到表头开始解析
            if "No Hit" in line and "Prob" in line:
                start_parsing = True
                continue
            
            if start_parsing:
                if line.strip() == "": break # 空行表示表格结束
                
                match = metric_pattern.search(line)
                if match:
                    try:
                        e_value = float(match.group(2))
                        score = float(match.group(4))
                        
                        # 过滤逻辑：只统计 E-value < 1.0e-5 的显著结果
                        # 这与老师原本的逻辑保持一致
                        if e_value < 1.0e-5:
                            good_scores.append(score)
                    except ValueError:
                        continue
                        
    except Exception as e:
        print(f"Error calculating stats {hhr_file}: {e}")
        
    if not good_scores:
        # 如果没有显著结果，返回 0
        return 0.0, 0.0, 0.0
        
    return np.mean(good_scores), np.std(good_scores), gmean(good_scores)

# 为了兼容性，保留 main 块 (虽然 Celery Worker 是 import 调用，但保留也没坏处)
if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)
    
    hhr_file = sys.argv[1]
    res = get_hhr_results(hhr_file)
    stats = get_score_statistics(hhr_file)
    print(res, stats)
