import sys
import os
import shutil
import uuid
import json
import logging
from subprocess import run, PIPE
from celery_app import app
# 直接导入解析器函数，而不是用 subprocess 调用
import results_parser

# ================= 配置路径 =================
S4PRED_SCRIPT = '/opt/s4pred/run_model.py'
HHSEARCH_BIN = '/opt/hh-suite/bin/hhsearch'
HHSEARCH_DB = '/nfs/pdb70/pdb70'
# 结果直接写入 NFS，保证数据安全
RESULTS_DIR = '/nfs/data/results'

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= 辅助函数 =================

def run_hhsearch(a3m_file, hhr_file, cpu_cores=1):
    # 检查数据库
    if not os.path.exists(HHSEARCH_DB + "_hhm.ffindex"):
         return False, f"Database not found at {HHSEARCH_DB}"

    cmd = [HHSEARCH_BIN, '-i', a3m_file, '-cpu', str(cpu_cores), '-d', HHSEARCH_DB, '-o', hhr_file]
    
    # 使用 subprocess.run 更现代、更安全
    result = run(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    
    if result.returncode == 0:
        return True, "Success"
    else:
        return False, result.stderr

def read_horiz(tmp_file, horiz_file, a3m_file):
    if not os.path.exists(horiz_file): return False
    
    pred, conf = '', ''
    with open(horiz_file) as fh:
        for line in fh:
            if line.startswith('Conf: '): conf += line[6:].rstrip()
            if line.startswith('Pred: '): pred += line[6:].rstrip()
            
    with open(tmp_file) as fh:
        contents = fh.read()
        
    with open(a3m_file, "w") as fh_out:
        fh_out.write(f">ss_pred\n{pred}\n>ss_conf\n{conf}\n")
        fh_out.write(contents)
    return True

def run_s4pred(input_file, out_file):
    cmd = ['python3', S4PRED_SCRIPT, '-t', 'horiz', '-T', '1', input_file]
    result = run(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    
    if result.returncode != 0:
        return False, result.stderr
    
    with open(out_file, "w") as fh:
        fh.write(result.stdout)
    return True, "Success"

# ================= Celery Task =================

@app.task(name='pipeline.run_analysis', bind=True)
def run_analysis_task(self, sequence_id, sequence_data):
    # 1. 创建唯一的临时工作目录，避免并发冲突
    task_uid = str(uuid.uuid4())
    work_dir = os.path.join('/opt/calc_engine/work_dir', task_uid)
    os.makedirs(work_dir, exist_ok=True)
    
    # 确保 NFS 结果目录存在
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # 定义绝对路径
    safe_id = sequence_id.replace('|', '_').replace('/', '_')
    tmp_fas = os.path.join(work_dir, 'query.fas')
    horiz_file = os.path.join(work_dir, 'query.horiz')
    a3m_file = os.path.join(work_dir, 'query.a3m')
    hhr_file = os.path.join(work_dir, 'query.hhr')
    
    # 最终结果文件路径
    final_json_path = os.path.join(RESULTS_DIR, f"{safe_id}.json")

    # 如果结果已存在，直接跳过 (幂等性设计)
    if os.path.exists(final_json_path):
        shutil.rmtree(work_dir)
        return f"Skipped: {sequence_id} already exists"

    try:
        # Step 1: Write FASTA
        with open(tmp_fas, "w") as f:
            f.write(f">{sequence_id}\n{sequence_data}\n")

        # Step 2: S4Pred
        ok, msg = run_s4pred(tmp_fas, horiz_file)
        if not ok: raise Exception(f"S4Pred failed: {msg}")

        # Step 3: Convert
        if not read_horiz(tmp_fas, horiz_file, a3m_file):
            raise Exception("Horiz parsing failed")

        # Step 4: HHSearch
        ok, msg = run_hhsearch(a3m_file, hhr_file)
        if not ok: raise Exception(f"HHSearch failed: {msg}")

        # Step 5: Parse Results (调用 Python 函数)
        if os.path.exists(hhr_file) and os.path.getsize(hhr_file) > 0:
            # 获取 Best Hit 信息
            hit_info = results_parser.get_hhr_results(hhr_file)
            # 获取统计信息 (Mean, Std, GMean)
            mean, std, gmean = results_parser.get_score_statistics(hhr_file)
            
            # 构造最终数据结构
            output_data = {
                "id": sequence_id,
                "best_hit": hit_info.get('best_hit', 'None'),
                "best_evalue": hit_info.get('best_evalue', '0'),
                "best_score": hit_info.get('best_score', '0'),
                "mean": mean,
                "std": std,
                "gmean": gmean
            }
            
            # 写入 NFS
            with open(final_json_path, 'w') as f:
                json.dump(output_data, f)
                
            return f"Done: {sequence_id}"
        else:
            raise Exception("Empty HHR output")

    except Exception as e:
        logger.error(f"Task failed for {sequence_id}: {e}")
        # 即使失败也抛出异常，让 Celery 知道
        raise e
        
    finally:
        # 无论成功失败，都清理临时目录
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
