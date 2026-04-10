import numpy as np
import msz
import threading
import signal
import logging
import traceback
import tempfile
import shutil
from pathlib import Path
from ffcz_correction import sweep_ffcz_frequency_bounds

# Configure logger for this module
logger = logging.getLogger(__name__)

def safe_handler(handler_func):
    """
    Decorator to wrap metric handlers with comprehensive error handling.
    Prevents any handler from crashing the server.
    """
    def wrapper(*args, **kwargs):
        try:
            return handler_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {handler_func.__name__}: {e}")
            logger.error(traceback.format_exc())
            return {
                'type': 'text',
                'content': f'Error in {handler_func.__name__}: {str(e)}'
            }
    return wrapper

def _get_msz_accelerator(config):
    """Helper to map accelerator string from config to msz constant."""
    if not isinstance(config, dict):
        return msz.ACCELERATOR_NONE
    
    acc_str = str(config.get('accelerator', '')).lower()
    mapping = {
        'omp': msz.ACCELERATOR_OMP,
        'cuda': msz.ACCELERATOR_CUDA,
        'hip': msz.ACCELERATOR_HIP,
        'sycl': msz.ACCELERATOR_SYCL,
        'none': msz.ACCELERATOR_NONE,
        '': msz.ACCELERATOR_NONE
    }
    return mapping.get(acc_str, msz.ACCELERATOR_NONE)


def _derive_edits_with_data_size_check(orig_f64, decp_f64, config, connectivity_type, W, H, D, threshold, preservation_options, accelerator):
    """
    Wrapper around msz.derive_edits() with size-based timeout guidance.
    
    For large datasets (>1M elements), derive_edits can take significant time.
    This helper logs performance expectations and potential optimizations.
    """
    data_size = orig_f64.size
    logger.info(f"Dataset contains ({data_size:,} elements)")
    
    # Call the actual function - no timeout here, but user is warned
    status, edits = msz.derive_edits(
        orig_f64, 
        decp_f64,
        preservation_options=preservation_options,
        connectivity_type=connectivity_type,
        W=W, H=H, D=D,
        rel_err_bound=threshold,
        accelerator=accelerator 
    )
    
    return status, edits


