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
    dim_flag = f"-{len(dims)}"
    corrected_output = None

    if return_corrected_data:
        corrected_output = f"{output_prefix}.corrected"

    command = [
        ffcz_bin,
        "-f" if dtype == "float" else "-d",
        "-i", original_path,
        "-e", base_decomp_path,
        "-z", output_prefix,
        dim_flag,
        *[str(v) for v in dims],
        "-M", spatial_mode, str(spatial_value),
        "-F", freq_mode, str(freq_value),
    ]

    if corrected_output:
        command.extend(["-o", corrected_output])
        logger.info(f"FFCz will generate corrected data at: {corrected_output}")

    logger.info(f"Running FFCz command: {' '.join(command)}")

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"ffcz failed with code {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n\n"
            f"stderr:\n{completed.stderr}"
        )

    # Log FFCz output for debugging
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
    }

    # Read corrected data if requested
    if return_corrected_data and corrected_output:
        corrected_path = Path(corrected_output)
        if corrected_path.exists():
            try:
                np_dtype = np.float32 if dtype == "float" else np.float64
                corrected_data = np.fromfile(corrected_path, dtype=np_dtype)

                # Reshape to match original dimensions
                # dims are in file order (matching numpy shape), so reshape directly
                expected_size = math.prod(dims)
                if corrected_data.size == expected_size:
                    # Reshape to match dims directly (already in correct order)
                    corrected_data = corrected_data.reshape(dims)
                    result["corrected_data"] = corrected_data
                    logger.info(f"Read corrected data: shape={corrected_data.shape}, dtype={corrected_data.dtype}")
                else:
                    logger.warning(f"Corrected data size mismatch: got {corrected_data.size}, expected {expected_size}")

                # Clean up the corrected file after reading
                corrected_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to read corrected data from {corrected_path}: {e}")
        else:
            logger.warning(f"Corrected data file not found: {corrected_path}")

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
