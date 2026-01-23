import os
import json
import csv
import glob
import numpy as np

RESULTS_DIR = '/nfs/data/results'
OUTPUT_HITS = 'hits_output.csv'
OUTPUT_PROFILE = 'profile_output.csv'

def safe_float(x):
    """尝试将值转换为浮点数，失败则返回 None"""
    try:
        if x is None:
            return None
        return float(x)
    except (ValueError, TypeError):
        return None

def main():
    print(f"Collating results from {RESULTS_DIR}...")

    json_files = glob.glob(os.path.join(RESULTS_DIR, "*.json"))
    print(f"Found {len(json_files)} result files.")

    all_data = []

    for jf in json_files:
        try:
            with open(jf, 'r') as f:
                data = json.load(f)
                all_data.append(data)
        except Exception as e:
            # 读取文件本身出错（如JSON格式损坏）时不应中断整个流程
            print(f"Error reading {jf}: {e}")

    if not all_data:
        print("No data found!")
        return

    # Hits Output
    print(f"Writing {OUTPUT_HITS}...")
    with open(OUTPUT_HITS, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['fasta_id', 'best_hit_id'])
        for item in all_data:
            # 补丁 A: 使用 .get() 防止 KeyError，默认值给空字符串或 'Unknown'
            writer.writerow([item.get('id', 'Unknown'), item.get('best_hit', 'None')])

    # Profile Output
    print(f"Writing {OUTPUT_PROFILE}...")

    # 补丁 B: 安全转换 float 并过滤无效值
    # 先尝试转换所有数据
    stds_raw = [safe_float(item.get('std')) for item in all_data]
    # 只保留非 None 的有效数字
    stds = [x for x in stds_raw if x is not None]

    gmeans_raw = [safe_float(item.get('gmean')) for item in all_data]
    gmeans = [x for x in gmeans_raw if x is not None]
    
    # 打印一些统计信息，让你知道有多少数据被过滤了
    print(f"Valid STD values: {len(stds)}/{len(all_data)}")
    print(f"Valid GMean values: {len(gmeans)}/{len(all_data)}")

    avg_std = np.mean(stds) if stds else 0.0
    avg_gmean = np.mean(gmeans) if gmeans else 0.0

    with open(OUTPUT_PROFILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ave_std', 'ave_gmean'])
        writer.writerow([avg_std, avg_gmean])

    print("Done!")

if __name__ == "__main__":
    main()
