<template>
  <div class="container align-items-center">
    <h1 class="h4 px-2 mt-3">
      Decompressed Dataset
      <i
        type="button"
        class="bi bi-info-circle ms-2 fs-5"
        title="Upload a locally decompressed raw binary file to compare against the paired original dataset."
      ></i>
    </h1>

    <div v-if="!hasConnectedOriginal" class="alert alert-warning py-2 px-3 small mt-2">
      <i class="bi bi-plug me-1"></i>
      Connect an <strong>Original Data</strong> node to this node's input port before computing comparison stats.
    </div>

    <div v-else-if="originalDataset" class="alert alert-light border py-2 px-3 small mt-2">
      <div class="fw-semibold mb-1">Paired Original Dataset</div>
      <div>
        Name: <strong>{{ $maskDisplayPath(originalDataset.name || 'Unnamed') }}</strong>
        <span v-if="originalDimensions.length" class="ms-2 text-muted">
          ({{ originalDimensions.join(' × ') }})
        </span>
      </div>
      <div class="text-muted mt-1">
        Precision: <code>{{ originalDataset.precision || 'unknown' }}</code>
        <span class="ms-2">Endianness: <code>{{ originalDataset.endianness || 'little' }}</code></span>
        <span v-if="expectedByteLength" class="ms-2">Expected size: <code>{{ formatBytes(expectedByteLength) }}</code></span>
      </div>
    </div>

    <input
      ref="decompressedFileInput"
      type="file"
      multiple
      class="form-control mt-3 mb-2"
      id="decompressedFileLoader"
      @change="handleFileChange"
    >

    <div v-if="files.length > 0" class="mb-2">
      <div class="small text-muted mb-1">
        Selected {{ files.length }} {{ files.length === 1 ? 'file' : 'files' }}:
      </div>
      <ul class="list-group list-group-flush border rounded small">
        <li
          v-for="(f, idx) in files"
          :key="`${f.name}-${idx}`"
          class="list-group-item d-flex justify-content-between align-items-center py-1 px-2"
        >
          <span class="text-truncate me-2">{{ f.name }}</span>
          <span class="badge bg-secondary">{{ formatBytes(f.size) }}</span>
        </li>
      </ul>
    </div>

    <div v-if="fileSizeError" class="alert alert-danger py-1 px-2 small mb-2">
      <i class="bi bi-exclamation-triangle-fill me-1"></i>
      {{ fileSizeError }}
    </div>

    <div v-if="validationError" class="alert alert-danger py-1 px-2 small mb-2">
      <i class="bi bi-exclamation-triangle-fill me-1"></i>
      {{ validationError }}
    </div>

    <div class="form-text mb-2 text-muted small">
      <i class="bi bi-info-circle me-1"></i>Maximum file size: {{ maxUploadSizeFormatted }}.
    </div>

    <div class="row g-3 align-items-center my-2">
      <div class="col-md-6">
        <select class="form-select" aria-label="Decompressed precision" v-model="precision">
          <option value="" disabled>Data precision</option>
          <option value="f">float32 (f)</option>
          <option value="d">float64 (d)</option>
          <option value="i8">int8 (i8)</option>
          <option value="u8">uint8 (u8)</option>
          <option value="i16">int16 (i16)</option>
          <option value="u16">uint16 (u16)</option>
          <option value="i32">int32 (i32)</option>
          <option value="u32">uint32 (u32)</option>
        </select>
      </div>
      <div class="col-md-6">
        <select class="form-select" aria-label="Decompressed endianness" v-model="endianness">
          <option value="" disabled>Endianness</option>
          <option value="little">Little-endian</option>
          <option value="big">Big-endian</option>
        </select>
      </div>
    </div>

    <button
      type="button"
      class="btn btn-success my-2"
      @click="applyDecompressedData"
      :disabled="!canSubmit || isProcessing"
    >
      <span v-if="isProcessing" class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
      {{ existingEntry ? 'Update & Recompute' : 'Load Decompressed Data' }}
    </button>
    <button
      type="button"
      class="btn btn-info ms-2 my-2"
      @click="viewSavedDatasets"
      :disabled="!hasConnectedOriginal || isApplyingSelection || isLoadingDatasets || isProcessing"
      title="View all saved decompressed datasets on the server"
    >
      View datasets
    </button>

    <div v-if="isUploading" class="mt-2">
      <div class="d-flex justify-content-between small text-muted mb-1">
        <span>{{ uploadProgressMessage || 'Uploading...' }}</span>
        <span>{{ uploadProgress }}%</span>
      </div>
      <div class="progress" style="height: 8px;">
        <div
          class="progress-bar progress-bar-striped progress-bar-animated"
          role="progressbar"
          :style="{ width: `${uploadProgress}%` }"
          :aria-valuenow="uploadProgress"
          aria-valuemin="0"
          aria-valuemax="100"
        ></div>
      </div>
    </div>

    <div v-if="existingEntry" class="alert alert-success mt-2 small">
      Loaded: <strong>{{ existingEntry.name }}</strong>
    </div>
    <div v-if="multiUploadMessage" class="alert alert-info mt-2 small">
      <i class="bi bi-info-circle me-1"></i>{{ multiUploadMessage }}
    </div>

    <!-- Saved Decompressed Datasets Modal -->
    <div
      ref="decompressedDatasetModalRef"
      class="modal fade"
      data-bs-backdrop="static"
      tabindex="-1"
      aria-labelledby="decompressedDatasetModalLabel"
      aria-hidden="true"
    >
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h1 class="modal-title fs-5" id="decompressedDatasetModalLabel">Saved decompressed datasets</h1>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body overflow-auto" v-if="hasSavedDatasets">
            <div v-if="groupedSavedDatasets.length > 1" class="d-flex justify-content-end mb-2">
              <button
                type="button"
                class="btn btn-sm btn-outline-secondary"
                @click="toggleAllGroups"
              >
                {{ allGroupsExpanded ? 'Collapse all' : 'Expand all' }}
              </button>
            </div>
            <div
              v-for="group in groupedSavedDatasets"
              :key="group.key"
              class="card mb-2"
            >
              <div
                class="card-header d-flex justify-content-between align-items-center py-2 px-3"
                role="button"
                style="cursor: pointer;"
                @click="toggleGroup(group.key)"
              >
                <div class="d-flex align-items-center flex-wrap gap-2 text-break">
                  <i :class="['bi', expandedGroups[group.key] ? 'bi-chevron-down' : 'bi-chevron-right']"></i>
                  <span class="fw-semibold">{{ $maskDisplayPath(group.label) }}</span>
                  <span v-if="group.isCurrentOriginal" class="badge bg-success">Current</span>
                  <span v-if="group.dimensions.length" class="small text-muted">
                    ({{ group.dimensions.join(' × ') }})
                  </span>
                </div>
                <span class="badge bg-secondary ms-2">
                  {{ group.items.length }} {{ group.items.length === 1 ? 'file' : 'files' }}
                </span>
              </div>
              <ul v-if="expandedGroups[group.key]" class="list-group list-group-flush">
                <li
                  v-for="item in group.items"
                  :key="item.ds.name || item.key"
                  :class="[
                    'list-group-item',
                    'd-flex',
                    'justify-content-between',
                    'align-items-start',
                    {
                      active: item.ds.name === datasetToSelect?.name,
                      'list-group-item-danger': datasetsToDelete.includes(item.key)
                    }
                  ]"
                >
                  <div class="ms-2 me-auto">
                    <div :class="['fw-bold', 'text-break', { 'text-decoration-line-through': datasetsToDelete.includes(item.key) }]">
                      {{ $maskDisplayPath(item.ds.name) }}
                      <span v-if="item.ds.precision" class="badge bg-secondary ms-1">{{ formatPrecisionLabel(item.ds.precision) }}</span>
                      <span v-if="item.ds.size" class="badge bg-info ms-1">{{ item.ds.size }}</span>
                      <span v-if="item.ds.endianness" class="badge bg-light text-dark border ms-1">{{ item.ds.endianness }}</span>
                    </div>
                    <div v-if="Array.isArray(item.ds.dimensions) && item.ds.dimensions.length" class="small">
                      dimensions: ({{ item.ds.dimensions.join(' × ') }})
                    </div>
                  </div>
                  <div class="d-flex align-items-center">
                    <button
                      type="button"
                      class="btn btn-sm ms-2"
                      :class="item.ds.name === datasetToSelect?.name ? 'btn-primary' : 'btn-outline-primary'"
                      :title="item.ds.name === datasetToSelect?.name ? 'Selected dataset' : 'Select dataset'"
                      :disabled="datasetsToDelete.includes(item.key) || isApplyingSelection"
                      @click="selectSavedDataset(item.ds)"
                    >
                      <i :class="item.ds.name === datasetToSelect?.name ? 'bi bi-check-circle' : 'bi bi-circle'"></i>
                    </button>
                    <button
                      type="button"
                      class="ms-2 btn btn-sm"
                      :class="[datasetsToDelete.includes(item.key) ? 'btn-danger' : 'btn-outline-danger']"
                      :title="datasetsToDelete.includes(item.key) ? 'Undo delete' : 'Delete dataset'"
                      :hidden="datasetToSelect?.name === item.ds.name"
                      @click="toggleDeleteDataset(item.key)"
                    >
                      <i class="bi bi-trash"></i>
                    </button>
                  </div>
                </li>
              </ul>
            </div>
          </div>
          <div v-else class="modal-body">
            <p v-if="isLoadingDatasets" class="text-info mb-0">Loading decompressed datasets from server...</p>
            <p v-else class="text-warning mb-0">No saved decompressed datasets!</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            <button
              type="button"
              class="btn btn-primary"
              data-bs-dismiss="modal"
              @click="applySavedDatasetChanges"
              :disabled="isApplyingSelection || (!datasetToSelect && datasetsToDelete.length === 0)"
            >
              Save changes
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { Modal } from 'bootstrap';
import { toNumericArray, computeMinMax, generateUUID } from '@/utils/datasetUtils';
import {
  uploadDecompressedDataset,
  listDecompressedDatasets,
  updateDecompressedDatasets,
  downloadDecompressedDataset,
} from '@/api/datasets';

