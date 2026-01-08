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
