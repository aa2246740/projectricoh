#!/usr/bin/env python3
"""Append only the four milestones authorized in this research brief, once."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import fcntl
import io
import sys

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT


def main():
    milestones=[
        ('body_rpc8_probe_result',
         'R-ROM为优先候选：机身RPC8可用X/V/W访问模块源表；ABI、读回与T提交边界已有静态证据',
         'V记账计数、游标独占、运行可达、SDRAM写入与冷启动复原仍未验证；T并非已证明永不自动提交',
         'research/body_rpc8_probe/REPORT.md; research/canonical_gr_pack/REPORT.md',
         'SPECIFICATION_ONLY_GATED；未连接相机，未生成注入固件'),
        ('gr_complete_pipeline_result',
         'GRD IV正片curve24..32中心28与color9..12/25..28已命名；GRIII原生默认滑杆和III/IV GammaTuning整数算法已恢复',
         '原生矩阵+gamma部分模型已对bastibe24块RAW/JPEG检验；尚未同时通过参考端0.5/1.0 ΔE00门槛',
         'research/gr_complete_pipeline/REPORT.md; research/canonical_gr_pack/sourced_reference_check.json',
         'PARTIAL；不把共享曲线、原始表或部分模型称为完整GR渲染器'),
        ('color_references_result',
         '保留真实GRIII原机色卡配对、DNG共同白点桥与屏幕工具；新增R8051140..1143四对GXR实拍、192块提取；本包仅使用Ricoh原生固件目标',
         'Adobe DCP不作为本包目标；四张GXR照片不能辨识真实GR传感器桥或15个控件；本批WB增益最大漂移6.17%',
         'research/color_references/REPORT.md; research/canonical_gr_pack/calibrate_from_macbook_captures.py',
         'SCREEN_DIAGNOSTIC_FIT；192/192基础提取有效；GRD IV完整颜色和品牌视觉匹配未验收'),
        ('canonical_gr_pack_synthesized',
         '单一正片选1B原生GRD IV row28+color10/26；负片选GRIII原生gamma+III/IV同字节矩阵；HC选GRD IV row11+GXR03候选，另保留GRIV原生HC合成曲线',
         '修正GRD IV HC=mode11、mode12=Cross；GXR10..18依赖Q64条件非03专属；GRIV index16 descriptor flag1专用LUT已作独立整数与原指令模型核对',
         'research/canonical_gr_pack/REPORT.md; canonical_16_slots.json; deep_isp_tables.json; verification.json',
         '16槽研究候选与4对真实诊断拟合；Stage1c v2为RECIPE20/21.DAT，1056B；主机检查不等于深表/色彩验收'),
    ]
    path=ROOT/'decisions.tsv'
    with path.open('a+',newline='') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        handle.seek(0)
        existing=list(csv.reader(handle,delimiter='\t'))
        if not existing or existing[0]!=['ts','phase','decision','why','evidence','result']:
            raise ValueError('Unexpected decisions.tsv schema')
        phases={row[1] for row in existing[1:] if len(row)==6}
        now=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
        buffer=io.StringIO(newline='')
        writer=csv.writer(buffer,delimiter='\t',lineterminator='\n')
        added=[]
        for row in milestones:
            if row[0] not in phases:
                writer.writerow([now,*row]);added.append(row[0])
        handle.seek(0,2);handle.write(buffer.getvalue());handle.flush()
        fcntl.flock(handle,fcntl.LOCK_UN)
    print('Appended milestones: '+', '.join(added))


if __name__=='__main__':main()
