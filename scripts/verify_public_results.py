#!/usr/bin/env python3
"""Validate public X5 uplift aggregate results and optional packaged Tableau Story."""
import csv
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'tableau'/'data'

def read(filename):
    with (DATA/filename).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

kpis=read('09_test_targeting_kpis.csv')
diffs=read('09_test_strategy_differences_bootstrap.csv')
qini=read('09_test_qini_summary.csv')
segments=read('10_customer_insights_segments.csv')
d04_diff=read('13_strategy_difference_ci.csv')
d04_qini=read('13_qini_area_summary.csv')
exploratory=read('06_segment_uplift_summary.csv')
assert len(kpis)==15 and len(diffs)==3 and len(qini)==3
assert len(segments)==5 and len(exploratory)==5
assert len(d04_diff)==3 and len(d04_qini)==3
assert all('comparison_ko' in r for r in d04_diff)
assert len({(r['strategy'],r['top_fraction']) for r in kpis})==15
for r in kpis:
    n=Decimal(r['selected_customers'])
    observed=Decimal(r['sms_cvr_pct'])-Decimal(r['control_cvr_pct'])
    assert abs(observed-Decimal(r['uplift_pp']))<Decimal('0.00000002')
    assert abs(n*Decimal(r['uplift_pp'])/100-Decimal(r['estimated_extra_conversions']))<Decimal('0.00001')
by20={r['strategy']:r for r in kpis if Decimal(r['top_fraction'])==Decimal('0.20')}
assert len(by20)==3
for r in diffs:
    a=Decimal(by20[r['strategy_A']]['uplift_pp'])
    b=Decimal(by20[r['strategy_B']]['uplift_pp'])
    assert abs(a-b-Decimal(r['uplift_diff_A_minus_B_pp']))<Decimal('0.00000002')
    assert int(r['bootstrap_iterations'])==600

workbook=ROOT/'tableau'/'workbook'/'Who_Should_We_Persuade_public.twbx'
if workbook.is_file():
    with zipfile.ZipFile(workbook) as z:
        assert z.testzip() is None
        twb=next(n for n in z.namelist() if n.endswith('.twb'))
        raw=z.read(twb)
        assert b'C:/Users/' not in raw and b'client_id' not in raw
        root=ET.fromstring(raw)
        story=[x for x in root.findall('.//dashboard') if x.get('type')=='storyboard']
        assert len(story)==1 and len(story[0].findall('.//story-point'))==4
        assert story[0].find('size').get('maxheight')=='900'
        assert story[0].find('size').get('maxwidth')=='1200'
        assert len([n for n in z.namelist() if n.endswith('.hyper')])==4

print('PASS: 7 aggregate CSVs, 15 KPI rows, 3 bootstrap comparisons, 3 Qini rows, Tableau Story validation')
