import axios from 'axios';

const BASE_URL = '/api';

/**
 * Fetch all saved/uploaded datasets from the server.
 * @returns {Promise<{datasets: Object}>}
 */
export async function listDatasets() {
  const response = await axios.get(`${BASE_URL}/listDatasets`);
  return response.data;
}

/**
 * Upload a new dataset or update dataset metadata.
 * @param {FormData} formData
 * @param {Function} [onUploadProgress]
 * @returns {Promise<{dataset: Object}>}
 */
export async function uploadDataset(formData, onUploadProgress) {
  const response = await axios.post(`${BASE_URL}/upload`, formData, {
    onUploadProgress,
  });
  return response.data;
}

/**
 * Update datasets state, such as deleting datasets or changing active dataset.
 * @param {FormData} formData
 * @returns {Promise<{datasets: Object}>}
 */
export async function updateDatasets(formData) {
  const response = await axios.post(`${BASE_URL}/updateDatasets`, formData);
  return response.data;
}

/**
 * Download raw dataset binary content.
 * @param {string} filename
 * @param {string} [filetype='raw']
 * @param {Function} [onDownloadProgress]
 * @returns {Promise<ArrayBuffer>}
 */
export async function downloadDataset(filename, filetype = 'raw', onDownloadProgress) {
  const response = await axios.get(`${BASE_URL}/download`, {
    params: { filename, filetype },
    responseType: 'arraybuffer',
    onDownloadProgress,
  });
  return response.data;
}

/**
 * Download a sliced NetCDF variable array from the server.
 * @param {Object} params
 * @param {string} params.filename
 * @param {string} params.variable
 * @param {Array<Object>} [params.slices]
 * @param {Function} [onDownloadProgress]
 * @returns {Promise<ArrayBuffer>}
 */
export async function downloadNetCDFVariable({ filename, variable, slices }, onDownloadProgress) {
  const response = await axios.get(`${BASE_URL}/download`, {
    params: {
      filename,
      filetype: 'netcdf',
      variable,
      slices: slices ? JSON.stringify(slices) : undefined,
    },
    responseType: 'arraybuffer',
    onDownloadProgress,
  });
  return response.data;
}

export default {
  listDatasets,
  uploadDataset,
  updateDatasets,
  downloadDataset,
  downloadNetCDFVariable,
};
