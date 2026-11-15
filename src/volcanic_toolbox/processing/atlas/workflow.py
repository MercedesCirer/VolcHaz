"""High-level ERA5 download, conversion and ATLAS concatenation workflow."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import timedelta
import logging
from pathlib import Path

import pandas as pd

from .atlas_netcdf import (
    AtlasChunk,
    AtlasConversionError,
    concatenate_chunks,
    final_atlas_filename,
    inspect_atlas_file,
)
from .config import AtlasERA5DownloadConfig
from .meteorology_downloader import (
    DownloadError,
    DownloadJob,
    build_jobs,
    build_scenario_phase_manifest,
    detect_phase_names,
    download_job,
    read_scenario_table,
    validate_area,
    write_coverage_summary,
    write_download_plan,
    write_request_preview,
)


@dataclass
class AtlasERA5Preparation:
    phase_names: list[str]
    manifest: pd.DataFrame
    jobs: list[DownloadJob]
    download_plan: pd.DataFrame
    coverage_summary: pd.DataFrame
    manifest_path: Path
    request_preview_path: Path
    download_plan_path: Path
    coverage_summary_path: Path

    @property
    def unique_initial_dates(self) -> int:
        return int(self.manifest["initial_date"].nunique())

    @property
    def unique_phase_dates(self) -> int:
        return int(
            self.manifest[
                ["phase", "initial_date"]
            ].drop_duplicates().shape[0]
        )

    @property
    def total_file_requests(self) -> int:
        return int(len(self.download_plan))


def prepare_atlas_era5_downloads(
    config: AtlasERA5DownloadConfig,
) -> AtlasERA5Preparation:
    table = read_scenario_table(config.scenario_table)
    phases = detect_phase_names(table, config.phase_names)
    manifest = build_scenario_phase_manifest(
        table,
        phases,
        accepted_only=config.accepted_only,
    )

    output = Path(config.output_directory)
    era5_directory = output / "era5"
    manifest_directory = output / "manifests"

    era5_directory.mkdir(parents=True, exist_ok=True)
    manifest_directory.mkdir(parents=True, exist_ok=True)

    manifest_path = (
        manifest_directory
        / "atlas_scenario_phase_manifest.csv"
    )
    manifest.to_csv(manifest_path, index=False)

    jobs = build_jobs(
        manifest,
        validate_area(config.area),
        era5_directory,
        config.days_after,
    )

    request_preview_path = write_request_preview(
        jobs,
        manifest_directory,
    )
    download_plan_path, download_plan = write_download_plan(
        jobs,
        manifest_directory,
    )
    coverage_summary_path, coverage_summary = write_coverage_summary(
        manifest,
        jobs,
        download_plan,
        manifest_directory,
    )

    if len(download_plan) != 2 * len(jobs):
        raise RuntimeError(
            "Incomplete request plan: each monthly job must contain one "
            "pressure and one single-level request."
        )

    return AtlasERA5Preparation(
        phase_names=phases,
        manifest=manifest,
        jobs=jobs,
        download_plan=download_plan,
        coverage_summary=coverage_summary,
        manifest_path=manifest_path,
        request_preview_path=request_preview_path,
        download_plan_path=download_plan_path,
        coverage_summary_path=coverage_summary_path,
    )


def _group_jobs(
    jobs: list[DownloadJob],
) -> dict[tuple[str, object], list[DownloadJob]]:
    grouped: dict[tuple[str, object], list[DownloadJob]] = {}

    for job in jobs:
        key = (job.phase, job.initial_date.date())
        grouped.setdefault(key, []).append(job)

    for key in grouped:
        grouped[key].sort(key=lambda item: item.group.start)

    return grouped


def _job_netcdf_paths(job: DownloadJob) -> tuple[Path, Path]:
    pressure = (
        job.target_folder
        / f"pressure_{job.group.label}.nc"
    )
    single = (
        job.target_folder
        / f"single_{job.group.label}.nc"
    )
    return pressure, single


def _process_phase_date(
    jobs: list[DownloadJob],
    config: AtlasERA5DownloadConfig,
) -> list[str]:
    """Resume one complete phase-date branch."""
    if not jobs:
        return []

    first = jobs[0]
    initial_date = first.initial_date.date()
    expected_total_hours = (config.days_after + 1) * 24
    final_path = (
        first.target_folder
        / final_atlas_filename(initial_date)
    )

    final_status = inspect_atlas_file(
        final_path,
        expected_hours=expected_total_hours,
        initial_date=initial_date,
    )

    # A complete final ATLAS file is authoritative. Do not redownload chunks.
    if final_status.complete and not config.overwrite:
        return [f"SKIP COMPLETE PHASE-DATE {final_path}"]

    messages: list[str] = []
    chunks: list[AtlasChunk] = []

    for job in jobs:
        # download_job already implements:
        # - skip valid NetCDF
        # - reuse/download GRIB
        # - convert GRIB to NetCDF
        messages.extend(
            download_job(
                job,
                overwrite=config.overwrite,
                keep_grib=config.keep_grib,
                executable=config.grib_to_netcdf_executable,
                data_type=config.netcdf_data_type,
                kind=config.netcdf_kind,
                compression_level=config.netcdf_compression_level,
            )
        )

        pressure_path, single_path = _job_netcdf_paths(job)
        chunks.append(
            AtlasChunk(
                pressure_path=pressure_path,
                single_path=single_path,
                start=job.group.start.date(),
                end_exclusive=(
                    job.group.end.date()
                    + timedelta(days=1)
                ),
            )
        )

    messages.extend(
        concatenate_chunks(
            chunks,
            output_path=final_path,
            event_initial_date=initial_date,
            expected_total_hours=expected_total_hours,
            overwrite_invalid=config.overwrite,
        )
    )

    return messages


def execute_atlas_era5_downloads(
    preparation: AtlasERA5Preparation,
    config: AtlasERA5DownloadConfig,
) -> None:
    """Download, convert, concatenate and resume every phase-date branch."""
    if config.dry_run:
        return

    grouped = _group_jobs(preparation.jobs)
    failures: list[str] = []

    failed_log = (
        Path(config.output_directory)
        / "manifests"
        / "failed_downloads_or_concatenations.txt"
    )

    with ThreadPoolExecutor(
        max_workers=config.max_workers,
    ) as executor:
        futures = {
            executor.submit(
                _process_phase_date,
                jobs,
                config,
            ): key
            for key, jobs in grouped.items()
        }

        total = len(futures)

        for completed, future in enumerate(
            as_completed(futures),
            start=1,
        ):
            phase, initial_date = futures[future]

            try:
                for message in future.result():
                    logging.info(
                        "[%d/%d] %s",
                        completed,
                        total,
                        message,
                    )
            except Exception as error:
                description = (
                    f"{phase} | {initial_date} | "
                    f"{type(error).__name__}: {error}"
                )
                failures.append(description)
                logging.error(
                    "[%d/%d] FAILED %s",
                    completed,
                    total,
                    description,
                )

    if failures:
        failed_log.parent.mkdir(parents=True, exist_ok=True)
        failed_log.write_text(
            "\n\n".join(failures) + "\n",
            encoding="utf-8",
        )
        raise DownloadError(
            f"{len(failures)} phase-date branches failed. "
            f"See {failed_log}"
        )

    failed_log.unlink(missing_ok=True)
