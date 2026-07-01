#!/usr/bin/env python

import math
import re
import subprocess
from pathlib import Path
import logging
import numpy as np

logger = logging.getLogger(__name__)


def parse_metric(stdout_text: str, label: str):
    """Parse a metric value from FFCz stdout.

    Args:
        stdout_text: The stdout output from ffcz command
        label: The metric label to search for (e.g., "MAE", "PSNR")

    Returns:
        The parsed float value or None if not found
    """
    match = re.search(rf"^{re.escape(label)}:\s+([^\n]+)$", stdout_text, re.MULTILINE)
    if not match:
        return None
    token = match.group(1).strip().split()[0]
    try:
        return float(token)
    except ValueError:
        return None


def collect_ffcz_bytes(prefix: Path) -> int:
    """Collect total size of all FFCz correction files.

    Args:
        prefix: Path prefix for FFCz output files

    Returns:
        Total size in bytes of all correction files
    """
    total = 0
    for suffix in [".fedits", ".fflags", ".sedits", ".sflags", ".extreme"]:
        path = Path(f"{prefix}{suffix}")
        if path.exists():
            total += path.stat().st_size
    return total


def cleanup_ffcz_files(prefix: Path):
    """Remove FFCz correction files after reading their sizes.

    Args:
        prefix: Path prefix for FFCz output files
    """
    for suffix in [".fedits", ".fflags", ".sedits", ".sflags", ".extreme"]:
        path = Path(f"{prefix}{suffix}")
        if path.exists():
            try:
                path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete {path}: {e}")


def _build_dim_args(dims: tuple):
    dim_flag = f"-{len(dims)}"
    return [dim_flag, *[str(v) for v in dims]]



def _load_corrected_data(corrected_path: Path, dtype: str, dims: tuple, result: dict):
    if corrected_path.exists():
        print(f"[FFCz] corrected file exists: {corrected_path}")
        try:
            np_dtype = np.float32 if dtype == "float" else np.float64
            corrected_data = np.fromfile(corrected_path, dtype=np_dtype)
            expected_size = math.prod(dims)
            if corrected_data.size == expected_size:
                corrected_data = corrected_data.reshape(dims)
                result["corrected_data"] = corrected_data
                result["corrected_data_available"] = True
                logger.info(
                    f"Read corrected data: shape={corrected_data.shape}, dtype={corrected_data.dtype}"
                )
                print(f"[FFCz] loaded corrected data from: {corrected_path}")
            else:
                warning = (
                    f"Corrected data size mismatch: got {corrected_data.size}, expected {expected_size}"
                )
                result["corrected_data_warning"] = warning
                logger.warning(warning)

            corrected_path.unlink()
            print(f"[FFCz] removed corrected file: {corrected_path}")
        except Exception as e:
            warning = f"Failed to read corrected data from {corrected_path}: {e}"
            result["corrected_data_warning"] = warning
            logger.warning(warning)
    else:
        warning = f"Corrected data file not found: {corrected_path}"
        result["corrected_data_warning"] = warning
        logger.warning(warning)
        print(f"[FFCz] missing corrected file: {corrected_path}")



def _annotate_corrected_data(base_decomp_path: str, dtype: str, dims: tuple, result: dict):
    corrected_data = result.get("corrected_data")
    if corrected_data is None:
        return

    try:
        np_dtype = np.float32 if dtype == "float" else np.float64
        base_data = np.fromfile(base_decomp_path, dtype=np_dtype)
        expected_size = math.prod(dims)
        if base_data.size != expected_size:
            warning = (
                f"Base decompressed data size mismatch during corrected-data verification: "
                f"got {base_data.size}, expected {expected_size}"
            )
            result["corrected_data_warning"] = warning
            logger.warning(warning)
            return

        base_data = base_data.reshape(dims)
        max_abs_delta = float(np.max(np.abs(corrected_data - base_data))) if corrected_data.size else 0.0
        changed = not np.array_equal(corrected_data, base_data)
        result["corrected_data_changed"] = changed
        result["corrected_data_max_abs_delta"] = max_abs_delta

        if not changed:
            warning = (
                "FFCz produced no effective edits for this frequency bound; "
                "corrected data is identical to the base decompressed data."
            )
            result["corrected_data_warning"] = warning
            logger.info(warning)
            print("[FFCz] corrected data unchanged from base decompressed data")
        else:
            logger.info(f"FFCz corrected data differs from base decompressed data (max abs delta={max_abs_delta})")
            print(f"[FFCz] corrected data differs from base decompressed data (max abs delta={max_abs_delta})")
    except Exception as e:
        warning = f"Failed to compare corrected data against base decompressed data: {e}"
        result["corrected_data_warning"] = warning
        logger.warning(warning)


