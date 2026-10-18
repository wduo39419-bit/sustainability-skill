"""Portable read-only CFD progress dashboard; no research data or solver calls."""
from __future__ import annotations

import argparse
from datetime import datetime
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit


NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
TIME = re.compile(r'^Time\s*=\s*(' + NUMBER + r')\s*$', re.M)
RESIDUAL = re.compile(r'Solving for\s+(\w+),\s*Initial residual\s*=\s*(' + NUMBER + r'),\s*Final residual\s*=\s*(' + NUMBER + r'),\s*No Iterations\s+(\d+)')
CONTINUITY = re.compile(r'time step continuity errors\s*:\s*sum local\s*=\s*(' + NUMBER + r'),\s*global\s*=\s*(' + NUMBER + r'),\s*cumulative\s*=\s*(' + NUMBER + r')')
MAX_TAIL_BYTES = 256 * 1024


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def number(value):
    if finite(value):
        return value
    try:
        result = float(value)
        return result if math.isfinite(result) and not isinstance(value, bool) else None
    except (ValueError, TypeError):
        return None


def esc(value):
    return html.escape(str(value), quote=True)


def fmt(value, digits=3):
    return f'{value:.{digits}f}' if finite(value) else '—'


def percentage(value):
    return fmt(value * 100, 2) + '%' if finite(value) else '—'


def first(data, *keys):
    return next((data[key] for key in keys if key in data and data[key] is not None), None)


def read_state(path):
    if path is None:
        return {}, None, None
    for _ in range(3):
        try:
            state = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(state, dict):
                return {}, None, '状态文件顶层需要是 JSON 对象。'
            return state, path.stat().st_mtime, None
        except (OSError, ValueError):
            time.sleep(.02)
    return {}, None, '暂时无法读取状态文件，请检查文件是否存在、JSON 格式及写入是否完成。'


def read_log(path):
    if path is None:
        return '', None, None
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            offset = max(0, stream.tell() - MAX_TAIL_BYTES)
            stream.seek(offset)
            content = stream.read().decode('utf-8', errors='replace')
            if offset:
                content = content.partition('\n')[2]
        return content, path.stat().st_mtime, None
    except OSError:
        return '', None, '暂时无法读取求解日志，请检查路径、权限及日志是否已经生成。'


def parse_log(text):
    coordinates = [float(value) for value in TIME.findall(text)]
    markers = list(TIME.finditer(text))
    # The final Time block can be partial. Keep preceding values explicitly
    # marked with their own coordinate instead of presenting them as current.
    residuals = {}
    for match in RESIDUAL.finditer(text):
        preceding = [m for m in markers if m.start() < match.start()]
        residuals[match[1]] = {'initial': float(match[2]), 'final': float(match[3]), 'linear_iterations': int(match[4]), 'coordinate': float(preceding[-1][1]) if preceding else None}
    continuity = list(CONTINUITY.finditer(text))
    last = continuity[-1] if continuity else None
    before = [m for m in markers if last and m.start() < last.start()]
    return {
        'coordinate': coordinates[-1] if coordinates else None,
        'residuals': residuals,
        'continuity': {'local': float(last[1]), 'global': float(last[2]), 'cumulative': float(last[3]), 'coordinate': float(before[-1][1]) if before else None} if last else None,
        'ended': bool(re.search(r'^End\s*$', text, re.M)),
        'fatal_marker': bool(re.search(r'FOAM FATAL|Floating point exception|Segmentation fault', text, re.I)),
    }


