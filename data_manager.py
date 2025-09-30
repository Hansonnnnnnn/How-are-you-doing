import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
CSV_PATH = DATA_DIR / "mood_log.csv"


def _read_all_records() -> List[Tuple[str, int]]:
    if not CSV_PATH.exists():
        return []
    out: List[Tuple[str, int]] = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        _ = next(reader, None)
        for r in reader:
            if len(r) >= 2:
                day = str(r[0]).strip()
                try:
                    score = int(r[1])
                except Exception:
                    continue
                out.append((day, score))
    return out


def _aggregate_daily_average(records: List[Tuple[str, int]]) -> Dict[str, float]:
    sums: Dict[str, int] = {}
    counts: Dict[str, int] = {}
    for d, s in records:
        sums[d] = sums.get(d, 0) + s
        counts[d] = counts.get(d, 0) + 1
    return {d: sums[d] / counts[d] for d in sums}


def _last_n_dates(n: int) -> List[str]:
    today = date.today()
    days = [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
    return [d.isoformat() for d in days]


def _to_sparkline(values: List[Optional[float]]) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    out_chars: List[str] = []
    for v in values:
        if v is None:
            out_chars.append("·")
        else:
            v = max(1.0, min(10.0, float(v)))
            idx = int(round((v - 1.0) / 9.0 * (len(blocks) - 1)))
            idx = max(0, min(len(blocks) - 1, idx))
            out_chars.append(blocks[idx])
    return "".join(out_chars)


def render_trend(last_days: int = 30) -> None:
    """读取 CSV 并打印最近 N 天的心情趋势与统计。"""
    days, aligned_values = _read_aligned_series(last_days)
    if not days:
        print("\n暂无历史数据用于统计。")
        return

    spark = _to_sparkline(aligned_values)
    available = [v for v in aligned_values if v is not None]
    print(f"\n=== 最近{last_days}天心情趋势 ===")
    print(f"曲线: {spark}")
    print("日期: " + " ".join(d[-5:] for d in days))
    if available:
        avg = sum(available) / len(available)
        mn = min(available)
        mx = max(available)
        print(f"可用天数: {len(available)}/{last_days} | 均值: {avg:.2f} | 最低: {mn:.2f} | 最高: {mx:.2f}")
    else:
        print("选定范围内没有可用记录。")


def _read_aligned_series(last_days: int) -> Tuple[List[str], List[Optional[float]]]:
    records = _read_all_records()
    if not records:
        return [], []
    daily_avg = _aggregate_daily_average(records)
    days = _last_n_dates(last_days)
    aligned_values: List[Optional[float]] = [daily_avg.get(d) for d in days]
    return days, aligned_values


def render_ascii_bar(last_days: int = 30) -> None:
    """以 ASCII 柱状图渲染最近 N 天的均值（1-10）。"""
    days, values = _read_aligned_series(last_days)
    if not days:
        print("\n暂无历史数据用于统计。")
        return
    print(f"\n=== 最近{last_days}天心情柱状图 ===")
    for d, v in zip(days, values):
        label = d[-5:]
        if v is None:
            bar = "(无)"
        else:
            # 将 1..10 映射到 1..10 个块
            length = max(1, min(10, int(round(float(v)))))
            bar = "█" * length
        print(f"{label} | {bar}")


def export_png(last_days: int = 30, out_path: Optional[str] = None) -> Optional[str]:
    """导出最近 N 天趋势为 PNG。需要 matplotlib。返回输出路径或 None。"""
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        print("未安装 matplotlib，无法导出 PNG。请先安装：pip install matplotlib")
        return None

    days, values = _read_aligned_series(last_days)
    if not days:
        print("暂无历史数据用于导出。")
        return None

    y = [float(v) if v is not None else None for v in values]
    x = list(range(len(days)))

    fig, ax = plt.subplots(figsize=(max(6, last_days * 0.2), 3))
    ax.plot(x, y, marker="o")
    ax.set_ylim(1, 10)
    ax.set_ylabel("score")
    ax.set_title(f"Mood Trend (last {last_days} days)")
    # 仅显示稀疏刻度，避免过密
    step = max(1, last_days // 10)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([d[-5:] for d in days][::step], rotation=45, ha="right")
    fig.tight_layout()

    if out_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_file = DATA_DIR / f"trend_last{last_days}.png"
    else:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(out_file, dpi=150)
    plt.close(fig)
    print(f"PNG 已导出: {out_file}")
    return str(out_file)


def export_html(last_days: int = 30, out_path: Optional[str] = None) -> Optional[str]:
    """导出最近 N 天趋势为交互式 HTML。需要 plotly。返回输出路径或 None。"""
    try:
        import plotly.graph_objects as go  # type: ignore
    except Exception:
        print("未安装 plotly，无法导出 HTML。请先安装：pip install plotly")
        return None

    days, values = _read_aligned_series(last_days)
    if not days:
        print("暂无历史数据用于导出。")
        return None

    y = [float(v) if v is not None else None for v in values]
    x = [d[-5:] for d in days]

    fig = go.Figure(data=[go.Scatter(x=x, y=y, mode="lines+markers")])
    fig.update_layout(
        title=f"Mood Trend (last {last_days} days)",
        yaxis=dict(range=[1, 10], title="score"),
        xaxis=dict(title="date"),
        margin=dict(l=40, r=20, t=40, b=40),
    )

    if out_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_file = DATA_DIR / f"trend_last{last_days}.html"
    else:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

    fig.write_html(out_file, include_plotlyjs="cdn")
    print(f"HTML 已导出: {out_file}")
    return str(out_file)


def render_diary(last_k: int = 10) -> None:
    """显示最近 K 条包含日记(note 非空)的记录。"""
    if not CSV_PATH.exists():
        print("暂无日记记录。")
        return
    rows: List[List[str]] = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        _ = next(reader, None)
        for r in reader:
            rows.append(r)
    # 过滤 note 非空
    diary_rows = [r for r in rows if len(r) >= 4 and str(r[3]).strip()]
    if not diary_rows:
        print("暂无日记记录。")
        return
    print(f"\n=== 最近{min(last_k, len(diary_rows))}条日记 ===")
    for r in diary_rows[-last_k:]:
        day = r[0]
        score = r[1] if len(r) > 1 else ""
        note = r[3]
        print(f"{day} (score {score})\n- {note}\n")


