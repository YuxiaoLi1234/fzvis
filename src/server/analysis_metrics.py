import numpy as np
import msz
import threading
import signal
import logging
import traceback

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
    """Compute power spectrum using existing plotPowerSpectrum.py logic"""
    import base64
    from io import BytesIO
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    dim = parameters.get('dim', len(data_array.shape))
    
    # Compute FFT
    fft_result = np.fft.fftn(data_array)
    power_spectrum = np.abs(fft_result) ** 2
    
    # Create k-space grid
    if dim == 1:
        N = data_array.shape[0]
        kx = np.fft.fftfreq(N, d=1.0)
        k_magnitude = np.abs(kx)
    elif dim == 2:
        Ny, Nx = data_array.shape
        ky = np.fft.fftfreq(Ny, d=1.0)
        kx = np.fft.fftfreq(Nx, d=1.0)
        kx_grid, ky_grid = np.meshgrid(kx, ky)
        k_magnitude = np.sqrt(kx_grid**2 + ky_grid**2)
    else:  # 3D
        Nz, Ny, Nx = data_array.shape
        kz = np.fft.fftfreq(Nz, d=1.0)
        ky = np.fft.fftfreq(Ny, d=1.0)
        kx = np.fft.fftfreq(Nx, d=1.0)
        kx_grid, ky_grid, kz_grid = np.meshgrid(kx, ky, kz, indexing='ij')
        k_magnitude = np.sqrt(kx_grid**2 + ky_grid**2 + kz_grid**2)
    
    # Flatten arrays
    k_flat = k_magnitude.flatten()
    power_flat = power_spectrum.flatten()
    
    # Remove zero frequency
    non_zero_mask = k_flat > 0
    k_flat = k_flat[non_zero_mask]
    power_flat = power_flat[non_zero_mask]
    
    # Bin the power spectrum
    k_bins = np.logspace(np.log10(k_flat.min()), np.log10(k_flat.max()), 50)
    bin_indices = np.digitize(k_flat, k_bins)
    
    binned_k = []
    binned_power = []
    for i in range(1, len(k_bins)):
        mask = bin_indices == i
        if np.any(mask):
            binned_k.append(np.mean(k_flat[mask]))
            binned_power.append(np.mean(power_flat[mask]))
    
    # Create plot
    plt.figure(figsize=(10, 6))
    plt.loglog(binned_k, binned_power, 'o-', linewidth=2, markersize=4)
    plt.xlabel('Wavenumber k', fontsize=12)
    plt.ylabel('Power Spectrum P(k)', fontsize=12)
    plt.title('Power Spectrum', fontsize=14)
    plt.grid(True, alpha=0.3)
    
    # Save to base64
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    return {
        'type': 'power_spectrum',
        'data': [
            {'k': float(k), 'p': float(p)}
            for k, p in zip(binned_k, binned_power)
        ]
    }


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

        config = parameters.get('config', {})
        accelerator = _get_msz_accelerator(config)
        connectivity_type = int(config.get('connectivityType', 0))
        
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
        
        compute_segmentation = bool(config.get('computeSegmentation', True))
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
        
        # Convert CriticalPoint objects to dictionaries
        # The C++ binding already provides x, y, z coordinates and values
        minima_points = []
        maxima_points = []
        saddles_points = []
        
        for cp_obj in minima_list:
            minima_points.append({
                'index': int(cp_obj.index),
                'x': int(cp_obj.x),
                'y': int(cp_obj.y),
                'z': int(cp_obj.z),
                'value': float(cp_obj.value)
            })
        
        for cp_obj in maxima_list:
            maxima_points.append({
                'index': int(cp_obj.index),
                'x': int(cp_obj.x),
                'y': int(cp_obj.y),
                'z': int(cp_obj.z),
                'value': float(cp_obj.value)
            })

        for cp_obj in saddles_list:
            saddles_points.append({
                'index': int(cp_obj.index),
                'x': int(cp_obj.x),
                'y': int(cp_obj.y),
                'z': int(cp_obj.z),
                'value': float(cp_obj.value)
            })

        res = {
            'type': 'critical_points',
            'minima': {
                'count': len(minima_points),
                'points': minima_points
            },
            'maxima': {
                'count': len(maxima_points),
                'points': maxima_points
            },
            'saddles': {
                'count': len(saddles_points),
                'points': saddles_points
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

        config = params.get('config', {})
        accelerator = _get_msz_accelerator(config)
        connectivity_type = int(config.get('connectivityType', 0))

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

        return {
            'status': 'success',
            'num_edits': len(edits),
            'corrected_data': final_corrected_data
        }

    except Exception as e:
        logger.error(f'Error applying correction: {e}')
        logger.error(traceback.format_exc())
        return {'error': f'Error applying correction: {e}'}


# Wrap all handlers with error handling to prevent crashes
METRIC_HANDLERS = {
    'power_spectrum': safe_handler(compute_power_spectrum),
    'histogram': safe_handler(compute_histogram),
    'statistics': safe_handler(compute_statistics),
    'entropy': safe_handler(compute_entropy),
    'correlation': safe_handler(compute_correlation),
    'wavelet': safe_handler(compute_wavelet),
    'critical_points': safe_handler(compute_critical_points),
    'critical_points_correction': safe_handler(apply_critical_points_correction),
}
