import sys
import os
import time
from Bio import SeqIO
from celery_app import app
from celery.result import AsyncResult

# 引用任务名称 (必须与 worker 中的 @app.task(name=...) 一致)
TASK_NAME = 'pipeline.run_analysis'

# 数据路径
PROTEOME_FILE = '/nfs/data/UP000000589_10090.fasta' 
ID_LIST_FILE = 'experiment_ids.txt'

def load_proteome_index(fasta_path):
    print(f"Indexing proteome from {fasta_path}...")
    # key_function=None 表示默认行为：取 > 后的第一个单词
    return SeqIO.index(fasta_path, "fasta")

def validate_id_format(db, target_ids):
    """
    飞行前检查：对比 FASTA 索引的 Key 格式和 ID 列表的格式
    """
    print("\n--- Pre-flight ID Check ---")
    
    # 获取 DB 中的前 3 个 Key
    db_sample_keys = []
    try:
        iterator = iter(db)
        for _ in range(3):
            db_sample_keys.append(next(iterator))
    except StopIteration:
        pass
    
    # 获取 ID 列表中的前 3 个 ID
    list_sample_ids = target_ids[:3]

    print(f"DB Keys Sample (from FASTA): {db_sample_keys}")
    print(f"Target IDs Sample (from txt): {list_sample_ids}")

    # 简单测试第一个目标 ID 是否在 DB 中
    if list_sample_ids and list_sample_ids[0] not in db:
        print("\n[CRITICAL WARNING] First target ID NOT found in database!")
        print("Possible mismatch formats:")
        print(f"  - Database expects: '{db_sample_keys[0]}'")
        print(f"  - You provided:     '{list_sample_ids[0]}'")
        print("Please check if you need to strip 'sp|' prefixes or fix experiment_ids.txt.")
        print("Wait 5 seconds before continuing (Ctrl+C to abort)...")
        time.sleep(5)
    else:
        print("[OK] ID format looks compatible.")
    print("---------------------------\n")

def main():
    if not os.path.exists(PROTEOME_FILE):
        print(f"Error: Proteome file not found at {PROTEOME_FILE}")
        return

    # 1. 加载数据索引
    db = load_proteome_index(PROTEOME_FILE)
    
    # 2. 读取需要处理的 ID
    if not os.path.exists(ID_LIST_FILE):
        print(f"Error: {ID_LIST_FILE} not found.")
        return

    with open(ID_LIST_FILE, 'r') as f:
        target_ids = [line.strip() for line in f if line.strip()]
    
    print(f"Found {len(target_ids)} proteins to process.")
    
    # === 新增：执行格式检查 ===
    validate_id_format(db, target_ids)

    # 3. 分发任务
    sent_count = 0
    skipped_count = 0
    
    for protein_id in target_ids:
        # 获取序列
        if protein_id in db:
            seq_record = db[protein_id]
            sequence_str = str(seq_record.seq)
            
            # 检查结果是否已存在
            safe_id = protein_id.replace('|', '_').replace('/', '_')
            if os.path.exists(f"/nfs/data/results/{safe_id}.json"):
                skipped_count += 1
                if skipped_count % 100 == 0:
                    print(f"Skipped {skipped_count} existing results...")
                continue

            # 发送任务到 Celery
            app.send_task(TASK_NAME, args=[protein_id, sequence_str])
            sent_count += 1
            
            if sent_count % 100 == 0:
                print(f"Submitted {sent_count} tasks...")
        else:
            # 这里的 Else 将会非常关键，如果格式对不上，屏幕会疯狂刷这个 Warning
            print(f"Warning: Protein ID {protein_id} not found in database!")

    print(f"Dispatch Complete. Sent: {sent_count}, Skipped: {skipped_count}")
    db.close()

if __name__ == "__main__":
    main()