def normalize_rows(state, limit):
    source = first(state, 'snapshots', 'rows', 'history') or []
    rows = []
    if not isinstance(source, list):
        return rows
    for row in source:
        if not isinstance(row, dict):
            continue
        coordinate = number(first(row, 'iteration', 'coordinate', 'time'))
        if coordinate is None:
            continue
        areas = first(row, 'areas_m2', 'exceedance_area_m2') or {}
        gap = number(row.get('momentum_gap_relative'))
        if gap is None and number(row.get('momentum_gap_percent')) is not None:
            gap = number(row['momentum_gap_percent']) / 100
        rows.append({
            'iteration': coordinate,
            'tau95_Pa': number(row.get('tau95_Pa')),
            'taumax_Pa': number(first(row, 'taumax_Pa', 'tau_max_Pa')),
            'areas_m2': {str(key): number(value) for key, value in areas.items()} if isinstance(areas, dict) else {},
            'source_force_N': number(first(row, 'source_force_N', 'force_N')),
            'momentum_gap_relative': gap,
            'Umax_m_s': number(first(row, 'Umax_m_s', 'max_velocity_m_s')),
        })
    unique = {row['iteration']: row for row in rows}
    return [unique[key] for key in sorted(unique)][-limit:]


def relative_change(left, right):
    if not finite(left) or not finite(right):
        return None
    scale = max(abs(left), abs(right))
    return abs(right - left) / scale if scale else 0.0


def demo_state():
    # Entirely invented examples: not copied or scaled from any research result.
    return {
        'status': 'DEMO', 'current_case': 'demo-case', 'current_action': '静态接口演示',
        'start_iteration': 0, 'max_end_iteration': 1000,
        'snapshots': [
            {'iteration': step, 'tau95_Pa': .08 + index * .007, 'taumax_Pa': .16 + index * .009,
             'areas_m2': {'0.2': index * .35, '0.4': 0.0}, 'source_force_N': 100.0,
             'momentum_gap_relative': .08 / (index + 1), 'Umax_m_s': .5 + index * .02}
            for index, step in enumerate([100, 200, 300, 400])
        ],
        'acceptance': {'local_stability': '演示：未判定', 'momentum': '演示：未判定', 'residuals': '演示：未判定', 'overall': '虚构数据，不作验收'},
        'conditions': [{'name': 'demo-case', 'status': '虚构演示', 'description': '未运行求解器'}],
    }


def snapshot(config):
    state, state_time, state_error = read_state(config.get('status_path'))
    log, log_time, log_error = read_log(config.get('log_path'))
    parsed = parse_log(log)
    if config.get('demo'):
        state, state_time, state_error = demo_state(), None, None
        parsed = parse_log('Time = 400\nsmoothSolver: Solving for Ux, Initial residual = 0.002, Final residual = 1e-08, No Iterations 3\n')
    rows = normalize_rows(state, config['max_points'])
    latest = rows[-1]['iteration'] if rows else None
    current = parsed['coordinate'] if parsed['coordinate'] is not None else latest
    start = config.get('start')
    if start is None:
        start = number(state.get('start_iteration')) or 0
    budget = config.get('budget')
    if budget is None:
        budget = number(first(state, 'max_end_iteration', 'end_iteration'))
    progress = 100 * (current - start) / (budget - start) if finite(current) and finite(budget) and budget > start else None
    age = max(0, time.time() - log_time) if log_time is not None else None
    state_age = max(0, time.time() - state_time) if state_time is not None else None
    warnings = [message for message in [state_error, log_error] if message]
    if age is not None and age > config['stale_seconds']:
        warnings.append('日志长时间未更新；可能处于暂停、计算结束或较长单步，需结合求解器状态判断。')
    if parsed['fatal_marker']:
        warnings.append('日志尾部包含求解器异常标记，请检查原始日志。')
    if finite(latest) and finite(parsed['coordinate']) and latest > parsed['coordinate']:
        warnings.append('诊断记录的进度晚于日志，可能读取了不同运行的文件；进度以日志标记显示。')
    if config.get('demo'):
        warnings.insert(0, '虚构演示数据 · 未连接任何真实算例 · 未启动 CFD。')
    elif not config.get('status_path'):
        warnings.append('只读取日志。剪切、面积、力与动量审计需要额外状态文件。')
    acceptance = state.get('acceptance', {})
    conditions = state.get('conditions', [])
    return {
        'title': config['title'], 'demo': config.get('demo', False), 'status': str(state.get('status', '未提供外部运行状态')),
        'case': str(state.get('current_case', '未指定')), 'phase': str(state.get('current_action', '只读监测')),
        'current': current, 'latest': latest, 'start': start, 'budget': budget,
        'budget_used_percent': progress, 'rows': rows, 'log': parsed,
        'log_age_seconds': age, 'status_age_seconds': state_age, 'warnings': warnings,
        'acceptance': {key: str(acceptance.get(key, '未提供')) for key in ['local_stability', 'momentum', 'residuals', 'overall']} if isinstance(acceptance, dict) else {},
        'conditions': [{'name': str(item.get('name', '未命名')), 'status': str(item.get('status', '未提供')), 'description': str(item.get('description', ''))} for item in conditions if isinstance(item, dict)] if isinstance(conditions, list) else [],
        'coordinate_label': config['coordinate_label'],
        'updated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
    }