def compute_power_spectrum(data_array, parameters):
    """Compute power spectrum and relative error if original data is available"""
    import base64
    from io import BytesIO
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    dim = parameters.get('dim', len(data_array.shape))

    def compute_binned_spectrum(data, dim):
        """Helper function to compute binned power spectrum"""
        # Step 1: Compute density contrast (fluctuations around mean)
        mean_density = np.mean(data)
        delta = (data - mean_density) / mean_density

        # Step 2: Compute FFT and shift zero frequency to center
        delta_k = np.fft.fftn(delta)
        delta_k = np.fft.fftshift(delta_k)

        # Step 3: Calculate power spectrum (magnitude squared)
        power_spectrum = np.abs(delta_k) ** 2

        # Step 4: Create k-space grid matching actual data dimensions
        if dim == 1:
            N = data.shape[0]
            k_values = np.fft.fftfreq(N, d=1.0 / N)
            k_magnitude = np.abs(k_values)
        elif dim == 2:
            Ny, Nx = data.shape
            ky_values = np.fft.fftfreq(Ny, d=1.0 / Ny)
            kx_values = np.fft.fftfreq(Nx, d=1.0 / Nx)
            ky_grid, kx_grid = np.meshgrid(ky_values, kx_values, indexing='ij')
            k_magnitude = np.sqrt(kx_grid**2 + ky_grid**2)
        else:  # 3D
            Nz, Ny, Nx = data.shape
            kz_values = np.fft.fftfreq(Nz, d=1.0 / Nz)
            ky_values = np.fft.fftfreq(Ny, d=1.0 / Ny)
            kx_values = np.fft.fftfreq(Nx, d=1.0 / Nx)
            kz_grid, ky_grid, kx_grid = np.meshgrid(kz_values, ky_values, kx_values, indexing='ij')
            k_magnitude = np.sqrt(kx_grid**2 + ky_grid**2 + kz_grid**2)

        # Shift zero frequency to center
        k_magnitude = np.fft.fftshift(k_magnitude)

        # Flatten arrays
        k_flat = k_magnitude.flatten()
        power_flat = power_spectrum.flatten()

        # Remove zero frequency (avoid zero for log scale)
        non_zero_mask = k_flat > 0
        k_flat = k_flat[non_zero_mask]
        power_flat = power_flat[non_zero_mask]

        # Step 5: Bin the power spectrum using logspace bins
        k_min = np.min(k_flat)
        k_max = np.max(k_flat)
        num_bins = 40
        bins = np.logspace(np.log10(k_min), np.log10(k_max), num_bins)

        binned_k = []
        binned_power = []
        for i in range(len(bins) - 1):
            bin_mask = (k_flat >= bins[i]) & (k_flat < bins[i+1])
            if np.any(bin_mask):
                binned_k.append(np.mean(k_flat[bin_mask]))
                binned_power.append(np.mean(power_flat[bin_mask]))

        return binned_k, binned_power

    # Compute power spectrum for decompressed data
    binned_k, binned_power = compute_binned_spectrum(data_array, dim)

    # Check if original data is available for comparison
    original_data = parameters.get('original_data')
    has_original = original_data is not None

    # Compute relative error if original data is available
    binned_k_orig = None
    relative_error = None
    if has_original:
        binned_k_orig, binned_power_orig = compute_binned_spectrum(np.array(original_data), dim)
        # Compute relative error: (P'(k) - P(k)) / P(k)
        # Match bins between original and decompressed
        min_len = min(len(binned_k), len(binned_k_orig))
        binned_k = binned_k[:min_len]
        binned_power = binned_power[:min_len]
        binned_k_orig = binned_k_orig[:min_len]
        binned_power_orig = binned_power_orig[:min_len]

        # Calculate relative error, avoiding division by zero
        relative_error = []
        for p_orig, p_decp in zip(binned_power_orig, binned_power):
            if p_orig > 0:
                rel_err = (p_decp - p_orig) / p_orig
                relative_error.append(rel_err)
            else:
                relative_error.append(0.0)

    from matplotlib.ticker import LogLocator

    # Create plots: one or two depending on whether we have original data
    num_plots = 2 if has_original else 1
    fig, axes = plt.subplots(num_plots, 1, figsize=(8, 6 * num_plots))
    if num_plots == 1:
        axes = [axes]  # Make it iterable

    # Plot 1: Power Spectrum
    ax = axes[0]
    if has_original:
        ax.loglog(binned_k_orig, binned_power_orig, 'o-', linewidth=2.5, markersize=5,
                 label='Original', color='blue', alpha=0.7)
        ax.loglog(binned_k, binned_power, 's--', linewidth=2.5, markersize=5,
                 label='Decompressed', color='red', alpha=0.7)
        ax.legend(fontsize=14, loc='best', framealpha=0.9)
    else:
        ax.loglog(binned_k, binned_power, 'o-', linewidth=2.5, markersize=5)

    ax.set_xlabel('Wavenumber k', fontsize=16, fontweight='bold')
    ax.set_ylabel('Power Spectrum P(k)', fontsize=16, fontweight='bold')
    ax.set_title('Power Spectrum', fontsize=18, fontweight='bold', pad=15)
    ax.tick_params(axis='both', which='major', labelsize=14, width=1.5, length=6)
    ax.tick_params(axis='both', which='minor', labelsize=12, width=1, length=4)
    ax.xaxis.set_major_locator(LogLocator(base=10.0, numticks=6))
    ax.yaxis.set_major_locator(LogLocator(base=10.0, numticks=6))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    ax.grid(True, alpha=0.3, linewidth=1.2)
    ax.grid(True, which='minor', alpha=0.15, linewidth=0.8)

    # Plot 2: Relative Error (if original data available)
    if has_original:
        ax2 = axes[1]
        ax2.semilogx(binned_k, relative_error, 'o-', linewidth=2.5, markersize=5, color='green')
        ax2.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.5, label='Original (zero error)')

        ax2.set_xlabel('Wavenumber k', fontsize=16, fontweight='bold')
        ax2.set_ylabel('Relative Error (P\'(k) - P(k)) / P(k)', fontsize=16, fontweight='bold')
        ax2.set_title('Power Spectrum Relative Error', fontsize=18, fontweight='bold', pad=15)
        ax2.tick_params(axis='both', which='major', labelsize=14, width=1.5, length=6)
        ax2.tick_params(axis='both', which='minor', labelsize=12, width=1, length=4)
        ax2.xaxis.set_major_locator(LogLocator(base=10.0, numticks=6))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        ax2.grid(True, alpha=0.3, linewidth=1.2)
        ax2.grid(True, which='minor', alpha=0.15, linewidth=0.8)
        ax2.legend(fontsize=12, loc='best', framealpha=0.9)

    # Tighter layout with extra padding for rotated labels
    plt.tight_layout(pad=1.5)

    # Save to base64 with higher DPI for publication quality
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')

    result = {
        'type': 'power_spectrum',
        'data': [
            {'k': float(k), 'p': float(p)}
            for k, p in zip(binned_k, binned_power)
        ]
    }

    if has_original and relative_error:
        result['relative_error'] = [
            {'k': float(k), 'error': float(e)}
            for k, e in zip(binned_k, relative_error)
        ]

    return result


def compute_histogram(data_array, parameters):
    """Compute histogram data for frontend visualization"""
    num_bins = parameters.get('bins', 50)
    
    flat_data = data_array.flatten()
    
    try:
        counts, bin_edges = np.histogram(flat_data, bins=num_bins)
    except (ValueError, IndexError) as e:
        logger.error(f"Histogram computation failed: {e}")
        logger.error(f"Data range: [{np.min(flat_data)}, {np.max(flat_data)}]")
        logger.error(f"Data contains inf: {np.isinf(flat_data).any()}")
        logger.error(f"Data contains nan: {np.isnan(flat_data).any()}")
        logger.error(f"First 10 values: {flat_data[:10]}")
        raise
    
    # Calculate bin centers for plotting
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    bins_data = []
    for count, center in zip(counts, bin_centers):
        bins_data.append({
            'x': float(center),
            'count': int(count)
        })
        
    return {
        'type': 'histogram',
        'bins': bins_data
    }


def compute_statistics(data_array, parameters):
    """Compute basic statistical summary"""
    flat_data = data_array.flatten()
    
    stats_data = [
        ['Minimum', f'{np.min(flat_data)}'],
        ['Maximum', f'{np.max(flat_data)}'],
        ['Mean', f'{np.mean(flat_data)}'],
        ['Median', f'{np.median(flat_data)}'],
        ['Std Dev', f'{np.std(flat_data)}'],
        ['Variance', f'{np.var(flat_data)}'],
    ]
    
    return {
        'type': 'table',
        'headers': ['Statistic', 'Value'],
        'rows': stats_data
    }


def compute_entropy(data_array, parameters):
    """Compute information entropy"""
    bins = parameters.get('bins', 256)
    flat_data = data_array.flatten()
    
    # Compute histogram
    hist, _ = np.histogram(flat_data, bins=bins)
    
    # Normalize to get probabilities
    hist = hist / hist.sum()
    
    # Remove zero probabilities
    hist = hist[hist > 0]
    
    # Compute entropy
    entropy = -np.sum(hist * np.log2(hist))
    
    return {
        'type': 'scalar',
        'label': 'Entropy (bits)',
        'value': f'{entropy:.6f}'
    }


