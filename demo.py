import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.replay import preview
from report.archive import ReportArchive
from report.issue import issue_report
from report.readback import read_report
from station.freeze import freeze_station
from station.issue import export_station
from station.store import EvidenceStore
from trial.registry import register
from trial.revisions import RevisionStore
from wiring.freeze import freeze_wiring
from wiring.registry import WiringRegistry


def _freeze(connection, trial, entry):
    revisions = RevisionStore(connection)
    evidence = EvidenceStore(connection)
    revisions.initialize()
    evidence.initialize()
    register(
        revisions, trial, entry['station'], entry['revision'], entry['model'],
        entry['initial_state'], entry['source'],
    )
    frozen = freeze_station(revisions, evidence, trial, entry['station'], entry['revision'])
    return frozen, export_station(evidence, frozen.evidence_id)


def _scenario(case_id, case_input, expected, actual, downstream_expected, downstream_actual, code_paths, oracle):
    if actual != expected or downstream_actual != downstream_expected:
        raise AssertionError(f'{case_id}: {actual!r} / {downstream_actual!r}')
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id,
        'input': case_input,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': code_paths,
        'oracle': oracle,
    }, ensure_ascii=False, sort_keys=True))


def _handoff_value(issued):
    report, receipt = issued
    return {
        'report': report.report_id,
        'receipt': asdict(receipt),
        'verdict': report.verdict.value,
        'parents': asdict(report.parents),
    }


def main():
    sample = json.loads(Path(__file__).with_name('sample.json').read_text(encoding='utf-8'))
    with TemporaryDirectory(prefix='chengwan-demo-') as temp:
        source_path = Path(temp) / 'station.sqlite'
        archive_path = Path(temp) / 'center.sqlite'
        with closing(sqlite3.connect(archive_path)) as center:
            registry = WiringRegistry(center)
            archive = ReportArchive(center)
            registry.initialize()
            archive.initialize()
            with closing(sqlite3.connect(source_path)) as source:
                left, exported_left = _freeze(source, sample['trial'], sample['left'])
                right, exported_right = _freeze(source, sample['trial'], sample['right'])
                registry.register_ports(left.ports)
                registry.register_ports(right.ports)
                connected = freeze_wiring(registry, left.ports, right.ports, *sample['connected'])
                disconnected = freeze_wiring(registry, left.ports, right.ports, *sample['disconnected'])
                observation = left.ports[2]
                for case_id, wiring, gains, numbers in (
                    ('v4', connected, sample['connected'], ('1', '2', '0', '0')),
                    ('v5', disconnected, sample['disconnected'], ('1', '2', '4', '8')),
                ):
                    ticks = sample['preview_ticks']
                    readings = preview(exported_left, exported_right, wiring, observation, ticks)
                    _scenario(
                        case_id,
                        {'left_initial': sample['left']['initial_state'], 'gains': gains, 'ticks': ticks},
                        list(numbers), [str(reading.value) for reading in readings],
                        list(range(ticks)), [reading.tick for reading in readings],
                        ['station/response.py', 'analysis/closed_loop.py', 'analysis/replay.py'],
                        '甲状态为 2 的逐拍幂，乙直通，往返恰好两拍，断线则回流为零。',
                    )
            archived = [
                issue_report(archive, exported_left, exported_right, registry.get_fixed(wiring.wiring_id), observation)
                for wiring in (connected, disconnected)
            ]
            expected_parents = [
                [left.evidence_id, right.evidence_id, wiring.wiring_id, asdict(observation)]
                for wiring in (connected, disconnected)
            ]
            actual_parents = [
                [record.parents.left.evidence_id, record.parents.right.evidence_id,
                 record.parents.wiring_id, asdict(record.parents.observation)]
                for record, _ in archived
            ]
            _scenario(
                'v6', {'fixed_parents': expected_parents},
                ['decay', 'no_decay'], [record.verdict.value for record, _ in archived],
                expected_parents, actual_parents,
                ['analysis/decay.py', 'report/issue.py', 'report/provenance.py', 'report/archive.py'],
                '接通时第三拍起恰为零，断线时甲状态继续翻倍。',
            )
            corrected = {**sample['left'], 'revision': 2, 'initial_state': ['0'], 'source': '日班复核更正 A-010'}
            with closing(sqlite3.connect(source_path)) as reopened:
                new_left, exported_new = _freeze(reopened, sample['trial'], corrected)
            new_issue = issue_report(archive, exported_new, exported_right, disconnected, observation)
        with closing(sqlite3.connect(archive_path)) as reopened:
            archive = ReportArchive(reopened)
            archive.initialize()
            old_issued = archived[1]
            old_read = read_report(archive, old_issued[0].report_id)
            _scenario(
                'v7',
                {'old_report': old_issued[0].report_id, 'new_report': new_issue[0].report_id, 'new_initial': ['0']},
                ['decay', new_left.evidence_id, 2],
                [new_issue[0].verdict.value, new_issue[0].parents.left.evidence_id,
                 new_issue[0].parents.left.revision],
                _handoff_value(old_issued), _handoff_value(old_read),
                ['station/freeze.py', 'report/issue.py', 'report/archive.py', 'report/readback.py'],
                '零初态在断线下始终为零。旧号的正文与回执须与首次签发时保存的值一致。',
            )


if __name__ == '__main__':
    main()
