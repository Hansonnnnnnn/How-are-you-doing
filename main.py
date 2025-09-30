import csv
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

IS_FROZEN = getattr(sys, "frozen", False)

def get_project_root() -> Path:
    # 在 PyInstaller(onefile) 下，资源位于临时解包目录 sys._MEIPASS
    if IS_FROZEN and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

PROJECT_ROOT = get_project_root()
EXE_DIR = Path(sys.executable).parent if IS_FROZEN else PROJECT_ROOT
DATA_DIR = (EXE_DIR if IS_FROZEN else PROJECT_ROOT) / "data"
CSV_PATH = DATA_DIR / "mood_log.csv"
# 同时兼容 messages.json 与 message.json 两种命名
CANDIDATE_MESSAGE_PATHS = [
    PROJECT_ROOT / "messages.json",
    PROJECT_ROOT / "message.json",
    EXE_DIR / "messages.json",   # 打包后放在 exe 同目录也可被读取
    EXE_DIR / "message.json",
]

def ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            # 升级后的表头：增加 note 列用于小型日记
            writer.writerow(["date", "score", "message", "note"])  # 表头
    else:
        upgrade_csv_schema()

def load_messages() -> Dict[str, List[str]]:
    # 内置默认文案，防止缺失文件导致崩溃
    defaults: Dict[str, List[str]] = {
        "low": [
            "再难也会过去的，你已经很棒了。",
            "今天先照顾好自己，一步一步来。",
        ],
        "mid": [
            "保持节奏，稳步向前，就是胜利。",
            "不错的状态，给自己点掌声。",
        ],
        "high": [
            "状态绝佳，继续发光！",
            "保持这股劲儿，去创造更多好事。",
        ],
    }

    try:
        actual_path: Optional[Path] = next((p for p in CANDIDATE_MESSAGE_PATHS if p.exists()), None)
        if actual_path is None:
            print("未找到 messages.json，使用内置默认文案。")
            return defaults
        with actual_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "low": list(map(str, data.get("low", defaults["low"]))),
            "mid": list(map(str, data.get("mid", defaults["mid"]))),
            "high": list(map(str, data.get("high", defaults["high"]))),
        }
    except Exception:
        print("读取 messages.json 失败，已使用默认文案。")
        return defaults

def upgrade_csv_schema():
    """将旧版三列表头(date, score, message)升级为四列，追加 note 列。"""
    try:
        with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            rows = list(reader)
    except FileNotFoundError:
        return
    except Exception:
        # 无法读取时跳过升级，避免破坏现有数据
        return

    # 空文件或仅有数据无表头的情况，一并标准化
    if header is None:
        with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "score", "message", "note"])
            for r in rows:
                if len(r) == 3:
                    writer.writerow([r[0], r[1], r[2], ""])  # 旧行补空 note
                else:
                    writer.writerow(r)
        return

    if len(header) == 3:
        with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "score", "message", "note"])  # 新表头
            for r in rows:
                if len(r) == 3:
                    writer.writerow([r[0], r[1], r[2], ""])  # 旧行补空 note
                else:
                    writer.writerow(r)

def ask_for_score() -> int:
    while True:
        raw = input("今天你感觉如何？请为自己打分（1-10）：").strip()
        try:
            score = int(raw)
            if 1 <= score <= 10:
                return score
            print("请输入 1-10 之间的整数。")
        except ValueError:
            print("请输入有效整数。")

def choose_message(
    score: int,
    messages: Dict[str, List[str]],
    exclude: Optional[str] = None,
    excludes: Optional[Set[str]] = None,
) -> str:
    if score <= 4:
        pool = messages.get("low") or ["再难也会过去的，你已经很棒了。"]
    elif score <= 7:
        pool = messages.get("mid") or ["保持节奏，稳步向前，就是胜利。"]
    else:
        pool = messages.get("high") or ["状态绝佳，继续发光！"]
    # 组合排除集合：上一句 + 最近N天已使用
    exclude_set: Set[str] = set()
    if exclude is not None:
        exclude_set.add(exclude)
    if excludes:
        exclude_set.update(excludes)
    candidates = [m for m in pool if m not in exclude_set]
    if candidates:
        return random.choice(candidates)
    # 候选为空时回退原池，避免阻塞（极端情况下）
    return random.choice(pool)

