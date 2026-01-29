import numpy as np
import msz

def compute_power_spectrum_metric(data_array, parameters):
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
        'type': 'image',
        'src': f'data:image/png;base64,{img_base64}'
    }


def compute_histogram_metric(data_array, parameters):
    """Compute histogram of data values"""
    import base64
    from io import BytesIO
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    bins = parameters.get('bins', 50)
    
    plt.figure(figsize=(10, 6))
    plt.hist(data_array.flatten(), bins=bins, edgecolor='black', alpha=0.7)
    plt.xlabel('Value', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title('Data Histogram', fontsize=14)
    plt.grid(True, alpha=0.3)
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    return {
        'type': 'image',
        'src': f'data:image/png;base64,{img_base64}'
    }


def compute_statistics_metric(data_array, parameters):
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


def compute_entropy_metric(data_array, parameters):
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


def compute_correlation_metric(data_array, parameters):
    """Compute spatial autocorrelation"""
    max_lag = parameters.get('lag', 10)
    
    if len(data_array.shape) == 1:
        # 1D autocorrelation
        lags = range(0, min(max_lag + 1, len(data_array) // 2))
        correlations = []
        for lag in lags:
            if lag == 0:
                correlations.append(1.0)
            else:
                corr = np.corrcoef(data_array[:-lag], data_array[lag:])[0, 1]
                correlations.append(corr)
        
        table_data = [[lag, f'{corr:.6f}'] for lag, corr in zip(lags, correlations)]
        return {
            'type': 'table',
            'headers': ['Lag', 'Correlation'],
            'rows': table_data
        }
    else:
        return {
            'type': 'text',
            'content': 'Spatial correlation analysis is currently only supported for 1D data.'
        }


def compute_wavelet_metric(data_array, parameters):
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


METRIC_HANDLERS = {
    'power_spectrum': compute_power_spectrum_metric,
    'histogram': compute_histogram_metric,
    'statistics': compute_statistics_metric,
    'entropy': compute_entropy_metric,
    'correlation': compute_correlation_metric,
    'wavelet': compute_wavelet_metric,
}