def _materialize_corrected_output(
    ffcz_bin: str,
    dtype: str,
    base_decomp_path: str,
    output_prefix: str,
    dims: tuple,
    spatial_mode: str,
    spatial_value: float,
    freq_mode: str,
    freq_value: float,
    corrected_output: str,
    result: dict,
):
    corrected_path = Path(corrected_output)
    print(f"[FFCz] corrected output path: {corrected_path}")
    logger.info(f"FFCz will materialize corrected data at: {corrected_path}")

    command = [
        ffcz_bin,
        "-f" if dtype == "float" else "-d",
        "-e", base_decomp_path,
        "-z", output_prefix,
        *(_build_dim_args(dims)),
        "-o", corrected_output,
        "-M", spatial_mode, str(spatial_value),
        "-F", freq_mode, str(freq_value),
    ]
    logger.info(f"Running FFCz decompression command: {' '.join(command)}")
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    result["corrected_stdout"] = completed.stdout
    result["corrected_stderr"] = completed.stderr
    if completed.returncode != 0:
        warning = (
            f"ffcz decompression failed with code {completed.returncode}; stderr: {completed.stderr.strip() or '(empty)'}"
        )
        result["corrected_data_warning"] = warning
        logger.warning(warning)
        return

    logger.info(f"FFCz decompression stdout for corrected output:\n{completed.stdout}")
    if completed.stderr:
        logger.warning(f"FFCz decompression stderr: {completed.stderr}")

    _load_corrected_data(corrected_path, dtype, dims, result)
    _annotate_corrected_data(base_decomp_path, dtype, dims, result)



def run_ffcz_once(
    ffcz_bin: str,
    dtype: str,
    original_path: str,
    base_decomp_path: str,
    output_prefix: str,
    dims: tuple,
    spatial_mode: str,
    spatial_value: float,
    freq_mode: str,
    freq_value: float,
    return_corrected_data: bool = False,
):
    """Run FFCz once with a single frequency bound.

    Args:
        ffcz_bin: Path to ffcz executable
        dtype: Data type ('float' or 'double')
        original_path: Path to original raw file
        base_decomp_path: Path to base decompressed file
        output_prefix: Prefix for output correction files
        dims: Tuple of dimensions (e.g., (512, 512, 50))
        spatial_mode: Spatial error mode ('REL' or 'ABS')
        spatial_value: Spatial error bound value
        freq_mode: Frequency error mode ('REL' or 'ABS')
        freq_value: Frequency error bound value
        return_corrected_data: Whether to generate and return corrected data

    Returns:
        Dictionary containing metrics and file sizes
    """
    corrected_output = f"{output_prefix}.corrected" if return_corrected_data else None

    command = [
        ffcz_bin,
        "-f" if dtype == "float" else "-d",
        "-i", original_path,
        "-e", base_decomp_path,
        "-z", output_prefix,
        *(_build_dim_args(dims)),
        "-M", spatial_mode, str(spatial_value),
        "-F", freq_mode, str(freq_value),
    ]

    logger.info(f"Running FFCz command: {' '.join(command)}")

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"ffcz failed with code {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )

    logger.info(f"FFCz stdout for freq_bound={freq_value}:\n{completed.stdout}")
    if completed.stderr:
        logger.warning(f"FFCz stderr: {completed.stderr}")

    prefix = Path(output_prefix)
    ffcz_bytes = collect_ffcz_bytes(prefix)
    logger.info(f"FFCz correction files total: {ffcz_bytes} bytes")

    result = {
        "freq_bound": freq_value,
        "ffcz_bytes": ffcz_bytes,
        "additional_storage": parse_metric(completed.stdout, "Additional storage"),
        "max_relative_frequency_error": parse_metric(completed.stdout, "max relative frequency error"),
        "mae": parse_metric(completed.stdout, "MAE"),
        "mse": parse_metric(completed.stdout, "MSE"),
        "rmse": parse_metric(completed.stdout, "RMSE"),
        "nrmse": parse_metric(completed.stdout, "NRMSE"),
        "psnr": parse_metric(completed.stdout, "PSNR") or parse_metric(completed.stdout, "PNSR"),
        "ssnr": parse_metric(completed.stdout, "SSNR"),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "corrected_data_requested": bool(return_corrected_data),
        "corrected_data_available": False,
        "corrected_data_changed": None,
    }

    if return_corrected_data and corrected_output:
        _materialize_corrected_output(
            ffcz_bin=ffcz_bin,
            dtype=dtype,
            base_decomp_path=base_decomp_path,
            output_prefix=output_prefix,
            dims=dims,
            spatial_mode=spatial_mode,
            spatial_value=spatial_value,
            freq_mode=freq_mode,
            freq_value=freq_value,
            corrected_output=corrected_output,
            result=result,
        )

    return result


