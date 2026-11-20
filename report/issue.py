from analysis.closed_loop import build_closed_loop
from analysis.decay import decide_decay
from analysis.observation import resolve_observation
from report.archive import IssueReceipt, ReportArchive, ReportRecord
from report.provenance import bind_parents
from report.request import normalize_request
from station.envelope import PublicPort, StationEvidence
from wiring.registry import WiringRevision


def issue_report(
    archive: ReportArchive,
    first: StationEvidence | str,
    second: StationEvidence | str,
    wiring: WiringRevision,
    observation: PublicPort,
) -> tuple[ReportRecord, IssueReceipt]:
    request = normalize_request(first, second, wiring, observation)
    loop = build_closed_loop(request.first, request.second, request.wiring)
    observed = resolve_observation(loop, request.observation)
    parents = bind_parents(loop, observed)
    verdict = decide_decay(loop, observed)
    return archive.publish(parents, verdict)