def chart(title, series, units, coordinate_label, references=()):
    points = [(x, y) for _, _, data in series for x, y in data if finite(x) and finite(y)]
    if not points:
        return f'<section><h2>{esc(title)}</h2><p class="muted">等待诊断数据</p></section>'
    xmin, xmax = min(x for x, _ in points), max(x for x, _ in points)
    if xmax == xmin:
        xmax = xmin + 1
    ymax = max([y for _, y in points] + [y for _, y in references] + [0])
    ymin = min([y for _, y in points] + [y for _, y in references] + [0])
    span = ymax - ymin or 1
    ymax += .12 * span
    X = lambda x: 66 + (x - xmin) / (xmax - xmin) * 504
    Y = lambda y: 185 - (y - ymin) / (ymax - ymin) * 167
    content = [f'<svg viewBox="0 0 600 225" role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>']
    for index in range(4):
        value = ymin + (ymax - ymin) * index / 3
        content.append(f'<line x1="66" y1="{Y(value):.2f}" x2="570" y2="{Y(value):.2f}" class="gridline"/><text x="57" y="{Y(value)+4:.2f}" text-anchor="end">{fmt(value,2)}</text>')
        x = xmin + (xmax - xmin) * index / 3
        content.append(f'<text x="{X(x):.2f}" y="205" text-anchor="middle">{x:g}</text>')
    content.append(f'<text x="66" y="12">{esc(units)}</text>')
    for label, value in references:
        content.append(f'<line x1="66" y1="{Y(value):.2f}" x2="570" y2="{Y(value):.2f}" class="limit"/><text x="567" y="{Y(value)-4:.2f}" text-anchor="end">{esc(label)}</text>')
    for label, key, data in series:
        clean = [(x, y) for x, y in data if finite(x) and finite(y)]
        coords = ' '.join(f'{X(x):.2f},{Y(y):.2f}' for x, y in clean)
        content.append(f'<polyline points="{coords}" class="series {key}"/>')
        for x, y in clean:
            content.append(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="3" class="dot {key}"><title>{esc(label)} · {x:g} · {fmt(y)} {esc(units)}</title></circle>')
    content.append('</svg>')
    legend = ' '.join(f'<span class="legend"><span class="swatch {key}"></span>{esc(label)}</span>' for label, key, _ in series)
    return f'<section><h2>{esc(title)}</h2><div class="legendrow">{legend}</div>{"".join(content)}<small>{esc(coordinate_label)}</small></section>'


STYLE = '''
:root{color-scheme:light;--bg:#f5f7fa;--fg:#162032;--panel:#fff;--muted:#546277;--border:#dce3ec;--one:#1a61b9;--two:#ba5b09;--three:#268044}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 system-ui,'Microsoft YaHei',sans-serif}
main{max-width:1100px;margin:auto;padding:22px}h1{font-size:22px;margin:0 0 5px;font-weight:600}h2{font-size:16px;margin:0 0 8px}p{margin:6px 0}.muted,small{color:var(--muted)}.heading{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.status{font-size:17px;font-weight:600;margin-top:20px}.summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:16px 0}.summary>div{background:var(--panel);border-radius:8px;padding:14px}.value{font-size:23px;font-variant-numeric:tabular-nums;margin-top:5px}.track{height:12px;background:var(--border);border-radius:6px;overflow:hidden;margin:8px 0}.fill{height:100%;background:var(--one)}.two{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:22px}section{min-width:0}svg{width:100%;height:auto}svg text{fill:var(--fg);font:12px system-ui,sans-serif}.gridline{stroke:var(--border);stroke-width:1}.limit{stroke:var(--muted);stroke-dasharray:4 3;stroke-width:1}.series{fill:none;stroke-width:2}.series.s1{stroke:var(--one)}.series.s2{stroke:var(--two)}.series.s3{stroke:var(--three)}.dot.s1{fill:var(--one)}.dot.s2{fill:var(--two)}.dot.s3{fill:var(--three)}.legendrow{display:flex;gap:15px;flex-wrap:wrap}.legend{display:inline-flex;align-items:center;gap:6px}.swatch{width:16px;height:3px;display:inline-block}.swatch.s1{background:var(--one)}.swatch.s2{background:var(--two)}.swatch.s3{background:var(--three)}.conditions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}.condition{padding:10px;border-left:3px solid var(--border)}.condition strong,.condition span,.condition small{display:block}.tablewrap{overflow-x:auto;margin-top:12px}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--border);white-space:nowrap}th{font-weight:600}.notice{margin:18px 0;padding:12px;background:var(--panel);border-radius:8px}.demo{border-left:4px solid var(--two)}a{color:var(--one)}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#10151c;--fg:#e4eaf3;--panel:#19222e;--muted:#b1bed0;--border:#344356;--one:#6eaaf3;--two:#ffb06d;--three:#72ce94}}
@media(max-width:700px){main{padding:14px}.two,.summary{grid-template-columns:1fr}.conditions{grid-template-columns:repeat(2,minmax(0,1fr))}}
'''


def render(data, config):
    rows = data['rows']
    latest = rows[-1] if rows else {}
    shear = chart('床面剪切指标', [(label, f's{index+1}', [(r['iteration'], r.get(key)) for r in rows]) for index, (label, key) in enumerate([('τ95', 'tau95_Pa'), ('τmax', 'taumax_Pa')])], 'Pa', data['coordinate_label'])
    thresholds = sorted({key for row in rows for key in row['areas_m2']}, key=lambda key: (number(key) is None, number(key) or 0, key))
    area = chart('超阈值面积', [(f'>{key} Pa', f's{index%3+1}', [(r['iteration'], r['areas_m2'].get(key)) for r in rows]) for index, key in enumerate(thresholds)], 'm²', data['coordinate_label'])
    reference = config.get('momentum_reference_percent')
    references = [(f'用户参考线 {reference:g}%', reference)] if finite(reference) else []
    momentum = chart('动量缺口', [('相对缺口', 's1', [(r['iteration'], r['momentum_gap_relative'] * 100 if finite(r['momentum_gap_relative']) else None) for r in rows])], '%', data['coordinate_label'], references)
    changes = []
    for left, right in zip(rows, rows[1:]):
        cells = []
        for key in thresholds:
            a, b = left['areas_m2'].get(key), right['areas_m2'].get(key)
            cells.append(f'{esc(key)}: {fmt(b-a)}' if finite(a) and finite(b) else f'{esc(key)}: —')
        a, b = left['source_force_N'], right['source_force_N']
        changes.append(f'<tr><td>{left["iteration"]:g} → {right["iteration"]:g}</td><td>{percentage(relative_change(left["tau95_Pa"],right["tau95_Pa"]))}</td><td>{percentage(relative_change(left["taumax_Pa"],right["taumax_Pa"]))}</td><td>{" / ".join(cells) or "—"}</td><td>{fmt(b-a) if finite(a) and finite(b) else "—"}</td><td>{percentage(right["momentum_gap_relative"])}</td></tr>')
    residual_rows = ''.join(f'<tr><td>{esc(key)}</td><td>{fmt(value["coordinate"],3)}</td><td>{value["initial"]:.3g}</td><td>{value["final"]:.3g}</td><td>{value["linear_iterations"]}</td></tr>' for key, value in data['log']['residuals'].items())
    warnings = ''.join(f'<p>{esc(value)}</p>' for value in data['warnings'])
    acceptance = ''.join(f'<p>{label}：{esc(data["acceptance"].get(key,"未提供"))}</p>' for label, key in [('局部稳定','local_stability'),('动量审计','momentum'),('残差审查','residuals'),('综合验收','overall')])
    conditions = ''.join(f'<div class="condition"><strong>{esc(row["name"])}</strong><span>{esc(row["status"])}</span><small>{esc(row["description"])}</small></div>' for row in data['conditions']) or '<p class="muted">未提供工况队列。</p>'
    budget = f'{data["budget"]:g}' if finite(data['budget']) else '未设置'
    progress = data['budget_used_percent']
    bar = f'<div class="track" role="progressbar" aria-label="运行预算使用，不表示收敛" aria-valuenow="{max(0,min(100,progress)):.1f}" aria-valuemin="0" aria-valuemax="100"><div class="fill" style="width:{max(0,min(100,progress)):.1f}%"></div></div>' if finite(progress) else ''
    continuity = data['log']['continuity']
    mass = f'<p>连续性（标记 {fmt(continuity["coordinate"])}）：local {continuity["local"]:.3g} / global {continuity["global"]:.3g} / cumulative {continuity["cumulative"]:.3g}</p>' if continuity else '<p>连续性：未读取到</p>'
    ended = '<p>日志包含 End 结束标记；不代表验收通过。</p>' if data['log']['ended'] else ''
    title = esc(data['title'])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="{config['refresh']}"><title>{title}</title><style>{STYLE}</style></head><body><main>
<div class="heading"><div><h1>{title}</h1><p class="muted">只读 · 每 {config['refresh']} 秒刷新 · 无互联网依赖</p></div><div class="muted">更新时间 {esc(data['updated_at'])}<br>日志更新：{fmt(data['log_age_seconds'],0)} 秒前<br>诊断更新：{fmt(data['status_age_seconds'],0)} 秒前</div></div>
<p class="status">{esc(data['case'])} · {esc(data['status'])}</p><p>{esc(data['phase'])}</p>{ended}
<div class="summary"><div><span>日志最近进度标记</span><div class="value">{fmt(data['current'])} / {budget}</div><small>{esc(data['coordinate_label'])}</small></div><div><span>最近完成诊断</span><div class="value">{fmt(data['latest'])}</div><small>由外部后处理提供</small></div><div><span>运行预算使用</span><div class="value">{fmt(progress,1)}{'%' if finite(progress) else ''}</div><small>预算使用比例不代表收敛程度</small></div></div>{bar}
<div class="notice {'demo' if data['demo'] else ''}">{warnings or '<p>运行状态与验收结论分别显示。</p>'}</div>
<div class="two">{shear}{area}{momentum}<section><h2>最新诊断与验收</h2><p>源区力积分：{fmt(latest.get('source_force_N'))} N</p><p>最大速度：{fmt(latest.get('Umax_m_s'))} m/s</p>{mass}{acceptance}<small>看板展示外部判断，不自动定义稳定、停止或验收条件。</small></section></div>
<h2 style="margin-top:24px">阶段变化记录</h2><div class="tablewrap"><table><thead><tr><th>阶段</th><th>τ95变化</th><th>τmax变化</th><th>阈值: Δ面积（m²）</th><th>Δ力（N）</th><th>动量缺口</th></tr></thead><tbody>{''.join(changes) or '<tr><td colspan="6">等待两个有效诊断阶段</td></tr>'}</tbody></table></div><p class="muted">变化率使用绝对差除以相邻阶段较大绝对值；两者均零时变化为零，缺值保留为空。</p>
<h2 style="margin-top:24px">最近方程残差</h2><div class="tablewrap"><table><thead><tr><th>方程</th><th>对应进度标记</th><th>初始残差</th><th>最终线性残差</th><th>线性迭代数</th></tr></thead><tbody>{residual_rows or '<tr><td colspan="5">等待日志残差</td></tr>'}</tbody></table></div><p class="muted">最终线性残差不能单独代表非线性收敛；部分日志末步未写完时保留各方程所属标记。</p>
<h2 style="margin-top:24px">工况队列</h2><div class="conditions">{conditions}</div><p class="muted">只读查看，不启动、暂停或修改计算。超阈值面积的物理意义由使用者定义。</p></main></body></html>'''


def handler_for(config):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlsplit(self.path).path
            if route not in ('/', '/index.html', '/api/status', '/health'):
                self.send_error(404)
                return
            if route == '/health':
                payload, content_type = b'{"ok":true,"read_only":true}', 'application/json; charset=utf-8'
            else:
                try:
                    data = snapshot(config)
                    payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8') if route == '/api/status' else render(data, config).encode('utf-8')
                    content_type = 'application/json; charset=utf-8' if route == '/api/status' else 'text/html; charset=utf-8'
                except Exception:
                    self.send_error(503, 'Progress input temporarily unavailable')
                    return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass
    return Handler


def load_config(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--status', dest='status_file')
    parser.add_argument('--log')
    parser.add_argument('--port', type=int)
    parser.add_argument('--budget', type=float)
    parser.add_argument('--start', type=float)
    parser.add_argument('--refresh', type=int)
    parser.add_argument('--title')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    settings = {'title': 'CFD 实时进度', 'port': 0, 'refresh': 6, 'stale_seconds': 300, 'max_points': 60, 'coordinate_label': '求解进度标记（以日志 Time 字段为准）'}
    base = Path.cwd()
    if args.config:
        try:
            config_file = args.config.resolve()
            loaded = json.loads(config_file.read_text(encoding='utf-8-sig'))
            if not isinstance(loaded, dict):
                parser.error('配置文件需要是 JSON 对象')
            settings.update(loaded)
            base = config_file.parent
        except (OSError, ValueError):
            parser.error('无法读取配置文件；请检查文件路径和 JSON 格式')
    for key in ['status_file', 'log', 'port', 'budget', 'start', 'refresh', 'title']:
        value = getattr(args, key)
        if value is not None:
            settings[key] = value
    settings['demo'], settings['check'] = args.demo, args.check
    for key in ['port', 'refresh', 'max_points', 'stale_seconds']:
        value = settings.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            parser.error(f'{key} 必须为整数')
    if not 0 <= settings['port'] <= 65535 or not 1 <= settings['refresh'] <= 3600 or not 2 <= settings['max_points'] <= 500 or settings['stale_seconds'] < 1:
        parser.error('端口、刷新间隔、历史点数或日志时效设置超出范围')
    for key in ['budget', 'start', 'momentum_reference_percent']:
        if settings.get(key) is not None and not finite(settings[key]):
            parser.error(f'{key} 必须为有限数值')
    for key in ['title', 'coordinate_label']:
        if not isinstance(settings[key], str):
            parser.error(f'{key} 必须为文字')
    if args.demo and (args.log or args.status_file or args.config):
        parser.error('--demo 与实际文件参数分开使用')
    # Explicit CLI input paths are relative to the invocation directory, while
    # configured paths are relative to the configuration file.
    for key, target in [('log', 'log_path'), ('status_file', 'status_path')]:
        value = settings.get(key)
        path_base = Path.cwd() if getattr(args, key) is not None else base
        settings[target] = (path_base / value).resolve() if value else None
    if not args.demo and not settings['log_path'] and not settings['status_path']:
        parser.error('请指定 --log、--status、--config 或 --demo')
    return settings


def main(argv=None):
    config = load_config(argv)
    if config['check']:
        data = snapshot(config)
        print(json.dumps({'demo': data['demo'], 'diagnostic_points': len(data['rows']), 'log_coordinate': data['log']['coordinate'], 'warnings': data['warnings']}, ensure_ascii=False, allow_nan=False))
        return 1 if data['warnings'] and not data['demo'] else 0
    server = ThreadingHTTPServer(('127.0.0.1', config['port']), handler_for(config))
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/', 'read_only': True, 'demo': config['demo']}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