def read_existing_for_date(target_date: str) -> List[List[str]]:
    if not CSV_PATH.exists():
        return []
    rows = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        _ = next(reader, None)
        for r in reader:
            if len(r) >= 1 and r[0] == target_date:
                rows.append(r)
    return rows

def append_record(day: str, score: int, message: str, note: str):
    with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([day, score, message, note])

# === 统计与可视化 ===

def read_recent_messages(last_days: int = 30) -> Set[str]:
    """读取最近 last_days 天内已使用的寄语集合。"""
    used: Set[str] = set()
    if not CSV_PATH.exists():
        return used
    today = date.today()
    cutoff = today - timedelta(days=last_days - 1)
    try:
        with CSV_PATH.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            _ = next(reader, None)
            for r in reader:
                if len(r) >= 3:
                    day_str = str(r[0]).strip()
                    try:
                        d = date.fromisoformat(day_str)
                    except Exception:
                        continue
                    if cutoff <= d <= today:
                        used.add(str(r[2]))
    except Exception:
        return used
    return used

def read_all_records() -> List[Tuple[str, int]]:
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

def aggregate_daily_average(records: List[Tuple[str, int]]) -> Dict[str, float]:
    # 多条同日记录 → 取均值
    sums: Dict[str, int] = {}
    counts: Dict[str, int] = {}
    for d, s in records:
        sums[d] = sums.get(d, 0) + s
        counts[d] = counts.get(d, 0) + 1
    return {d: sums[d] / counts[d] for d in sums}

