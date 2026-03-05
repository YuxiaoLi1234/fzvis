import axios from 'axios';
/**
 * Utilities for working with dataset buffers and metadata.
 */

/**
 * Convert a dataset or raw buffer into a numeric array.
 * Accepts:
 * - Vuex dataset object { content, precision }
 * - TypedArray
 * - ArrayBuffer (requires precision hint: 'f' for float32, 'd' for float64)
 * - Plain number[]
 * Returns a TypedArray or null if conversion fails.
 * @param {object|ArrayBuffer|Array|TypedArray|null} datasetOrBuffer
 * @param {'f'|'d'|undefined} precisionHint
 * @returns {Float32Array|Float64Array|TypedArray|null}
 */
export function toNumericArray(datasetOrBuffer, precisionHint) {
  if (!datasetOrBuffer) return null;
  try {
    // Vuex dataset object
    if (datasetOrBuffer && typeof datasetOrBuffer === 'object' && 'content' in datasetOrBuffer) {
      const buf = datasetOrBuffer.content;
      const prec = datasetOrBuffer.precision || precisionHint;
      return toNumericArray(buf, prec);
    }
    // TypedArray
    if (ArrayBuffer.isView(datasetOrBuffer)) {
      return datasetOrBuffer;
    }
    // Raw ArrayBuffer
    if (datasetOrBuffer instanceof ArrayBuffer) {
      const prec = precisionHint === 'd' ? 'd' : 'f';
      return prec === 'd' ? new Float64Array(datasetOrBuffer) : new Float32Array(datasetOrBuffer);
    }
    // Plain array
    if (Array.isArray(datasetOrBuffer)) {
      // Prefer Float64 for precision
      return Float64Array.from(datasetOrBuffer);
    }
  } catch (_) {
    // Fall through
  }
  return null;
}

/**
 * Compute min and max of a numeric array, ignoring non-finite values.
 * Returns null if no finite values are found.
 * @param {TypedArray|Array|null} arr
 * @returns {{min:number, max:number}|null}
 */
export function computeMinMax(arr) {
  if (!arr || !arr.length) return null;
  let min = Infinity;
  let max = -Infinity;
  let found = false;
  // Use indexed loop for performance on TypedArrays
  for (let i = 0; i < arr.length; i++) {
    const v = arr[i];
    if (Number.isFinite(v)) {
      found = true;
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  return found ? { min, max } : null;
}

/**
 * Convenience: get min/max directly from a dataset object or raw buffer.
 * @param {object|ArrayBuffer|Array|TypedArray|null} datasetOrBuffer
 * @param {'f'|'d'|undefined} precisionHint
 * @returns {{min:number, max:number}|null}
 */
export function getDatasetMinMax(datasetOrBuffer, precisionHint) {
  const arr = toNumericArray(datasetOrBuffer, precisionHint);
  return computeMinMax(arr);
}

/**
 * Executes an axios request with automatic data re-upload fallback if the server reports missing data keys.
 * 
 * @param {Object} config - Axios request config
 * @param {Object} datasets - Map of data_key -> { content: ArrayBuffer, meta: Object }
 * @returns {Promise<Object>} - Axios response
 */
export async function requestWithFallback(config, datasets = {}) {
  try {
    return await axios(config);
  } catch (err) {
    const data = err.response?.data;
    if (err.response?.status === 404 && data?.error === 'DATA_KEY_NOT_FOUND' && data?.missing_keys) {
      console.warn('[API] Cache miss detected for keys:', data.missing_keys);

      // Upload missing keys
      for (const key of data.missing_keys) {
        const ds = datasets[key];
        if (!ds || (!ds.content && !ds.decp_data)) {
          console.error(`[API] Cannot recover key ${key}: No binary data provided in datasets map.`);
          throw err; // Cannot recover
        }

        const formData = new FormData();
        formData.append('data_key', key);
        
        // Extract metadata from dataset object structure
        // Supports both nested metadata (ds.meta/ds.dataset_meta) and flat properties
        const metadata = ds.meta || ds.dataset_meta || {
          precision: ds.precision,
          dimensions: ds.dimensions,
          name: ds.name,
          type: ds.type
        };
        formData.append('metadata', JSON.stringify(metadata));

        const content = ds.decp_data || ds.content;
        const blob = new Blob([content], { type: 'application/octet-stream' });
        formData.append('data', blob, 'data.bin');

        console.log(`[API] Re-uploading missing data for key: ${key}`);
        await axios.post('/api/cache/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      // Retry the original request
      console.log('[API] Retrying original request...');
      return await axios(config);
    }

    // If not a cache miss, or recovery failed, rethrow
    throw err;
  }
}
