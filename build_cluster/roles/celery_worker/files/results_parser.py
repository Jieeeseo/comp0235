import sys
import numpy as np
from scipy.stats import gmean

"""
Script to parse the hhr file produced by HHSearch
"""

def get_hhr_results(hhr_file):
    """
    Reads the hhr file and returns a dictionary of the results
    """
    results = {}
    with open(hhr_file) as fh_in:
        for line in fh_in:
            if line.startswith('Query '):
                results['query_id'] = line.split()[1]
            if line.startswith(' No '):
                # 跳过当前的表头行，读取下一行（第一条命中结果）
                best_hit_line = next(fh_in, None)
                if best_hit_line and best_hit_line.strip():
                    parts = best_hit_line.split()
                    if len(parts) >= 11: # 确保列数足够
                        results['best_hit'] = parts[1]
                        results['best_prob'] = parts[2]
                        results['best_evalue'] = parts[3]
                        results['best_pvalue'] = parts[4]
                        results['best_score'] = parts[5]
                        results['best_aligned_cols'] = parts[6]
                    else:
                        # 兜底：如果第一行数据格式不对
                        results['best_hit'] = "None"
                        results['best_evalue'] = "0"
                        results['best_score'] = "0"
                else:
                     # 没有任何命中结果的情况
                    results['best_hit'] = "None"
                    results['best_evalue'] = "0"
                    results['best_score'] = "0"
                break
    
    # 防止未找到 'Query' 或 'No' 的情况
    if 'query_id' not in results:
        results['query_id'] = "Unknown"
    if 'best_hit' not in results:
        results['best_hit'] = "None"
        results['best_evalue'] = "0"
        results['best_score'] = "0"
        
    return results

def get_score_statistics(hhr_file):
    """
    Reads the hhr file and returns the mean, std dev and geometric mean of the
    scores
    """
    scores = []
    with open(hhr_file) as fh_in:
        # 1. 先定位到 Hit Table 的开始
        in_table = False
        for line in fh_in:
            if line.startswith(' No '):
                in_table = True
                continue # 跳过表头行
            
            if in_table:
                # 2. 如果遇到空行，说明表格结束
                if line.strip() == '':
                    break
                
                # 3. 尝试解析分数列
                parts = line.split()
                # 标准行通常有 11+ 列，分数在第 6 列 (index 5)
                # No Hit Prob E-value P-value Score ...
                if len(parts) > 5:
                    try:
                        # 尝试转换，如果不是数字（比如读到了奇怪的文本），就跳过
                        score = float(parts[5])
                        scores.append(score)
                    except ValueError:
                        continue
    
    if not scores:
        return 0.0, 0.0, 0.0

    return np.mean(scores), np.std(scores), gmean(scores)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)
        
    hhr_file = sys.argv[1]
    
    try:
        results = get_hhr_results(hhr_file)
        mean, std, geometric_mean = get_score_statistics(hhr_file)
        
        print(f"query_id,best_hit,best_evalue,best_score,score_mean,score_std,score_gmean")
        print(f"{results['query_id']},{results['best_hit']},{results['best_evalue']},{results['best_score']},{mean:.2f},{std:.2f},{geometric_mean:.2f}")
    except Exception as e:
        # 如果解析彻底失败，打印错误但不让 Celery 任务崩溃（或者让它崩溃以便重试，看你的选择）
        # 这里选择打印错误信息，会被 pipeline_script 捕获
        print(f"Error parsing HHR: {e}")
        sys.exit(1) 