def last_n_dates(n: int) -> List[str]:
    today = date.today()
    days = [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
    return [d.isoformat() for d in days]

def to_sparkline(values: List[Optional[float]]) -> str:
    # 将 1-10 映射到 ▁▂▃▄▅▆▇█，缺失为 ·
    blocks = "▁▂▃▄▅▆▇█"
    out_chars: List[str] = []
    for v in values:
        if v is None:
            out_chars.append("·")
        else:
            # clamp 到 [1,10]
            v = max(1.0, min(10.0, float(v)))
            # 线性映射到 0..7
            idx = int(round((v - 1.0) / 9.0 * (len(blocks) - 1)))
            idx = max(0, min(len(blocks) - 1, idx))
            out_chars.append(blocks[idx])
    return "".join(out_chars)

def show_recent_stats(k: int = 7):
    records = read_all_records()
    if not records:
        print("\n暂无历史数据用于统计。")
        return
    daily_avg = aggregate_daily_average(records)
    days = last_n_dates(k)
    aligned_values: List[Optional[float]] = [daily_avg.get(d) for d in days]

    spark = to_sparkline(aligned_values)
    available = [v for v in aligned_values if v is not None]

    # 优先使用 Rich 表格展示；若缺失则回退到纯文本
    try:
        from rich.console import Console  # type: ignore
        from rich.table import Table  # type: ignore

        console = Console()
        table = Table(title="最近7天统计")
        table.add_column("日期", justify="center")
        table.add_column("均值", justify="right")
        table.add_column("迷你柱", justify="left")

        for d, v in zip(days, aligned_values):
            if v is None:
                mean_text = "-"
                bar = ""
            else:
                mean_text = f"{v:.2f}"
                length = max(1, min(10, int(round(float(v)))))
                bar = "█" * length
            table.add_row(d[-5:], mean_text, bar)

        console.print(table)
        if available:
            avg = sum(available) / len(available)
            mn = min(available)
            mx = max(available)
            console.print(f"可用天数: {len(available)}/{k} | 均值: {avg:.2f} | 最低: {mn:.2f} | 最高: {mx:.2f}")
        else:
            console.print("最近7天没有可用记录。")
    except Exception:
        print("\n—— 最近7天统计 ——")
        print(f"曲线: {spark}")
        print("日期: " + " ".join(d[-5:] for d in days))
        if available:
            avg = sum(available) / len(available)
            mn = min(available)
            mx = max(available)
            print(f"可用天数: {len(available)}/{k} | 均值: {avg:.2f} | 最低: {mn:.2f} | 最高: {mx:.2f}")
        else:
            print("最近7天没有可用记录。")

def main():
    # 延迟导入，避免编辑器静态分析路径导致的解析告警
    try:
        from data_manager import render_trend  # type: ignore
    except Exception:
        render_trend = None  # 运行时若找不到会按未安装处理

    print("=== How are you doing from 1–10 ===")
    ensure_storage()
    messages = load_messages()

    while True:
        today_str = date.today().isoformat()
        existing = read_existing_for_date(today_str)
        if existing:
            print(f"提示：今天({today_str})已记录 {len(existing)} 次。")

        raw = input("最近怎么样？输入 1-10 记录，V 可视化，D 看日记，N 退出：").strip()
        key = raw.lower()

        if key in ("n", "no", "否"):
            print("已退出，祝你有个美好的一天！")
            return

        if key == "v":
            try:
                from data_manager import render_trend, render_ascii_bar, export_png, export_html  # type: ignore
            except Exception:
                render_trend = None
                render_ascii_bar = None
                export_png = None
                export_html = None
            print("\n可视化选项：")
            print("1) ASCII 迷你曲线（最近30天）")
            print("2) ASCII 柱状图（最近30天）")
            print("3) 导出 PNG（最近30天）")
            print("4) 导出 HTML（最近30天）")
            print("5) 自定义天数的 ASCII 迷你曲线")
            sub = input("请选择 [1-5]（其它键返回）：").strip()
            if sub == "1" and render_trend is not None:
                render_trend(30)
            elif sub == "2" and render_ascii_bar is not None:
                render_ascii_bar(30)
            elif sub == "3" and export_png is not None:
                export_png(30)
            elif sub == "4" and export_html is not None:
                export_html(30)
            elif sub == "5" and render_trend is not None:
                raw_n = input("输入统计天数（默认30）：").strip()
                try:
                    n = int(raw_n) if raw_n else 30
                except Exception:
                    n = 30
                n = max(7, min(180, n))
                render_trend(n)
            else:
                print("已返回主菜单。")
            continue

        if key == "d":
            try:
                from data_manager import render_diary  # type: ignore
            except Exception:
                render_diary = None
            if render_diary is not None:
                raw_k = input("显示最近多少条日记？（默认10）：").strip()
                try:
                    k = int(raw_k) if raw_k else 10
                except Exception:
                    k = 10
                k = max(1, min(100, k))
                render_diary(k)
            else:
                print("暂不支持日记浏览。")
            continue

        # 尝试解析为分数
        try:
            score = int(raw)
        except Exception:
            print("未识别的输入，请输入 1-10 / V / D / N。")
            continue
        if not (1 <= score <= 10):
            print("请输入 1-10 之间的整数。")
            continue

        used_recent = read_recent_messages(30)
        msg = choose_message(score, messages, excludes=used_recent)
        print("\n—— 今日寄语 ——")
        print(msg)
        swap = input("\n是否换一句？（Y 换一句 / 任意键继续）：").strip().lower()
        if swap in ("y", "yes", "是"):
            new_msg = choose_message(score, messages, exclude=msg, excludes=used_recent)
            if new_msg != msg:
                msg = new_msg
                print("\n—— 今日寄语（已更换）——")
                print(msg)
            else:
                print("\n没有可替换的句子，保持不变。")
        note = input("\n有什么要记下的吗？直接输入（留空则跳过）：").strip()
        append_record(today_str, score, msg, note)
        print("\n记录完成，已写入 CSV。")
        # 记录后回显一条迷你趋势，提升反馈感
        show_recent_stats(7)

if __name__ == "__main__":
    main()