def compute_correlation(data_array, parameters):
    """Compute spatial autocorrelation"""
    max_lag = parameters.get('lag', 20)
    
    # Support 1D, 2D, 3D by flattening or taking a cross-section?
    # For simplicity, let's treat it as a 1D stream of data if requested,
    # or implement a more sophisticated spatial autocorrelation if needed.
    # For now, let's do a simple 1D autocorrelation of the flattened array
    # as a proxy for "random access" correlation.
    flat_data = data_array.flatten()
    
    lags = range(0, min(max_lag + 1, len(flat_data) // 4))
    correlations = []
    mean = np.mean(flat_data)
    var = np.var(flat_data)
    
    if var == 0:
        correlations = [1.0] * len(lags)
    else:
        for lag in lags:
            if lag == 0:
                correlations.append(1.0)
            else:
                # Optimized autocorrelation
                c = np.mean((flat_data[:-lag] - mean) * (flat_data[lag:] - mean)) / var
                correlations.append(float(c))
    
    return {
        'type': 'correlation',
        'data': [
            {'lag': int(l), 'value': float(v)}
            for l, v in zip(lags, correlations)
        ]
    }


def compute_wavelet(data_array, parameters):
    """Compute wavelet transform coefficients"""
    try:
        import pywt
    except ImportError:
        return {
            'type': 'text',
            'content': 'PyWavelets package is not installed. Please install it with: pip install PyWavelets'
        }
    
    wavelet = parameters.get('wavelet', 'db4')
    level = parameters.get('level', 3)
    
    if len(data_array.shape) == 1:
        coeffs = pywt.wavedec(data_array, wavelet, level=level)
        
        # Compute energy in each level
        energies = [np.sum(c**2) for c in coeffs]
        total_energy = sum(energies)
        
        table_data = []
        table_data.append(['Approximation', f'{energies[0]:.6e}', f'{100*energies[0]/total_energy:.2f}%'])
        for i in range(1, len(energies)):
            table_data.append([f'Detail {i}', f'{energies[i]:.6e}', f'{100*energies[i]/total_energy:.2f}%'])
        
        return {
            'type': 'table',
            'headers': ['Level', 'Energy', 'Percentage'],
            'rows': table_data
        }
    elif len(data_array.shape) == 2:
        coeffs = pywt.wavedec2(data_array, wavelet, level=level)
        return {
            'type': 'text',
            'content': f'2D wavelet decomposition completed with {level} levels using {wavelet} wavelet.'
        }
    else:
        return {
            'type': 'text',
            'content': 'Wavelet analysis is currently supported for 1D and 2D data only.'
        }


def _gaussian_kernel_1d(size, sigma):
    radius = size // 2
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x ** 2) / (2 * sigma ** 2))
    kernel /= np.sum(kernel)
    return kernel


def _gaussian_filter_2d(arr, size=11, sigma=1.5):
    if size < 1:
        return arr
    if size % 2 == 0:
        size += 1
    kernel = _gaussian_kernel_1d(size, sigma)
    radius = size // 2
    padded = np.pad(arr, ((radius, radius), (radius, radius)), mode='reflect')
    temp = np.apply_along_axis(lambda m: np.convolve(m, kernel, mode='valid'), axis=1, arr=padded)
    filtered = np.apply_along_axis(lambda m: np.convolve(m, kernel, mode='valid'), axis=0, arr=temp)
    return filtered


def _normalize_to_unit(arr, min_val=None, max_val=None):
    if min_val is None or max_val is None:
        min_val = np.min(arr)
        max_val = np.max(arr)
    denom = max_val - min_val
    if denom == 0:
        return np.zeros_like(arr, dtype=np.float64)
    return (arr - min_val) / denom


def _quantize(arr, bins=256):
    if bins <= 1:
        return arr
    levels = bins - 1
    return np.round(arr * levels) / levels


def _compute_dssim_2d(x, y, window_size, sigma, c1, c2, bins):
    min_val = min(np.min(x), np.min(y))
    max_val = max(np.max(x), np.max(y))
    x_n = _normalize_to_unit(x, min_val, max_val)
    y_n = _normalize_to_unit(y, min_val, max_val)
    x_q = _quantize(x_n, bins=bins)
    y_q = _quantize(y_n, bins=bins)
    mu_x = _gaussian_filter_2d(x_q, size=window_size, sigma=sigma)
    mu_y = _gaussian_filter_2d(y_q, size=window_size, sigma=sigma)
    mu_x2 = mu_x * mu_x
    mu_y2 = mu_y * mu_y
    sigma_x2 = _gaussian_filter_2d(x_q * x_q, size=window_size, sigma=sigma) - mu_x2
    sigma_y2 = _gaussian_filter_2d(y_q * y_q, size=window_size, sigma=sigma) - mu_y2
    sigma_xy = _gaussian_filter_2d(x_q * y_q, size=window_size, sigma=sigma) - (mu_x * mu_y)
    s1 = (2 * mu_x * mu_y + c1) / (mu_x2 + mu_y2 + c1)
    s2 = (2 * sigma_xy + c2) / (sigma_x2 + sigma_y2 + c2)
    local_dssim = s1 * s2
    return float(np.mean(local_dssim))


