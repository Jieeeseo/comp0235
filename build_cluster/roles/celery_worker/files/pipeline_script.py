import sys
import os
import shutil
from subprocess import Popen, PIPE
from celery_app import app 

# ================= 配置路径 =================
# 确保这些路径与你之前验证通过的路径一致
S4PRED_SCRIPT = '/opt/s4pred/run_model.py'
HHSEARCH_BIN = '/opt/hh-suite/bin/hhsearch'
HHSEARCH_DB = '/nfs/pdb70/pdb70' 
RESULTS_PARSER = '/opt/calc_engine/results_parser.py'
# ===========================================

def run_parser(hhr_file):
    cmd = ['python3', RESULTS_PARSER, hhr_file]
    p = Popen(cmd, stdin=PIPE,stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    return out.decode("utf-8") if p.returncode == 0 else f"Error: {err.decode('utf-8')}"

def run_hhsearch(a3m_file, hhr_file):
    # 检查数据库文件是否存在
    db_check_path = HHSEARCH_DB + "_hhm.ffindex"
    if not os.path.exists(db_check_path) and not os.path.exists(HHSEARCH_DB + ".hhm"):
        return False, f"Database not found at {HHSEARCH_DB}"

    # 修正: 添加 -o 参数，将结果写入文件，而不是仅打印到屏幕
    cmd = [HHSEARCH_BIN, '-i', a3m_file, '-cpu', '1', '-d', HHSEARCH_DB, '-o', hhr_file]
    
    p = Popen(cmd, stdin=PIPE,stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    
    # 既然指定了 -o 输出到文件，这里 stdout (out) 通常是空的或者只有日志，不需要返回作为结果内容
    return (True, "Run Complete") if p.returncode == 0 else (False, err.decode('utf-8'))

def read_horiz(tmp_file, horiz_file, a3m_file):
    if not os.path.exists(horiz_file):
        return False
    pred = ''
    conf = ''
    with open(horiz_file) as fh_in:
        for line in fh_in:
            if line.startswith('Conf: '): conf += line[6:].rstrip()
            if line.startswith('Pred: '): pred += line[6:].rstrip()
    with open(tmp_file) as fh_in:
        contents = fh_in.read()
    with open(a3m_file, "w") as fh_out:
        fh_out.write(f">ss_pred\n{pred}\n>ss_conf\n{conf}\n")
        fh_out.write(contents)
    return True

def run_s4pred(input_file, out_file):
    cmd = ['python3', S4PRED_SCRIPT, '-t', 'horiz', '-T', '1', input_file]
    p = Popen(cmd, stdin=PIPE,stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        return False, err.decode('utf-8')
    else:
        # S4Pred 将结果打印到 stdout，我们需要手动写入文件
        with open(out_file, "w") as fh_out: fh_out.write(out.decode("utf-8"))
        return True, "Success"

# ================= Celery Task 定义 =================

@app.task(name='pipeline.run_analysis')
def run_analysis_task(sequence_id, sequence_data):
    """
    Celery Worker 执行入口
    """
    work_dir = '/opt/calc_engine/work_dir'
    if not os.path.exists(work_dir):
        os.makedirs(work_dir, exist_ok=True)
    os.chdir(work_dir)

    safe_id = sequence_id.replace('|', '_').replace('/', '_')
    base_name = f"{safe_id}"
    tmp_file = f"{base_name}.fas"
    horiz_file = f"{base_name}.horiz"
    a3m_file = f"{base_name}.a3m"
    hhr_file = f"{base_name}.hhr"

    try:
        # 1. 写入临时 FASTA 文件
        with open(tmp_file, "w") as fh_out:
            fh_out.write(f">{sequence_id}\n{sequence_data}\n")

        # 2. 运行 S4Pred
        success, msg = run_s4pred(tmp_file, horiz_file)
        if not success: return f"S4Pred Failed: {msg}"

        # 3. 格式转换
        if not read_horiz(tmp_file, horiz_file, a3m_file):
            return "Read Horiz Failed: .horiz file missing"

        # 4. 运行 HHSearch (传入输出文件名 hhr_file)
        success, msg = run_hhsearch(a3m_file, hhr_file)
        if not success: return f"HHSearch Failed: {msg}"

        # 5. 运行 Parser
        if os.path.exists(hhr_file) and os.path.getsize(hhr_file) > 0:
            result_txt = run_parser(hhr_file)
            
            # 清理临时文件
            for f in [tmp_file, horiz_file, a3m_file, hhr_file]:
               if os.path.exists(f): os.remove(f)
            
            return result_txt 
        else:
            return "HHR file missing or empty"

    except Exception as e:
        return f"Exception in worker: {str(e)}"
