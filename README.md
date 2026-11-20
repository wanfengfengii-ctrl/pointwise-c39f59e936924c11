# 澄湾试验室停激复测台账

日班试验员登记实际停激工况。接线员冻结现场接法。质控员先核对短窗，再签发所选观测口的余振报告。夜班按报告号取回当时的裁决和父件，用 `no_decay` 安排复测。

```sh
python3 -B check_project.py
python3 -B demo.py
```

使用 Python 3.11 标准库。控制台物化时提供 `check_project.py`，完整 `unittest` 回归放在 `tests` 包内。演示读取 `sample.json`，在单独的临时目录运行，并输出短窗、同一对站件的两种裁决、新修订及历史领取结果。

## 公开入口

| 入口 | 输入及结果 |
| --- | --- |
| `trial.registry.register(store, trial, station, revision, model, initial_state, source)` | 按试验、站和正整数修订号追加登记，返回 `TrialRevision`。`source` 为留站原测出处。 |
| `station.freeze.freeze_station(revisions, evidence_store, trial, station, revision)` | 精确取得指定修订，返回带固定号的 `StationEvidence`。`station.issue.export_station(evidence_store, evidence_id)` 按号返回 V1 JSON 文本。 |
| `wiring.freeze.freeze_wiring(registry, left_ports, right_ports, left_to_right, right_to_left)` | 返回固定 `WiringRevision`。先用 `registry.register_ports(evidence.ports)` 登记两站完整口组。`registry.get_fixed(wiring_id)` 领取冻结接线。两个增益参数均必填。 |
| `analysis.replay.preview(first, second, wiring, observation, ticks)` | 接收站件对象或 V1 JSON 文本、固定接线对象、`PublicPort` 和非负整数拍数，返回有序 `ReplaySample` 元组。零拍数仍核验父件与观测口。 |
| `report.issue.issue_report(archive, first, second, wiring, observation)` | 返回 `(ReportRecord, IssueReceipt)`。沿接线方向配对站件，调用者可以交换两个站件参数的顺序。 |
| `report.readback.read_report(archive, report_id)` | 按正整数报告号返回归档时的 `(ReportRecord, IssueReceipt)`。查无该号时返回 `None`。 |

`RevisionStore`、`EvidenceStore`、`WiringRegistry` 和 `ReportArchive` 接收调用者提供的 `sqlite3.Connection`。在连接空闲时调用各自的 `initialize()`，并在写入时由存储对象管理事务。可将试验和站件放在一座站库，将接线和报告放在中心库。重复初始化保留现有数据。冻结后可以关闭站库，仅凭交换件在中心签发。试验更正使用新的修订号，原修订、原站件和原报告可按原号继续领取。

## 拍序与数值

模型字典由 `ports`、`transition`、`input_vector`、`return_vector`、`return_feedthrough`、`observation_vector`、`observation_feedthrough` 组成。`ports` 依次是入线、回线、观测的短名，完整身份由 `PublicPort(station, purpose, name)` 表示，`purpose` 分别为 `input`、`return`、`observation`。两站可使用同样的短名。裁决可直接用所选站件的 `ports[2]` 指定观测口。输入系数接受整数、`Fraction` 或带正分母的整数分式文本，如 `-3/2`，解析时拒绝浮点数、布尔值、空值和零分母。

设本站第 t 拍状态为 x，已有入量为 u。该拍读取两个公开输出 `C*x + D*u`，并按 `A*x + B*u` 推进本站状态。两站本拍回线出量分别乘其方向的冻结增益，作为对站下一拍的入量。输入及输出使用归一化读数，增益为无量纲倍率，每拍为一个离散采样间隔。零拍使用登记的实际状态且两个入量均为零。无状态直通使用空矩阵与空向量。短窗按同一拍序给出精确 `Fraction` 值。离线裁决使用指定口实际序列的有效递推，严格按开单位圆内的根判断趋零。零序列和有限尾段报 `decay`，持续常量、持续振荡及增长报 `no_decay`。

V1 JSON 以 `version`、`evidence_id`、`trial`、`station`、`revision`、`ports`、`response` 作为外层字段。`response` 中的状态坐标按位置编号，有理数按规范分式文本输出。原测出处只在本地修订记录中保存。站件号由其固定内容确定，接线号由两端完整口组和两向增益、延迟确定。重复冻结相同内容得到同号，修订身份或配置变化产生不同固定号。

形状、数值、重复修订和身份错配用 `ValueError` 拒绝。指定试验修订、已登记口组或导出站件查无记录时用 `KeyError` 拒绝。合法请求产生的报告与成功回执在同一 SQLite 事务提交。数据库写入或提交异常传播给调用者，本次报告和回执一并回滚。领取通过报告号联读归档正文和该号的原成功回执。

演示中的甲站每拍将状态翻倍，发回当前状态，观测口从当前状态中扣除四倍入量。乙站为回线直通。正常回线两拍返回后持续精确抵消，甲站前四拍为 `1, 2, 0, 0`。断开乙到甲后前四拍为 `1, 2, 4, 8`，仍需复测。回归还覆盖有符号分向增益、零拍核验、回流新激发的增长、单位模振荡及提交失败后的按号核账。