def compute_dssim(data_array, parameters):
    """Compute DSSIM between original data and data_array using the provided algorithm."""
    original = parameters.get('original_data')
    if original is None:
        return {
            'type': 'text',
            'content': 'DSSIM requires original_data (comparison_key) in parameters.'
        }
    window_size = int(parameters.get('window_size', 11))
    sigma = float(parameters.get('sigma', 1.5))
    bins = int(parameters.get('bins', 256))
    c1 = float(parameters.get('c1', 1e-8))
    c2 = float(parameters.get('c2', 1e-8))

    x = np.array(original, dtype=np.float64)
    y = np.array(data_array, dtype=np.float64)
    if x.shape != y.shape:
        return {
            'type': 'text',
            'content': f'DSSIM requires matching shapes. Got {x.shape} vs {y.shape}.'
        }
    if x.ndim == 2:
        value = _compute_dssim_2d(x, y, window_size, sigma, c1, c2, bins)
    elif x.ndim == 3:
        values = []
        for idx in range(x.shape[0]):
            values.append(_compute_dssim_2d(x[idx], y[idx], window_size, sigma, c1, c2, bins))
        value = float(np.mean(values))
    else:
        return {
            'type': 'text',
            'content': f'DSSIM supports 2D or 3D arrays. Got ndim={x.ndim}.'
        }
    return {
        'type': 'scalar',
        'label': 'DSSIM',
        'value': f'{value:.6f}'
    }


