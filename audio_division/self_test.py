from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from audio_division.archive_health_dashboard import ArchiveHealthReport, archive_health_report
from audio_division.closed_loop_monitor import discover_incoming_albums
from audio_division.dashboard import load_json
from audio_division.environment_health import (
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARNING,
    EnvironmentCheck,
    EnvironmentHealthReport,
    environment_health_report,
)
from audio_division.lifecycle_state import merge_lifecycle_rows
from audio_division.library import library_from_data_dir
from audio_division.physical_archive import build_archive_albums
from audio_division.pipeline_health import PipelineHealthReport, pipeline_health_report
from audio_division.settings import load_audio_division_settings
from curator.atomic import atomic_write_text


@dataclass(frozen=True)
class SelfTestResult:
    overall_status: str
    environment: EnvironmentHealthReport
    archive: ArchiveHealthReport
    pipeline: PipelineHealthReport
    failing_checks: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "environment": self.environment.to_dict(),
            "archive": self.archive.to_dict(),
            "pipeline": self.pipeline.to_dict(),
            "failing_checks": [dict(check) for check in self.failing_checks],
        }


class SelfTestRunner:
    def __init__(
        self,
        *,
        base_dir: Path,
        data_dir: Path | None = None,
        reports_dir: Path | None = None,
        settings: dict[str, Any] | None = None,
    ):
        self.base_dir = Path(base_dir)
        self.data_dir = Path(data_dir) if data_dir is not None else self.base_dir / "data"
        self.settings = settings or load_audio_division_settings(self.data_dir / "audio_division_settings.json")
        self.reports_dir = Path(reports_dir) if reports_dir is not None else self._reports_dir()

    def run(
        self,
        *,
        archive_albums: list[dict[str, Any]] | None = None,
        pipeline_releases: list[dict[str, Any]] | None = None,
    ) -> SelfTestResult:
        archive_rows = archive_albums if archive_albums is not None else self._archive_albums()
        pipeline_rows = pipeline_releases if pipeline_releases is not None else self._pipeline_rows(archive_rows)
        environment = environment_health_report(self.settings, base_dir=self.base_dir, data_dir=self.data_dir)
        archive = archive_health_report(archive_rows)
        pipeline = pipeline_health_report(pipeline_rows)
        failing = tuple(_failing_environment_checks(environment) + _metric_failures(archive, pipeline))
        overall = _overall_status(environment, archive, pipeline)
        return SelfTestResult(
            overall_status=overall,
            environment=environment,
            archive=archive,
            pipeline=pipeline,
            failing_checks=failing,
        )

    def write_reports(self, result: SelfTestResult) -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.reports_dir / "self_test.md", render_self_test_markdown(result))
        atomic_write_text(
            self.reports_dir / "self_test.json",
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def run_and_write(self) -> SelfTestResult:
        result = self.run()
        self.write_reports(result)
        return result

    def _reports_dir(self) -> Path:
        configured = str(self.settings.get("reports", {}).get("reports_directory") or "reports")
        path = Path(configured).expanduser()
        return path if path.is_absolute() else self.base_dir / path

    def _archive_albums(self) -> list[dict[str, Any]]:
        return build_archive_albums(
            load_json(self.data_dir / "archive_registry.json"),
            load_json(self.data_dir / "identity_registry.json"),
            load_json(self.data_dir / "metadata_cache.json"),
        )

    def _pipeline_rows(self, archive_albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
        archive_root = str(self.settings.get("archive_paths", {}).get("main_archive_root") or "")
        library = library_from_data_dir(self.data_dir, Path(archive_root) if archive_root else None)
        incoming = discover_incoming_albums(
            self.settings,
            archive_albums,
            load_json(self.data_dir / "processing_queue.json"),
        )
        return merge_lifecycle_rows(library.get("albums", []), archive_albums, incoming)


def render_self_test_markdown(result: SelfTestResult) -> str:
    archive = result.archive
    pipeline = result.pipeline
    lines = [
        "# STiGMA Self Test",
        "",
        f"- Overall Status: `{result.overall_status}`",
        f"- Environment: `{result.environment.status}`",
        f"- Archive: `{archive.status}`",
        "",
        "## Failing Checks",
        "",
        "| Area | Check | Status | Suggested Action |",
        "| --- | --- | --- | --- |",
    ]
    if not result.failing_checks:
        lines.append("| none |  |  |  |")
    for check in result.failing_checks:
        lines.append(
            f"| {_escape(check.get('area'))} | {_escape(check.get('name'))} | "
            f"{_escape(check.get('status'))} | {_escape(check.get('suggested_action'))} |"
        )

    lines.extend(
        [
            "",
            "## Environment Health",
            "",
            f"- PASS: `{result.environment.summary.get(STATUS_PASS, 0)}`",
            f"- WARNING: `{result.environment.summary.get(STATUS_WARNING, 0)}`",
            f"- FAIL: `{result.environment.summary.get(STATUS_FAIL, 0)}`",
            "",
            "## Archive Health",
            "",
            f"- Albums: `{archive.albums}`",
            f"- Healthy: `{archive.healthy}`",
            f"- Warnings: `{archive.warnings}`",
            f"- Errors: `{archive.errors}`",
            f"- Missing Artwork: `{archive.missing_artwork}`",
            f"- Missing NFO: `{archive.missing_nfo}`",
            f"- Missing Playlist: `{archive.missing_playlist}`",
            f"- Missing SFV: `{archive.missing_sfv}`",
            f"- Missing Validation: `{archive.missing_validation}`",
            f"- Metadata Coverage: `{archive.metadata_coverage}%`",
            f"- Identity Coverage: `{archive.identity_coverage}%`",
            f"- Duplicate Releases: `{archive.duplicate_releases}`",
            f"- Broken Layouts: `{archive.broken_layouts}`",
            f"- Unexpected Layouts: `{archive.unexpected_layouts}`",
            "",
            "## Pipeline Health",
            "",
            f"- Total Releases: `{pipeline.total_releases}`",
            f"- Discovered: `{pipeline.discovered}`",
            f"- Downloaded: `{pipeline.downloaded}`",
            f"- Validated: `{pipeline.validated}`",
            f"- Ready To Process: `{pipeline.ready_to_process}`",
            f"- Archived: `{pipeline.archived}`",
            f"- Needs Review: `{pipeline.needs_review}`",
            f"- Unknown: `{pipeline.unknown}`",
            f"- Stalled Downloads: `{pipeline.stalled_downloads}`",
            f"- Duplicate Downloads: `{pipeline.duplicate_downloads}`",
            f"- Validation Failures: `{pipeline.validation_failures}`",
            f"- Ready To Archive: `{pipeline.ready_to_archive}`",
            f"- Recently Archived: `{pipeline.recently_archived}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _overall_status(
    environment: EnvironmentHealthReport,
    archive: ArchiveHealthReport,
    pipeline: PipelineHealthReport,
) -> str:
    if environment.status == STATUS_FAIL or archive.errors or pipeline.validation_failures:
        return STATUS_FAIL
    if (
        environment.status == STATUS_WARNING
        or archive.warnings
        or pipeline.needs_review
        or pipeline.stalled_downloads
        or pipeline.duplicate_downloads
        or pipeline.unknown
    ):
        return STATUS_WARNING
    return STATUS_PASS


def _failing_environment_checks(report: EnvironmentHealthReport) -> list[dict[str, str]]:
    return [
        {
            "area": check.category or "Environment",
            "name": check.name,
            "status": check.status,
            "suggested_action": check.suggested_action,
            "evidence": check.evidence,
        }
        for check in report.checks
        if check.status == STATUS_FAIL
    ]


def _metric_failures(archive: ArchiveHealthReport, pipeline: PipelineHealthReport) -> list[dict[str, str]]:
    failures = []
    failures.extend(
        _metric_check("Archive", "Archive errors", archive.errors, "Review archive health errors before running archive operations.")
    )
    failures.extend(
        _metric_check("Archive", "Missing validation", archive.missing_validation, "Validate affected archive releases.")
    )
    failures.extend(
        _metric_check("Archive", "Broken layouts", archive.broken_layouts, "Review archive folder structure for affected releases.")
    )
    failures.extend(
        _metric_check("Pipeline", "Validation failures", pipeline.validation_failures, "Review validator logs and rerun validation after corrections.")
    )
    return failures


def _metric_check(area: str, name: str, count: int, suggested_action: str) -> list[dict[str, str]]:
    if count <= 0:
        return []
    return [
        {
            "area": area,
            "name": name,
            "status": STATUS_FAIL,
            "suggested_action": suggested_action,
            "evidence": str(count),
        }
    ]


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")