def sweep_ffcz_frequency_bounds(
    ffcz_bin: str,
    original_path: str,
    base_decomp_path: str,
    dims: tuple,
    dtype: str,
    spatial_mode: str,
    spatial_value: float,
    freq_mode: str,
    freq_bounds: list,
    workdir: str,
    base_compressed_bytes: int = None,
    return_corrected_data: bool = False,
):
    """Run FFCz with multiple frequency bounds and collect results.

    Args:
        ffcz_bin: Path to ffcz executable
        original_path: Path to original raw file
        base_decomp_path: Path to base decompressed file
        dims: Tuple of dimensions
        dtype: Data type ('float' or 'double')
        spatial_mode: Spatial error mode ('REL' or 'ABS')
        spatial_value: Spatial error bound value
        freq_mode: Frequency error mode ('REL' or 'ABS')
        freq_bounds: List of frequency error bounds to sweep
        workdir: Working directory for temporary files
        base_compressed_bytes: Optional base compressor size for compression ratio
        return_corrected_data: Whether to generate and return corrected data

    Returns:
        List of dictionaries, one per frequency bound, containing metrics and results
    """
    original_bytes = math.prod(dims) * (4 if dtype == "float" else 8)
    workdir_path = Path(workdir)
    workdir_path.mkdir(parents=True, exist_ok=True)

    rows = []
    for freq_bound in freq_bounds:
        safe_bound = f"{freq_bound:.12g}".replace("+", "")
        output_prefix = workdir_path / f"delta_{safe_bound}"

        row = run_ffcz_once(
            ffcz_bin=ffcz_bin,
            dtype=dtype,
            original_path=original_path,
            base_decomp_path=base_decomp_path,
            output_prefix=str(output_prefix),
            dims=dims,
            spatial_mode=spatial_mode,
            spatial_value=spatial_value,
            freq_mode=freq_mode,
            freq_value=freq_bound,
            return_corrected_data=return_corrected_data,
        )

        if base_compressed_bytes is not None:
            total_bytes = base_compressed_bytes + row["ffcz_bytes"]
            row["base_compressed_bytes"] = base_compressed_bytes
            row["total_bytes"] = total_bytes
            row["compression_ratio"] = original_bytes / total_bytes if total_bytes > 0 else 0

        # Clean up correction files after collecting sizes
        cleanup_ffcz_files(Path(str(output_prefix)))

        rows.append(row)

    return rows