def compute_critical_points(data_array, parameters):
    """Compute critical points (minima/maxima) for a single dataset using MSZ."""
    def _flatten_segmentation_field(field):
        if field is None:
            return None
        try:
            arr = np.asarray(field)
            return arr.ravel().tolist()
        except Exception:
            pass
        if hasattr(field, 'tolist'):
            try:
                return field.tolist()
            except Exception:
                pass
        if isinstance(field, (list, tuple)):
            return [float(x) if np.isfinite(x) else 0.0 for x in field]
        return None

    def _get_segmentation_component(labels_obj, candidate_names):
        if labels_obj is None:
            return None
        if isinstance(labels_obj, dict):
            for key in candidate_names:
                if key in labels_obj:
                    return labels_obj[key]
        for key in candidate_names:
            if hasattr(labels_obj, key):
                value = getattr(labels_obj, key)
                if callable(value):
                    try:
                        value = value()
                    except TypeError:
                        pass
                return value
        return None

    def _extract_segmentation_fields(labels_obj):
        metadata = {}
        if isinstance(labels_obj, np.ndarray):
            labels_arr = np.asarray(labels_obj)
            if labels_arr.ndim >= 4 and labels_arr.shape[-1] >= 2:
                # MSZ returns labels as (W, H, D, 2). Convert to (D, H, W) for C-order flattening.
                descending_raw = np.ascontiguousarray(labels_arr[..., 0].transpose(2, 1, 0)).astype(np.int64, copy=False)
                ascending_raw = np.ascontiguousarray(labels_arr[..., 1].transpose(2, 1, 0)).astype(np.int64, copy=False)

                def _remap_nonneg_labels(arr):
                    flat = arr.reshape(-1)
                    mask = flat >= 0
                    if not np.any(mask):
                        return arr, np.array([], dtype=np.int64)
                    unique = np.unique(flat[mask])
                    remapped = flat.copy()
                    remapped[mask] = np.searchsorted(unique, remapped[mask])
                    return remapped.reshape(arr.shape), unique

                descending_mapped, desc_unique = _remap_nonneg_labels(descending_raw)
                ascending_mapped, asc_unique = _remap_nonneg_labels(ascending_raw)

                logger.info(
                    "MSz segmentation labels: descending=%d unique, ascending=%d unique",
                    desc_unique.size,
                    asc_unique.size
                )
                logger.debug(
                    "Descending sample=%s | Ascending sample=%s",
                    desc_unique[:20].tolist(),
                    asc_unique[:20].tolist()
                )

                # One ID per observed (descending, ascending) manifold intersection.
                pairs = np.stack((descending_mapped, ascending_mapped), axis=-1)
                pairs_flat = pairs.reshape(-1, 2)
                unique_pairs, morse_inverse = np.unique(pairs_flat, axis=0, return_inverse=True)
                morse = morse_inverse.reshape(descending_mapped.shape, order='C').astype(np.int64, copy=False)

                metadata = {
                    'ascending': {
                        'unique': list(range(int(asc_unique.size))),
                        'count': int(asc_unique.size)
                    },
                    'descending': {
                        'unique': list(range(int(desc_unique.size))),
                        'count': int(desc_unique.size)
                    },
                    'morse_smale': {
                        'count': int(unique_pairs.shape[0]),
                        'pairs': unique_pairs.tolist()
                    }
                }

                return {
                    'ascending': ascending_mapped.tolist(),
                    'descending': descending_mapped.tolist(),
                    'morse_smale': morse.tolist(),
                }, metadata

        components = {}
        mapping = {
            'ascending': ('ascending', 'asc', 'ascending_manifold'),
            'descending': ('descending', 'desc', 'descending_manifold'),
            'morse_smale': ('morse_smale', 'morse', 'ms', 'morse_smale_manifold'),
        }
        for canonical, candidate_names in mapping.items():
            raw_component = _get_segmentation_component(labels_obj, candidate_names)
            serialized = _flatten_segmentation_field(raw_component)
            if serialized:
                components[canonical] = serialized
        if not components:
            serialized = _flatten_segmentation_field(labels_obj)
            if serialized:
                components['morse_smale'] = serialized
        return components, metadata

    try:
        logger.info("Starting critical points computation")
        dims = parameters.get('dimensions')

        if dims and len(dims) in (2, 3):
            if len(dims) == 2:
                width, height = int(dims[0]), int(dims[1])
                depth = 1
            else:
                width, height, depth = int(dims[0]), int(dims[1]), int(dims[2])
        else:
            # Fallback to numpy shape heuristics
            if len(data_array.shape) == 2:
                height, width = data_array.shape
                depth = 1
            elif len(data_array.shape) == 3:
                depth, height, width = data_array.shape
            else:
                return {
                    'type': 'text',
                    'content': 'Critical point extraction is supported for 2D and 3D data only.'
                }

        config = parameters.get('config', {}) or {}
        
        # Support flat parameters for common critical point settings
        accelerator_name = parameters.get('accelerator', config.get('accelerator', 'omp'))
        # Ensure we have a valid config for helper functions
        config = { **config, 'accelerator': accelerator_name }
        
        accelerator = _get_msz_accelerator(config)
        connectivity_type = int(parameters.get('connectivityType', config.get('connectivityType', 0)))
        
        # Validate data dimensions match expected size
        expected_size = width * height * depth
        actual_size = data_array.size
        if expected_size != actual_size:
            logger.error(f"Dimension mismatch: W={width} * H={height} * D={depth} = {expected_size}, but data size is {actual_size}")
            return {
                'type': 'text',
                'content': f'Dimension mismatch: expected {expected_size} elements but got {actual_size}'
            }
        
        # Ensure contiguous array for C++ binding
        arr_data = np.ascontiguousarray(data_array, dtype=np.float64)
        
        compute_segmentation = bool(parameters.get('computeSegmentation', config.get('computeSegmentation', True)))
        logger.info(
            f"Calling msz.extract_critical_points with dims: W={width}, H={height}, D={depth}, "
            f"compute_segmentation={compute_segmentation}, connectivity={connectivity_type}, "
            f"accelerator={accelerator}, data_size={arr_data.size}"
        )
        
        try:
            # Use explicit keywords to avoid argument shifts when the Python binding changes.
            result = msz.extract_critical_points(
                arr_data,
                compute_segmentation=compute_segmentation,
                connectivity_type=connectivity_type,
                W=width,
                H=height,
                D=depth,
                accelerator=accelerator
            )
            logger.info(f"msz.extract_critical_points returned successfully")
        except Exception as msz_error:
            logger.error(f"msz.extract_critical_points raised exception: {msz_error}")
            logger.error(traceback.format_exc())
            return {
                'type': 'text',
                'content': f'MSz library error: {str(msz_error)}. This may be due to incompatible accelerator settings or data format issues.'
            }
        
        # Check status
        status = result.get('status', msz.ERR_UNKNOWN_ERROR)
        if status != msz.ERR_NO_ERROR:
            msg = f'MSZ error: Failed to extract critical points (error code: {status})'
            if status == msz.ERR_NOT_IMPLEMENTED:
                msg = f'MSz extraction is not implemented for accelerator {accelerator}. Please try using "None" (CPU) instead.'
            return {
                'type': 'text',
                'content': msg
            }

        minima_list = result.get('minima', [])
        maxima_list = result.get('maxima', [])
        saddles_list = result.get('saddles', [])
        
        # Convert CriticalPoint objects to flat numeric lists [x, y, z, value, ...]
        # This significantly reduces memory and JSON size for large sets.
        minima_flat = []
        for cp_obj in minima_list:
            minima_flat.extend([int(cp_obj.x), int(cp_obj.y), int(cp_obj.z), float(cp_obj.value)])
        
        maxima_flat = []
        for cp_obj in maxima_list:
            maxima_flat.extend([int(cp_obj.x), int(cp_obj.y), int(cp_obj.z), float(cp_obj.value)])
        
        saddles_flat = []
        for cp_obj in saddles_list:
            saddles_flat.extend([int(cp_obj.x), int(cp_obj.y), int(cp_obj.z), float(cp_obj.value)])
        
        # Log counts for debugging
        logger.info(f"Critical points: {len(minima_list)} minima, {len(maxima_list)} maxima, {len(saddles_list)} saddles")

        res = {
            'type': 'critical_points',
            'minima': {
                'count': len(minima_list),
                'points': minima_flat,
                'format': 'flat' # Hint for frontend
            },
            'maxima': {
                'count': len(maxima_list),
                'points': maxima_flat,
                'format': 'flat'
            },
            'saddles': {
                'count': len(saddles_list),
                'points': saddles_flat,
                'format': 'flat'
            },
            'dimensions': {
                'width': width,
                'height': height,
                'depth': depth
            }
        }

        # Return segmentation labels (ascending/descending/Morse-Smale) when available.
        if compute_segmentation and result.get('labels') is not None:
            labels = result.get('labels')
            segmentation_fields, segmentation_meta = _extract_segmentation_fields(labels)
            if segmentation_fields:
                res['segmentation'] = {
                    'dimensions': {
                        'width': width,
                        'height': height,
                        'depth': depth
                    },
                    **segmentation_fields
                }
                if segmentation_meta:
                    res['segmentation']['metadata'] = segmentation_meta

        # If original data is provided, also compute faults
        original_data = parameters.get('original_data')
        if original_data is not None:
            logger.info(f"Original data found in parameters, computing faults for {res['type']}")
            # Use the standard handler signature (decompressed_data, parameters)
            # This is cleaner as parameters already contains original_data
            faults = compute_critical_points_faults(data_array, parameters)
            logger.info(f"Faults computed: {faults}")
            if faults and 'error' not in faults:
                res['faults'] = faults
        else:
            logger.info("Original data NOT found in parameters, skipping fault calculation")

        return res
    except Exception as e:
        logger.error(f"Error computing critical points: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'type': 'text',
            'content': f'Error computing critical points: {e}',
        }

