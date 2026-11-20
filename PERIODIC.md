# 周期切档台架的停激复核

澄湾试验室用 `decay` 和 `no_decay` 区分可交班工况和待复测工况。周期切档台架的零拍相位属于该次实际停激工况。同一组阶段以不同相位起步，接通时的判定可能相反。本页补充 [README.md](README.md) 的公开接口。

## 登记、冻结和导出

- `trial.registry.register(store, trial, station, revision, model, initial_state, source)` 接受周期模型字典 `{"ports": [...], "stages": [...], "phase": 0}`。`ports` 沿用 V1 的名称、身份和顺序，依次为入线、回线、观测。`stages` 是长度为 1～3 的有序列表或元组。每个阶段采用 V1 模型除 `ports` 外的六个系数字段。有理写法、矩阵及向量规则沿用 V1。所有阶段用同一状态坐标，维度一致且为 0～3。`initial_state` 是该坐标下的实际初态，`phase` 是零拍使用的阶段下标，取非布尔整数 `0 <= phase < len(stages)`。原测出处 `source` 仅保存在站库。更正使用新修订号。
- `station.freeze.freeze_station(revisions, evidence_store, trial, station, revision)` 按确切修订返回固定站件。周期修订即使只有一个阶段也生成 V2 件。站件提供 `evidence_id`、`trial`、`station`、`revision` 和完整 `ports`，可用于原有的口组登记和固定接线。
- `station.issue.export_station(evidence_store, evidence_id)` 按号返回 JSON 文本。V2 使用 V1 的外层字段，`version` 为整数 `2`。V2 `response` 的字段为 `initial_state`、`stages` 和 `phase`。输出的阶段顺序、初态及相位与冻结修订一致，系数和初态按 V1 口径输出规范分式文本。固定件号沿用 V1 对规范正文定号的规则，正文包含版本、身份、完整口组和整个响应。重冻同一内容沿用原号。更正后旧件仍可按原号导出。`station.codec.decode_evidence` 可读这两种版别，版本须匹配正文，身份或正文与固定号不符即拒绝。

## 中心短窗和签发

`analysis.replay.preview(first, second, wiring, observation, ticks)` 和 `report.issue.issue_report(archive, first, second, wiring, observation)` 沿用现有签名。每份站件可传冻结对象或其导出文本。中心核验实际站件内容，V2 双件须同试验、异站且完整口组与固定接线两端相符。传入顺序可以对调，读取和归档按接线方向配对。`observation` 是目标站件的完整观测口身份，如 `PublicPort('B', 'observation', 'meter')`。两件须同版。零拍数仍核验选件、接线和观测口。

各站在公共第 `t` 拍使用本件的阶段 `(phase + t) % len(stages)`。零拍以各自冻结初态和零入量开始。每拍以该拍开始时的状态与已到达入量，按本站当前阶段计算回线及观测输出，并更新状态。两站的回线量乘各自方向的冻结增益，分别成为对站下一拍的入量。状态和在途量都跨阶段及周期边界连续承接。零增益表示该方向断开。

短窗返回按拍号从零开始的 `ReplaySample` 元组，读数是精确 `Fraction`。正式报告核定所选口的实际全拍极限。趋零签 `decay`，其余签 `no_decay`。短窗长度不限制裁决所考虑的后续拍。报告沿用 `(ReportRecord, IssueReceipt)`，记录实际采用的双件和试验修订、接线、观测口及裁决，与成功回执同次提交。`report.readback.read_report(archive, report_id)` 在更正和重开后按号领取原存值。

非法阶段或相位、坏件、混版及父件错配报 `ValueError`。查无指定修订或导出号报 `KeyError`。合法的未知报告号返回 `None`。写入或提交错误传播，失败不留下本次报告或回执，解除故障后可重试。保留 V1 原入口、原站件字节、旧报告和全部原回归。

## 样例与运行

[periodic-sample.json](periodic-sample.json) 的每个 `case` 以 `trial` 和 `left`、`right` 对应登记入参。`right_correction` 如有，取乙站原登记，把 `revision`、`source` 和 `model.phase` 换成其中给出的值，其他输入沿用。`gains` 依次为甲到乙、乙到甲。`observation` 可直接拆为 `PublicPort` 的三个参数。`checks` 固定乙站修订，各项 `values` 为所需短窗的期望分式文本，长度给出拍数。

`CW-phase-01` 中甲站偶数拍发一个单位，乙站原相位恰在奇数拍读到。更正只变更乙站的起始相位，读数转为恒零。`CW-phase-02` 中甲乙周期为 2 和 3，所选口的前六拍全零，但第 6、12 拍都有一个单位读数，因此仍须复测。将原 `sample.json` 的两站模型各包装为一期周期模型、相位置零，可对照原接通和断线的读数与裁决。

沿用 `.pointwise-runtime.json` 的现有运行方式。`python3 -B check_project.py` 运行原回归及补充的周期业务核验，错误须以非零状态退出。`python3 -B demo.py` 展示原样例，以及周期样例在站库关闭后签发、换相更正后签出不同结果、重开中心库按报告号领取原裁决和回执。补充核验应覆盖异周期跨界、错配或坏件、提交失败及重试。提交失败可沿用 `tests/test_report.py` 中延迟外键触发器的夹具方式核对报告和回执。
