# CFD 实时进度看板

将 OpenFOAM 求解日志和可选的诊断状态文件转为本地实时网页。沿用原看板的进度条、剪切曲线、超阈值面积、动量缺口、阶段变化和工况队列显示方式，并将项目路径与判断规则改为可配置输入。

**这里只发布通用看板代码和明确标注的虚构演示。不包含任何论文数据、真实算例、原始流场、采样坐标、科研图件或实际计算结果。**

## 直接运行

Python 3.10 或更新版本，无需安装第三方库。Windows、Linux、macOS 均可运行。

```sh
python progress_view.py --demo
```

浏览器打开终端打印的 `http://127.0.0.1:端口/`。演示页面持续显示“虚构演示”，不会启动求解器，也不会假装有正在运行的 CFD。

连接自己的日志：

```sh
python progress_view.py --log /path/to/case/log.simpleFoam --budget 1000
```

同时连接自己的后处理状态文件：

```sh
python progress_view.py --log /path/to/case/log.simpleFoam --status /path/to/status.json --budget 1000 --port 8765
```

配置文件方式：

```sh
python progress_view.py --config config.example.json
```

相对路径基于配置文件所在目录解析。命令行参数覆盖配置文件。`--refresh 6` 设置网页刷新秒数；`--check` 只核对输入，输出概要后退出。按 `Ctrl+C` 停止网页服务。

## 显示内容

- 日志中的最新 `Time = ...` 标记和最近完成诊断的进度。
- 配置的运行预算使用比例，明确区别于收敛百分比。
- 最近的压力、速度和湍流方程初始/最终线性残差与迭代数。
- 状态文件提供的 τ95、τmax、超阈值面积、推进源力和动量缺口。
- 相邻保存阶段的指标变化、明确提供的验收状态和工况队列。
- 输入读取失败、日志未更新、诊断与日志进度不一致的提示。

`Time` 在不同求解器中可能表示稳态迭代编号或瞬态物理时间。请通过 `coordinate_label` 设置合适的说明。程序只读实际标记，不推断物理秒或预计剩余时间。

## 状态文件接口

看板可以单独解析求解日志。剪切、面积、力积分及全域动量审计需要你的后处理程序写入状态文件；看板本身不会计算这些物理量。

```json
{
  "status": "RUNNING",
  "current_case": "case-name",
  "current_action": "求解 / 后处理",
  "start_iteration": 0,
  "max_end_iteration": 1000,
  "snapshots": [
    {
      "iteration": 100,
      "tau95_Pa": 0.12,
      "taumax_Pa": 0.18,
      "areas_m2": {"0.2": 0.0},
      "source_force_N": 100.0,
      "momentum_gap_relative": 0.03
    }
  ],
  "acceptance": {
    "local_stability": "由外部审计填写",
    "momentum": "由外部审计填写",
    "residuals": "由外部审计填写",
    "overall": "未判定"
  },
  "conditions": [
    {"name": "case-name", "status": "运行中", "description": "用户自定义说明"}
  ]
}
```

上面的数字仅说明字段类型，不来自科研结果。可兼容原看板常用的 `rows` / `snapshots`、`tau_max_Pa` / `taumax_Pa`、`force_N` / `source_force_N` 等字段。`momentum_gap_relative` 使用比例，0.03 显示为 3%；若使用 `momentum_gap_percent`，直接填写百分数。

缺失指标显示为“—”，不会补成零。阈值面积的键可自定义；建议在你的状态文件中统一使用一种字符串形式。局部稳定、残差、动量与综合验收分别显示；看板不会替用户制定或放宽验收标准。

状态文件应由计算流程原子更新，例如先写临时文件，再替换目标文件。若写入中途被读取，看板显示读取警告，刷新后重试。

## 配置与运行方式

`config.example.json` 包含可修改的路径、刷新间隔、预算与可选参考线。默认不设收敛或动量阈值；参考线只用于显示，不会停止计算或授予验收。

服务只绑定本机 `127.0.0.1`。仅开放 `/`、`/index.html`、`/api/status` 和 `/health`，不提供任意文件浏览或命令执行接口。HTTP 日志默认静默，不向网页返回本地绝对路径。日志和状态文件只读，不修改模型、不写回状态、不暂停或启动求解器。

如需跨机器查看，可自行通过 SSH 本地端口转发访问。不要将真实状态文件、日志或配置上传到仓库。此目录的 `.gitignore` 已忽略常见本地输入。

GitHub 用于分发代码；这个实时看板需要在能读取日志的电脑上运行，GitHub Pages 无法读取本地求解日志。

## 测试

```sh
python -m unittest discover -s tests -v
```

测试只使用程序生成的虚构文本，覆盖日志解析、状态兼容、缺失值、HTML 转义、文件只读、预算显示以及 HTTP 路由。

## 项目来源与使用许可

由科研计算中使用的只读实时进度看板整理而来，移除了研究项目路径、硬编码的场景设置与论文结果。源码仅依赖 Python 标准库；未打包 OpenFOAM 或其他第三方软件。

本仓库尚未声明开源许可证，代码公开不等于已授予特定开源许可。复用前请联系仓库维护者，或等待其补充许可证。