def compute_critical_points_faults(data_array, parameters):
    """
    Compute critical point faults using MSZ.
    Can be called as a standalone handler or helper.
    """
    # If parameters is Actually a numpy array, it means this was called as a helper
    if isinstance(parameters, np.ndarray):
        original = data_array
        decompressed = parameters
        # In helper mode, we don't have parameters, so we use shape heuristics
        params = {}
    else:
        decompressed = data_array
        original = parameters.get('original_data')
        params = parameters

    if original is None:
        return {'error': 'Original data required for fault computation'}

    try:
        dims = params.get('dimensions')
        if dims and len(dims) in (2, 3):
            if len(dims) == 2:
                W, H = int(dims[0]), int(dims[1])
                D = 1
            else:
                W, H, D = int(dims[0]), int(dims[1]), int(dims[2])
        else:
            if len(original.shape) == 2:
                H, W = original.shape
                D = 1
            elif len(original.shape) == 3:
                D, H, W = original.shape
            else:
                return {'error': 'Critical point faults are supported for 2D and 3D data only.'}
        
        # Data is guaranteed to be clean from main.py cache entry points
        # Ensure arrays are contiguous for C++ binding
        orig_data = np.ascontiguousarray(original, dtype=np.float64)
        decp_data = np.ascontiguousarray(decompressed, dtype=np.float64)

        config = params.get('config', {}) or {}
        
        # Support flat parameters for top-level keys
        acc_name = params.get('accelerator', config.get('accelerator', 'omp'))
        # Reconstruct config for helper functions
        config = { **config, 'accelerator': acc_name }
        
        accelerator = _get_msz_accelerator(config)
        connectivity_type = int(params.get('connectivityType', config.get('connectivityType', 0)))

        # Count faults using MSZ
        try:
            result = msz.count_faults(
                orig_data, 
                decp_data, 
                connectivity_type=connectivity_type, 
                W=W, H=H, D=D,
                accelerator=accelerator
            )
            logger.info(f"msz.count_faults returned successfully")
        except Exception as msz_error:
            logger.error(f"msz.count_faults raised exception: {msz_error}")
            logger.error(traceback.format_exc())
            return {'error': f'MSz count_faults error: {str(msz_error)}'}

        # Check status
        status = result.get('status', msz.ERR_UNKNOWN_ERROR)
        if status != msz.ERR_NO_ERROR:
            msg = f'MSZ error: Failed to count faults (code: {status})'
            if status == msz.ERR_NOT_IMPLEMENTED:
                msg = f'MSz fault counting is not implemented for accelerator {accelerator}.'
            return {'error': msg}

        return {
            'type': 'faults',
            'num_false_min': result.get('num_false_min', 0),
            'num_false_max': result.get('num_false_max', 0),
            'num_false_labels': result.get('num_false_labels', 0),
        }
    except Exception as e:
        logger.error(f"Error computing critical point faults: {e}")
        logger.error(traceback.format_exc())
        return {'error': str(e)}


