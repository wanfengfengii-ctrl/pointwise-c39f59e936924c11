from report.archive import IssueReceipt, ReportArchive, ReportRecord


def read_report(archive: ReportArchive, report_id: int) -> tuple[ReportRecord, IssueReceipt] | None:
    return archive.get(report_id)