const BYTES_PER_ELEMENT = {
  f: 4,
  d: 8,
  i8: 1,
  u8: 1,
  i16: 2,
  u16: 2,
  i32: 4,
  u32: 4,
};

export default {
  name: 'DecompressedDataset',
  props: {
    nodeId: {
      type: String,
      required: true,
    },
    hasConnectedOriginal: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['decompressed-loaded', 'decompressed-error'],
  data() {
    return {
      files: [],
      precision: '',
      endianness: 'little',
      fileSizeError: null,
      validationError: null,
      isProcessing: false,
      isUploading: false,
      uploadProgress: 0,
      uploadProgressMessage: '',
      savedDatasets: {},
      expandedGroups: {},
      datasetToSelect: null,
      datasetsToDelete: [],
      isLoadingDatasets: false,
      isApplyingSelection: false,
      modalInstance: null,
      multiUploadMessage: null,
    };
  },
  computed: {
    originalDataset() {
      return this.$store?.state?.dataset || null;
    },
    originalDimensions() {
      const ds = this.originalDataset;
      if (!ds) return [];
      const dims = Array.isArray(ds.dimensions)
        ? ds.dimensions
        : [ds.width, ds.height, ds.depth];
      return dims.map(Number).filter(n => Number.isFinite(n) && n > 0);
    },
    expectedElementCount() {
      if (!this.originalDimensions.length) return 0;
      return this.originalDimensions.reduce((acc, d) => acc * d, 1);
    },
    expectedByteLength() {
      const bpe = BYTES_PER_ELEMENT[(this.precision || '').toLowerCase()];
      if (!bpe || !this.expectedElementCount) return 0;
      return this.expectedElementCount * bpe;
    },
    existingEntry() {
      return this.$store?.state?.comparisonData?.[this.nodeId] || null;
    },
    maxUploadSizeBytes() {
      return this.$store?.state?.maxUploadSizeBytes || (100 * 1024 * 1024);
    },
    maxUploadSizeFormatted() {
      return this.$store?.state?.maxUploadSizeFormatted || '100 MB';
    },
    canSubmit() {
      if (!this.hasConnectedOriginal || !this.originalDataset?.content) return false;
      if (this.fileSizeError || this.validationError) return false;
      if (!this.precision || !this.endianness) return false;
      return Boolean(this.files.length > 0 || this.existingEntry?.decp_data);
    },
    hasSavedDatasets() {
      return Object.keys(this.savedDatasets || {}).length > 0;
    },
    groupedSavedDatasets() {
      const groupsMap = new Map();
      const currentOriginalName = this.originalDataset?.name || '';

      Object.entries(this.savedDatasets || {}).forEach(([key, ds]) => {
        const origName = (ds?.original_name || '').trim();
        const groupKey = origName || '__ungrouped__';
        if (!groupsMap.has(groupKey)) {
          groupsMap.set(groupKey, {
            key: groupKey,
            label: origName || 'Ungrouped',
            items: [],
            dimensions: Array.isArray(ds?.dimensions) ? ds.dimensions : [],
            isCurrentOriginal: Boolean(origName && currentOriginalName && origName === currentOriginalName),
          });
        }
        groupsMap.get(groupKey).items.push({ key, ds });
      });

      const groups = Array.from(groupsMap.values());
      groups.forEach((g) => {
        g.items.sort((a, b) => (a.ds?.name || a.key).localeCompare(b.ds?.name || b.key));
      });
      groups.sort((a, b) => {
        if (a.isCurrentOriginal !== b.isCurrentOriginal) return a.isCurrentOriginal ? -1 : 1;
        if (a.key === '__ungrouped__') return 1;
        if (b.key === '__ungrouped__') return -1;
        return a.label.localeCompare(b.label);
      });
      return groups;
    },
    allGroupsExpanded() {
      const groups = this.groupedSavedDatasets;
      return groups.length > 0 && groups.every(g => Boolean(this.expandedGroups[g.key]));
    },
  },
  watch: {
    originalDataset: {
      immediate: true,
      handler(ds) {
        if (!this.precision && ds?.precision) {
          this.precision = ds.precision;
        }
        if (ds?.endianness) {
          this.endianness = ds.endianness;
        }
        this.validateSelectedFile();
      },
    },
    precision() {
      this.validateSelectedFile();
    },
  },
  mounted() {
    if (this.existingEntry) {
      this.precision = this.existingEntry.precision || this.originalDataset?.precision || '';
      this.endianness = this.existingEntry.endianness || this.originalDataset?.endianness || 'little';
    } else if (this.originalDataset) {
      this.precision = this.originalDataset.precision || '';
      this.endianness = this.originalDataset.endianness || 'little';
    }
    if (this.$refs.decompressedDatasetModalRef) {
      this.modalInstance = Modal.getOrCreateInstance(this.$refs.decompressedDatasetModalRef);
    }
  },
  beforeUnmount() {
    if (this.modalInstance) {
      this.modalInstance.hide();
      this.modalInstance.dispose();
      this.modalInstance = null;
    }
  },
  methods: {
    formatBytes(bytes) {
      if (!Number.isFinite(bytes) || bytes < 0) return '';
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let i = 0;
      let val = bytes;
      while (val >= 1024 && i < units.length - 1) {
        val /= 1024;
        i += 1;
      }
      return `${val.toFixed(2)} ${units[i]}`;
    },
    formatMetric(val) {
      if (!Number.isFinite(val)) return '-';
      if (Math.abs(val) >= 1000 || (Math.abs(val) > 0 && Math.abs(val) < 1e-3)) {
        return val.toExponential(3);
      }
      return val.toFixed(4);
    },
    handleFileChange(event) {
      const selectedFiles = Array.from(event.target.files || []);
      this.fileSizeError = null;
      this.validationError = null;
      this.multiUploadMessage = null;

      const oversized = selectedFiles.filter(f => f.size > this.maxUploadSizeBytes);
      if (oversized.length > 0) {
        const names = oversized.map(f => `${f.name} (${this.formatBytes(f.size)})`).join(', ');
        this.fileSizeError = `File size exceeds the maximum allowed limit of ${this.maxUploadSizeFormatted}: ${names}.`;
        this.files = [];
        event.target.value = '';
        return;
      }

      this.files = selectedFiles;
      this.validateSelectedFile();
    },
    validateSelectedFile() {
      this.validationError = null;
      if (!this.expectedByteLength) return;

      if (this.files.length > 0) {
        const mismatched = this.files.filter(f => f.size !== this.expectedByteLength);
        if (mismatched.length > 0) {
          const details = mismatched.map(f => `${f.name} (${this.formatBytes(f.size)})`).join(', ');
          this.validationError = `File size does not match expected size (${this.formatBytes(this.expectedByteLength)}) for ${this.originalDimensions.join(' × ')} with precision "${this.precision}": ${details}.`;
        }
        return;
      }

      const byteLength = this.existingEntry?.decp_data?.byteLength;
      if (!byteLength) return;
      if (byteLength !== this.expectedByteLength) {
        this.validationError = `File size (${this.formatBytes(byteLength)}) does not match expected size (${this.formatBytes(this.expectedByteLength)}) for ${this.originalDimensions.join(' × ')} with precision "${this.precision}".`;
      }
    },
    computeErrorMetrics(origBuffer, decpBuffer) {
      const origArr = toNumericArray(
        origBuffer,
        this.originalDataset?.precision,
        this.originalDataset?.endianness || 'little'
      );
      const decpArr = toNumericArray(decpBuffer, this.precision, this.endianness);
      if (!origArr || !decpArr) {
        throw new Error('Failed to decode numeric buffers for error metric computation.');
      }
      const len = Math.min(origArr.length, decpArr.length);
      if (len === 0) {
        throw new Error('Dataset contains zero elements.');
      }

      let sse = 0;
      let sae = 0;
      let maxAbsErr = 0;
      let maxRelErr = 0;
      let validCount = 0;
      let decpMin = Infinity;
      let decpMax = -Infinity;

      for (let i = 0; i < len; i += 1) {
        const o = Number(origArr[i]);
        const d = Number(decpArr[i]);
        if (!Number.isFinite(o) || !Number.isFinite(d)) continue;
        if (d < decpMin) decpMin = d;
        if (d > decpMax) decpMax = d;

        const err = Math.abs(o - d);
        if (err > maxAbsErr) maxAbsErr = err;
        sae += err;
        sse += err * err;

        if (o !== 0) {
          const relErr = err / Math.abs(o);
          if (relErr > maxRelErr) maxRelErr = relErr;
        }
        validCount += 1;
      }

      if (validCount === 0) {
        throw new Error('No finite elements found to compare.');
      }

      const mse = sse / validCount;
      const rmse = Math.sqrt(mse);
      const mae = sae / validCount;
      const minMax = computeMinMax(origArr);
      const origMin = minMax ? minMax.min : 0;
      const origMax = minMax ? minMax.max : 0;
      const range = origMax - origMin;
      const nrmse = range > 0 ? rmse / range : 0;
      const psnr = rmse > 0 && range > 0
        ? 20 * Math.log10(range / rmse)
        : (rmse === 0 ? Infinity : 0);

      const metrics = {
        'error:MSE': mse,
        'error:RMSE': rmse,
        'error:MAE': mae,
        'error:max_abs_error': maxAbsErr,
        'error:max_rel_error': maxRelErr,
        'error:NRMSE': nrmse,
        'stat:orig_min': origMin,
        'stat:orig_max': origMax,
        'stat:orig_range': range,
        'stat:decp_min': decpMin,
        'stat:decp_max': decpMax,
        'size:decompressed': decpBuffer.byteLength / 1024,
      };
      if (Number.isFinite(psnr)) {
        metrics['error:PSNR'] = psnr;
      }
      return metrics;
    },
    formatPrecisionLabel(prec) {
      const labels = {
        f: 'float32',
        d: 'float64',
        i8: 'int8',
        u8: 'uint8',
        i16: 'int16',
        u16: 'uint16',
        i32: 'int32',
        u32: 'uint32',
      };
      return labels[(prec || '').toLowerCase()] || prec;
    },
    initializeExpandedGroups() {
      const next = {};
      const groups = this.groupedSavedDatasets;
      const hasCurrent = groups.some(g => g.isCurrentOriginal);
      groups.forEach((g) => {
        if (hasCurrent) {
          next[g.key] = g.isCurrentOriginal;
        } else {
          next[g.key] = groups.length <= 2;
        }
      });
      this.expandedGroups = next;
    },
    toggleGroup(groupKey) {
      this.expandedGroups = {
        ...this.expandedGroups,
        [groupKey]: !this.expandedGroups[groupKey],
      };
    },
    toggleAllGroups() {
      const targetState = !this.allGroupsExpanded;
      const next = {};
      this.groupedSavedDatasets.forEach((g) => {
        next[g.key] = targetState;
      });
      this.expandedGroups = next;
    },
    async viewSavedDatasets() {
      this.datasetToSelect = null;
      this.datasetsToDelete = [];
      if (this.modalInstance) {
        this.modalInstance.show();
      }
      this.isLoadingDatasets = true;
      this.$store.commit('setProgress', { active: true, percent: 0, message: 'Loading decompressed datasets...' });
      this.$store.commit('setStatus', { type: 'info', message: 'Loading decompressed datasets from server...' });
      try {
        const res = await listDecompressedDatasets();
        this.savedDatasets = res?.datasets || {};
        this.initializeExpandedGroups();
        this.$store.commit('setProgress', { active: false, percent: 100, message: 'Decompressed datasets loaded' });
        this.$store.commit('setStatus', { type: 'success', message: 'Decompressed datasets loaded successfully!' });
      } catch (err) {
        this.$store.commit('setProgress', { active: false, percent: 0, message: 'Failed to load decompressed datasets' });
        this.$store.commit('setStatus', { type: 'danger', message: `Fetch decompressed datasets failed. ${err?.message || err}` });
        this.validationError = err?.response?.data?.error || err?.message || 'Failed to load saved decompressed datasets.';
      } finally {
        this.isLoadingDatasets = false;
      }
    },
    selectSavedDataset(ds) {
      if (this.datasetToSelect?.name === ds.name) {
        this.datasetToSelect = null;
      } else {
        this.datasetToSelect = ds;
      }
    },
    toggleDeleteDataset(key) {
      const idx = this.datasetsToDelete.indexOf(key);
      if (idx === -1) {
        this.datasetsToDelete.push(key);
      } else {
        this.datasetsToDelete.splice(idx, 1);
      }
    },
    async applySavedDatasetChanges() {
      this.isApplyingSelection = true;
      this.validationError = null;
      try {
        if (this.datasetsToDelete.length > 0) {
          this.$store.commit('setProgress', { active: true, percent: 0, message: 'Saving decompressed dataset changes...' });
          this.$store.commit('setStatus', { type: 'info', message: 'Saving decompressed dataset changes...' });
          const formData = new FormData();
          formData.append('deletedDatasets', JSON.stringify(this.datasetsToDelete));
          const res = await updateDecompressedDatasets(formData);
          this.savedDatasets = res?.datasets || {};
          this.datasetsToDelete = [];
          this.$store.commit('setProgress', { active: false, percent: 100, message: 'Changes saved' });
          this.$store.commit('setStatus', { type: 'success', message: 'Decompressed dataset changes saved!' });
        }

        if (this.datasetToSelect) {
          const selected = this.datasetToSelect;
          const nextPrecision = selected.precision || this.precision || this.originalDataset?.precision || 'f';
          const nextEndianness = selected.endianness || this.endianness || this.originalDataset?.endianness || 'little';
          this.precision = nextPrecision;
          this.endianness = nextEndianness;

          this.$store.commit('setProgress', { active: true, percent: 0, message: 'Downloading decompressed dataset...' });
          this.$store.commit('setStatus', { type: 'info', message: 'Downloading decompressed dataset...' });

          const buffer = await downloadDecompressedDataset(selected.name, (eventData) => {
            if (eventData.lengthComputable) {
              const percentComplete = Math.round((eventData.loaded / eventData.total) * 100);
              this.$store.commit('setProgress', { active: true, percent: percentComplete, message: `Downloading... ${percentComplete}%` });
            }
          });
          await this.commitLoadedBuffer({
            buffer,
            name: selected.name,
            precision: nextPrecision,
            endianness: nextEndianness,
            serverPath: selected.path || null,
          });
          this.$store.commit('setProgress', { active: false, percent: 100, message: 'Download complete' });
          this.$store.commit('setStatus', { type: 'success', message: 'Downloaded decompressed file successfully!' });
          this.datasetToSelect = null;
        }
      } catch (err) {
        const message = err?.response?.data?.error || err?.message || 'Failed to apply saved decompressed dataset changes.';
        this.$store.commit('setProgress', { active: false, percent: 0, message: 'Operation failed' });
        this.$store.commit('setStatus', { type: 'danger', message });
        this.validationError = message;
        this.$emit('decompressed-error', { nodeId: this.nodeId, error: message });
      } finally {
        this.isApplyingSelection = false;
      }
    },
    async commitLoadedBuffer({ buffer, name, precision, endianness, serverPath = null }) {
      const bpe = BYTES_PER_ELEMENT[(precision || '').toLowerCase()];
      const expectedBytes = (bpe && this.expectedElementCount) ? (this.expectedElementCount * bpe) : 0;
      if (expectedBytes && buffer.byteLength !== expectedBytes) {
        throw new Error(
          `File size (${this.formatBytes(buffer.byteLength)}) does not match expected size (${this.formatBytes(expectedBytes)}).`
        );
      }

      const metrics = this.computeErrorMetrics(this.originalDataset.content, buffer);

      this.$store.commit('setComparisonData', {
        [this.nodeId]: {
          name,
          compressor_id: 'direct_upload',
          data_key: generateUUID(),
          decp_data: buffer,
          content: buffer,
          precision,
          endianness,
          dimensions: this.originalDimensions,
          metrics,
          serverPath,
          is_local_decompressed: true,
          timestamp: Date.now(),
        },
      });

      this.$store.commit('addHistory', {
        kind: 'dataset',
        text: `Loaded decompressed data: ${name}`,
        timestamp: Date.now(),
      });

      this.files = [];
      if (this.$refs.decompressedFileInput) {
        this.$refs.decompressedFileInput.value = '';
      }
      this.$emit('decompressed-loaded', {
        nodeId: this.nodeId,
        name,
        precision,
        endianness,
        dimensions: this.originalDimensions,
        metrics,
        byteLength: buffer.byteLength,
      });
    },
    async applyDecompressedData() {
      if (!this.canSubmit) return;
      this.isProcessing = true;
      this.validationError = null;
      this.multiUploadMessage = null;
      try {
        if (this.files.length > 0) {
          const total = this.files.length;
          let primaryPayload = null;
          this.isUploading = true;
          this.uploadProgress = 0;

          for (let i = 0; i < total; i += 1) {
            const currentFile = this.files[i];
            const progressLabel = total > 1
              ? `Uploading (${i + 1}/${total}): ${currentFile.name}`
              : `Uploading ${currentFile.name}...`;

            this.uploadProgressMessage = progressLabel;
            this.$store.commit('setProgress', { active: true, percent: Math.round((i / total) * 100), message: progressLabel });
            this.$store.commit('setStatus', { type: 'info', message: progressLabel });

            const formData = new FormData();
            formData.append('file', currentFile);
            formData.append('precision', this.precision);
            formData.append('endianness', this.endianness);
            formData.append('dimensions', JSON.stringify(this.originalDimensions));
            formData.append('original_name', this.originalDataset?.name || '');
            formData.append('node_id', this.nodeId);

            const uploadRes = await uploadDecompressedDataset(formData, (eventData) => {
              if (eventData.lengthComputable) {
                const filePercent = Math.round((eventData.loaded / eventData.total) * 100);
                const overallPercent = Math.round(((i + filePercent / 100) / total) * 100);
                this.uploadProgress = overallPercent;
                this.uploadProgressMessage = total > 1
                  ? `Uploading (${i + 1}/${total}): ${currentFile.name}`
                  : `Uploading ${currentFile.name}...`;
                this.$store.commit('setProgress', {
                  active: true,
                  percent: overallPercent,
                  message: total > 1
                    ? `Uploading (${i + 1}/${total})... ${filePercent}%`
                    : `Uploading... ${filePercent}%`,
                });
              }
            });

            if (i === 0) {
              const buffer = await currentFile.arrayBuffer();
              primaryPayload = {
                buffer,
                name: currentFile.name,
                precision: this.precision,
                endianness: this.endianness,
                serverPath: uploadRes?.dataset?.path || null,
              };
            }
          }

          this.uploadProgress = 100;
          this.isUploading = false;
          this.uploadProgressMessage = '';
          this.$store.commit('setProgress', { active: false, percent: 100, message: 'Upload complete' });
          this.$store.commit('setStatus', {
            type: 'success',
            message: total > 1
              ? `Uploaded ${total} decompressed files successfully!`
              : 'Uploaded decompressed file successfully!',
          });

          if (primaryPayload) {
            await this.commitLoadedBuffer(primaryPayload);
          }
          if (total > 1) {
            this.multiUploadMessage = `Uploaded ${total} files to server and loaded "${primaryPayload.name}" into this node. Use "View datasets" to switch files.`;
          }
          return;
        }

        await this.commitLoadedBuffer({
          buffer: this.existingEntry.decp_data,
          name: this.existingEntry?.name || 'Decompressed Data',
          precision: this.precision,
          endianness: this.endianness,
          serverPath: this.existingEntry?.serverPath || null,
        });
      } catch (err) {
        const message = err?.message || 'Failed to load decompressed data.';
        this.validationError = message;
        this.$emit('decompressed-error', { nodeId: this.nodeId, error: message });
      } finally {
        this.isProcessing = false;
        this.isUploading = false;
        this.uploadProgress = 0;
        this.uploadProgressMessage = '';
      }
    },
  },
};
</script>