def apply_critical_points_correction(original, decompressed, parameters):
    """
    Apply topology-preserving correction to decompressed data using MSz.
    Uses derive_edits followed by apply_edits.
    """
    try:
        config = parameters.get('config', {})
        dims = parameters.get('dimensions') or parameters.get('metadata', {}).get('dimensions')
        
        if dims and len(dims) in (2, 3):
            if len(dims) == 2:
                W, H = int(dims[0]), int(dims[1])
                D = 1
            else:
                W, H, D = int(dims[0]), int(dims[1]), int(dims[2])
        else:
            # Fallback to numpy shape heuristics
            if len(original.shape) == 2:
                H, W = original.shape
                D = 1
            elif len(original.shape) == 3:
                D, H, W = original.shape
            else:
                logger.error("Critical point correction is supported for 2D and 3D data only.")
                return {'error': 'Critical point correction is supported for 2D and 3D data only.'}

        logger.info(f"Applying correction with dims: W={W}, H={H}, D={D}")

        # Preservation options
        preservation_options = 0
        if config.get('preserveMin', True):
            preservation_options |= msz.PRESERVE_MIN
        if config.get('preserveMax', True):
            preservation_options |= msz.PRESERVE_MAX
        if config.get('preservePath', False):
            preservation_options |= msz.PRESERVE_PATH
        
        connectivity_type = int(config.get('connectivityType', 0))
        threshold = float(config.get('threshold', 0.1))
        
        # Ensure arrays are contiguous for C++ binding
        logger.info(f"Ensuring contiguous arrays... Shapes: orig={original.shape}, decp={decompressed.shape}")
        orig_data = np.ascontiguousarray(original, dtype=np.float64)
        decp_data = np.ascontiguousarray(decompressed, dtype=np.float64)
        
        logger.info(f"Arrays prepared. Sizes: orig={orig_data.size}, decp={decp_data.size}")

        # 1. Derive edits
        # connectivity_type from config, accelerator mapping for performance
        accelerator = _get_msz_accelerator(config)
        logger.info(f"Starting msz.derive_edits(accelerator={accelerator})...")
        
        try:
            status, edits = _derive_edits_with_data_size_check(
                orig_data, 
                decp_data,
                config,
                connectivity_type,
                W, H, D,
                threshold,
                preservation_options,
                accelerator
            )
            logger.info(f"msz.derive_edits finished with status: {status}, num_edits: {len(edits)}")
        except Exception as e:
            logger.error(f"msz.derive_edits raised exception: {e}")
            raise

        if status != msz.ERR_NO_ERROR:
            msg = f'MSz derive_edits failed with status {status}'
            if status == msz.ERR_NOT_IMPLEMENTED:
                msg = f'MSz derive_edits is not implemented for accelerator {accelerator}. Please try using "None" (CPU) instead.'
            elif status == msz.ERR_NO_AVAILABLE_GPU:
                msg = 'No compatible GPU found for MSz operations.'
            return {'error': msg}

        # 2. Apply edits (in-place modification of corrected_data)
        # We ensure corrected_data is float64 to avoid silent failures in CUDA bindings
        # that might happen with float32 arrays (where they modify a temporary copy)
        # NOTE: We use ACCELERATOR_NONE (Serial) for apply_edits because it's a very fast
        # operation on CPU (O(N_edits)) and avoids CUDA host-device sync issues.
        # derive_edits (the heavy part) still uses the selected accelerator.
        logger.info(f"Applying {len(edits)} edits to corrected_data...")
        # Make an explicit deep copy to avoid in-place edits mutating the original decompressed array.
        corrected_data = np.array(decompressed, dtype=np.float64, copy=True, order='C')
        status = msz.apply_edits(
            corrected_data,
            edits,
            W=W, H=H, D=D,
            accelerator=accelerator,
            device_id=0
        )
        logger.info(f"msz.apply_edits finished with status: {status}")

        if status != msz.ERR_NO_ERROR:
            msg = f'MSz apply_edits failed with status {status}'
            if status == msz.ERR_NOT_IMPLEMENTED:
                msg = f'MSz apply_edits is not implemented for accelerator {accelerator}. falling back to serial application might be needed.'
            return {'error': msg}

        # Convert back to original dtype to maintain consistency with the rest of the pipeline
        final_corrected_data = corrected_data.astype(decompressed.dtype)
        
        # Log if data was actually changed
        diff = np.abs(final_corrected_data - decompressed)
        max_diff = np.max(diff)
        num_changed = np.count_nonzero(diff)
        logger.info(f"Correction complete. Max diff: {max_diff}, changed elements: {num_changed}")

        # 3. Compress edits and calculate total size and ratio
        compressed_edits_size = 0
        try:
            statusIdx, compressed_edits = msz.compress_edits_zstd(edits)
            if statusIdx == msz.ERR_NO_ERROR:
                compressed_edits_size = len(compressed_edits)
                logger.info(f"Edits compressed successfully. Size: {compressed_edits_size} bytes")
            else:
                logger.warning(f"Failed to compress edits (status: {statusIdx})")
        except Exception as ce_err:
            logger.warning(f"Error compressing edits: {ce_err}")

        # Calculate overall compression ratio if original data size and compressed size are available
        metadata = parameters.get('metadata', {})
        compressed_metrics = metadata.get('compressed_metrics', {})
        
        # Try to find compressed data size in metrics (common libpressio keys)
        comp_data_size = (
            compressed_metrics.get('size:compressed_size') or 
            compressed_metrics.get('pressio:compressed_size') or
            compressed_metrics.get('compressed_size')
        )
        
        # Fallback: search for any key ending in ':compressed_size'
        if comp_data_size is None:
            for k, v in compressed_metrics.items():
                if k.endswith(':compressed_size') and isinstance(v, (int, float)):
                    comp_data_size = v
                    break
        
        res = {
            'status': 'success',
            'num_edits': len(edits),
            'compressed_edits_size': compressed_edits_size,
            'corrected_data': final_corrected_data,
            'metrics': {
                'qoi:num_edits': len(edits),
                'qoi:compressed_edits_size': compressed_edits_size,
            }
        }

        # Calculate ratio if we have all parts
        if comp_data_size is not None:
            # original_size in bytes
            orig_size = original.nbytes
            total_compressed_size = comp_data_size + compressed_edits_size
            if total_compressed_size > 0:
                overall_ratio = orig_size / total_compressed_size
                res['overall_compression_ratio'] = float(overall_ratio)
                res['compressed_data_size'] = int(comp_data_size)
                
                # Add to metrics for standard visualization
                res['metrics']['qoi:overall_compression_ratio'] = float(overall_ratio)
                res['metrics']['qoi:total_compressed_size'] = int(total_compressed_size)
                
                logger.info(f"Overall compression ratio: {overall_ratio:.6f}")

        return res

    except Exception as e:
        logger.error(f'Error applying correction: {e}')
        logger.error(traceback.format_exc())
        return {'error': f'Error applying correction: {e}'}


