## How are you doing from 1–10

- 每天运行一次，输入 1-10 的心情分数，程序会显示一条对应寄语并记录到 `data/mood_log.csv`。

### 运行
- Python 3.9+
- 可选：创建虚拟环境
- 运行：
```bash
python main.py
```

### 主菜单（启动后提示）
- 提示：`最近怎么样？输入 1-10 记录，V 可视化，D 看日记，N 退出：`
  - `1-10`：记录一次，随后可输入一段日记（写入 `note` 列）
  - `V`：进入可视化子菜单（ASCII 曲线/柱状、导出 PNG/HTML、自定义天数）
  - `D`：查看最近若干条含日记的记录
  - `N`：退出

### 可视化依赖（可选）
- PNG 导出：`pip install matplotlib`
- HTML 导出：`pip install plotly`
- 控制台表格（Rich）：`pip install rich`

说明：已安装 Rich 时，“最近7天统计”会以表格形式显示；未安装则回退为纯文本输出。