def apply_ffcz_correction(original, decompressed, parameters):
    """
    Apply FFCz frequency-domain correction sweep.
    Runs FFCz with multiple frequency bounds and returns metrics for each.

    Args:
        original: Original numpy array
        decompressed: Base decompressed numpy array
        parameters: Dict containing 'config' and 'metadata'

    Returns:
        Dict with sweep results, metrics, and file sizes
    """
    try:
        config = parameters.get('config', {})
        metadata = parameters.get('metadata', {})

        # Extract dimensions
        dims = metadata.get('dimensions')
        logger.info(f"FFCz: metadata dimensions = {dims}")
        logger.info(f"FFCz: original.shape = {original.shape}, decompressed.shape = {decompressed.shape}")

        if not dims or len(dims) not in (2, 3):
            # Fallback to array shape
            # FFCz expects dimensions in the order they appear in the file
            # numpy.tofile() writes in C-order (row-major), so dims should match shape directly
            if len(original.shape) == 2:
                dims = (original.shape[0], original.shape[1])  # H, W (as stored in file)
            elif len(original.shape) == 3:
                dims = (original.shape[0], original.shape[1], original.shape[2])  # D, H, W (as stored in file)
            else:
                return {'error': 'FFCz correction requires 2D or 3D data'}

        logger.info(f"FFCz: Using dimensions = {dims} for FFCz command (matching file layout)")

        # Determine data type
        if original.dtype == np.float32:
            dtype = 'float'
        elif original.dtype == np.float64:
            dtype = 'double'
        else:
            # Convert to float32 by default
            original = original.astype(np.float32)
            decompressed = decompressed.astype(np.float32)
            dtype = 'float'

        # Get configuration parameters
        spatial_mode = config.get('spatial_mode', 'REL')
        spatial_value = float(config.get('spatial_value', 1e-3))
        freq_mode = config.get('freq_mode', 'REL')
        freq_bounds = config.get('freq_bounds', [1e-4])
        return_corrected_data = config.get('return_corrected_data', False)

        # Ensure freq_bounds is a list
        if not isinstance(freq_bounds, list):
            freq_bounds = [freq_bounds]

        # Get base compressed size if available
        compressed_metrics = metadata.get('compressed_metrics', {})
        base_compressed_bytes = (
            compressed_metrics.get('size:compressed_size') or
            compressed_metrics.get('pressio:compressed_size') or
            compressed_metrics.get('compressed_size')
        )
        if base_compressed_bytes is None:
            for k, v in compressed_metrics.items():
                if k.endswith(':compressed_size') and isinstance(v, (int, float)):
                    base_compressed_bytes = int(v)
                    break

        # Create temporary directory and files
        temp_dir = tempfile.mkdtemp(prefix='ffcz_')
        try:
            original_file = Path(temp_dir) / 'original.raw'
            decomp_file = Path(temp_dir) / 'decomp.raw'
            work_dir = Path(temp_dir) / 'work'

            # Write data to files
            logger.info(f"Writing original data to {original_file}")
            original_to_write = original.astype(np.float32 if dtype == 'float' else np.float64)
            original_to_write.tofile(original_file)
            original_size = Path(original_file).stat().st_size
            logger.info(f"Wrote original data: {original_size} bytes, shape={original.shape}, dtype={original.dtype}")

            logger.info(f"Writing decompressed data to {decomp_file}")
            decompressed_to_write = decompressed.astype(np.float32 if dtype == 'float' else np.float64)
            decompressed_to_write.tofile(decomp_file)
            decomp_size = Path(decomp_file).stat().st_size
            logger.info(f"Wrote decompressed data: {decomp_size} bytes, shape={decompressed.shape}, dtype={decompressed.dtype}")

            # Find FFCz binary
            ffcz_bin = shutil.which('ffcz')
            if not ffcz_bin:
                # Try common locations
                common_paths = [
                    '/home/guoxil/usr/local/bin/ffcz',
                    '/usr/local/bin/ffcz',
                    '/usr/bin/ffcz',
                ]
                for path in common_paths:
                    if Path(path).exists():
                        ffcz_bin = path
                        break

            if not ffcz_bin:
                return {'error': 'FFCz binary not found. Please ensure ffcz is installed.'}

            logger.info(f"Running FFCz sweep with {len(freq_bounds)} frequency bounds")

            # Run FFCz sweep
            results = sweep_ffcz_frequency_bounds(
                ffcz_bin=ffcz_bin,
                original_path=str(original_file),
                base_decomp_path=str(decomp_file),
                dims=tuple(dims),
                dtype=dtype,
                spatial_mode=spatial_mode,
                spatial_value=spatial_value,
                freq_mode=freq_mode,
                freq_bounds=freq_bounds,
                workdir=str(work_dir),
                base_compressed_bytes=base_compressed_bytes,
                return_corrected_data=return_corrected_data,
            )

            logger.info(f"FFCz sweep completed with {len(results)} results")

            # Format results for frontend
            formatted_results = []
            for row in results:
                result = {
                    'freq_bound': row['freq_bound'],
                    'ffcz_bytes': row['ffcz_bytes'],
                    'metrics': {}
                }

                # Add metrics with FFCz: prefix
                if row.get('freq_bound') is not None:
                    result['metrics']['FFCz:frequency_error_bound'] = row['freq_bound']
                if row.get('mae') is not None:
                    result['metrics']['FFCz:MAE'] = row['mae']
                if row.get('mse') is not None:
                    result['metrics']['FFCz:MSE'] = row['mse']
                if row.get('rmse') is not None:
                    result['metrics']['FFCz:RMSE'] = row['rmse']
                if row.get('nrmse') is not None:
                    result['metrics']['FFCz:NRMSE'] = row['nrmse']
                if row.get('psnr') is not None:
                    result['metrics']['FFCz:PSNR'] = row['psnr']
                if row.get('ssnr') is not None:
                    result['metrics']['FFCz:SSNR'] = row['ssnr']
                if row.get('max_relative_frequency_error') is not None:
                    result['metrics']['FFCz:max_freq_error'] = row['max_relative_frequency_error']
                if row.get('additional_storage') is not None:
                    result['metrics']['FFCz:additional_storage'] = row['additional_storage']

                # Add compression info if available
                if 'compression_ratio' in row:
                    result['compression_ratio'] = row['compression_ratio']
                    result['total_bytes'] = row['total_bytes']
                    result['base_compressed_bytes'] = row['base_compressed_bytes']
                    # Add to metrics for comparison charts
                    result['metrics']['FFCz:compression_ratio'] = row['compression_ratio']
                    result['metrics']['FFCz:total_bytes'] = row['total_bytes']
                    result['metrics']['FFCz:ffcz_bytes'] = row['ffcz_bytes']

                # Add corrected data if available
                if 'corrected_data' in row:
                    result['corrected_data'] = row['corrected_data']

                formatted_results.append(result)

            return {
                'status': 'success',
                'results': formatted_results,
                'config': {
                    'spatial_mode': spatial_mode,
                    'spatial_value': spatial_value,
                    'freq_mode': freq_mode,
                    'dims': dims,
                    'dtype': dtype,
                }
            }

        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")

    except Exception as e:
        logger.error(f'Error applying FFCz correction: {e}')
        logger.error(traceback.format_exc())
        return {'error': f'Error applying FFCz correction: {e}'}


# Wrap all handlers with error handling to prevent crashes
METRIC_HANDLERS = {
    'power_spectrum': safe_handler(compute_power_spectrum),
    'histogram': safe_handler(compute_histogram),
    'statistics': safe_handler(compute_statistics),
    'entropy': safe_handler(compute_entropy),
    'correlation': safe_handler(compute_correlation),
    'wavelet': safe_handler(compute_wavelet),
    'dssim': safe_handler(compute_dssim),
    'critical_points': safe_handler(compute_critical_points),
    'critical_points_correction': safe_handler(apply_critical_points_correction),
    'ffcz_correction': safe_handler(apply_ffcz_correction),
}
