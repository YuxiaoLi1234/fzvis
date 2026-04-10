<template>
  <div class="ffcz-correction">
    <div class="card-header bg-light py-2 px-3 border-bottom d-flex align-items-center justify-content-between">
      <div class="d-flex align-items-center gap-3">
        <h6 class="mb-0 text-muted small fw-bold">FFCz Frequency Correction</h6>
        <div class="form-check small mb-0 ms-2" v-if="allVariants.length > 0">
          <input class="form-check-input" type="checkbox" id="selectAllVariants" :checked="allChecked" @change="toggleSelectAll">
          <label class="form-check-label text-muted" for="selectAllVariants">Select All</label>
        </div>
      </div>
      <div v-if="allVariants.length > 0" class="badge bg-secondary">{{ allVariants.length }} Variants</div>
    </div>

    <div class="row g-0 correction-content">
      <!-- Left Sidebar: Variant List -->
      <div class="col-4 border-end bg-light correction-sidebar">
        <div class="list-group list-group-flush">
          <div
            v-for="v in allVariants"
            :key="v.id"
            class="list-group-item list-group-item-action py-3 border-bottom d-flex align-items-center gap-3"
            :class="{ 'active': selectedVariantId === v.id }"
            @click="selectedVariantId = v.id"
          >
            <div class="form-check" @click.stop>
              <input
                class="form-check-input"
                type="checkbox"
                :value="v.id"
                v-model="checkedVariants"
                :id="`check-${v.id}`"
              >
            </div>
            <div class="flex-grow-1 overflow-hidden">
              <div class="d-flex align-items-center gap-2 mb-1">
                <i :class="['bi', v.isBase ? 'bi-check-circle-fill' : 'bi-layers', selectedVariantId === v.id ? 'text-white' : 'text-primary']"></i>
                <span class="fw-semibold text-truncate small">{{ getVariantLabel(v) }}</span>
              </div>
              <div class="small opacity-75 text-truncate" style="font-size: 0.75rem;">
                {{ getVariantConfigSummary(v) }}
              </div>
            </div>
            <div v-if="getCorrectionStatus(v.id)" class="status-indicator">
              <i class="bi bi-check-circle-fill text-success" v-if="getCorrectionStatus(v.id) === 'done'"></i>
              <div class="spinner-border spinner-border-sm text-info" v-if="getCorrectionStatus(v.id) === 'running'"></div>
              <i class="bi bi-exclamation-circle-fill text-danger" v-if="getCorrectionStatus(v.id) === 'error'"></i>
            </div>
          </div>
        </div>

        <div v-if="allVariants.length === 0" class="p-4 text-center text-muted">
          <i class="bi bi-link-45deg fs-2 d-block mb-2"></i>
          <p class="small">Connect a compressor node to see variants here.</p>
        </div>
      </div>

      <!-- Right Pane: Configuration Form -->
      <div class="col-8 bg-white correction-detail">
        <div v-if="selectedVariant" class="variant-config-form p-3">
          <div class="d-flex align-items-center justify-content-between mb-3 pb-2 border-bottom">
            <h6 class="mb-0 fw-bold">{{ getVariantLabel(selectedVariant) }}</h6>
            <span class="badge" :class="selectedVariant.isBase ? 'bg-primary' : 'bg-info'">{{ selectedVariant.isBase ? 'Base' : 'Variant' }}</span>
          </div>

          <!-- Spatial Error Bound -->
          <div class="mb-3">
            <label class="form-label text-muted small fw-semibold">Spatial Error Bound</label>
            <div class="row g-2">
              <div class="col-4">
                <select class="form-select form-select-sm" v-model="localConfig.spatial_mode">
                  <option value="REL">Relative</option>
                  <option value="ABS">Absolute</option>
                </select>
              </div>
              <div class="col-8">
                <div class="input-group input-group-sm">
                  <input
                    type="number"
                    class="form-control"
                    v-model.number="localConfig.spatial_value"
                    step="0.0001"
                    min="0"
                  />
                  <button class="btn btn-outline-secondary" type="button" @click="resetToCompressorEB" title="Reset to compressor's error bound">
                    <i class="bi bi-arrow-counterclockwise"></i>
                  </button>
                </div>
              </div>
            </div>
            <div class="form-text">Spatial error bound from the base compressor.</div>
          </div>

          <!-- Frequency Error Mode -->
          <div class="mb-3">
            <label class="form-label text-muted small fw-semibold">Frequency Error Mode</label>
            <select class="form-select form-select-sm" v-model="localConfig.freq_mode">
              <option value="REL">Relative</option>
              <option value="ABS">Absolute</option>
            </select>
            <div class="form-text">Error mode for frequency domain correction.</div>
          </div>

          <!-- Frequency Bounds -->
          <div class="mb-3">
            <label class="form-label text-muted small fw-semibold">Frequency Error Bounds (Sweep)</label>
            <div class="mb-2">
              <textarea
                class="form-control form-control-sm font-monospace"
                v-model="freqBoundsText"
                rows="3"
                placeholder="1e-5, 2e-5, 5e-5, 1e-4, 2e-4, 5e-4, 1e-3"
              ></textarea>
              <div class="form-text">Comma-separated list of frequency bounds to sweep.</div>
            </div>
            <div class="d-flex gap-2">
              <button class="btn btn-sm btn-outline-secondary" @click="setPreset('fine')">Fine Sweep</button>
              <button class="btn btn-sm btn-outline-secondary" @click="setPreset('coarse')">Coarse Sweep</button>
              <button class="btn btn-sm btn-outline-secondary" @click="setPreset('single')">Single (1e-4)</button>
            </div>
          </div>

          <!-- Return Corrected Data Option -->
          <div class="mb-3">
            <div class="form-check">
              <input
                class="form-check-input"
                type="checkbox"
                id="returnCorrectedData"
                v-model="localConfig.return_corrected_data"
              />
              <label class="form-check-label text-muted small fw-semibold" for="returnCorrectedData">
                Return corrected data for analysis
              </label>
            </div>
            <div v-if="localConfig.return_corrected_data" class="alert alert-warning mt-2 py-2 px-3 small mb-0">
              <i class="bi bi-exclamation-triangle me-1"></i>
              <strong>Storage Warning:</strong> Each frequency bound will generate a full corrected dataset.
              <span v-if="estimatedStorageSize">
                Estimated: ~{{ estimatedStorageSize }} per bound × {{ parseFreqBounds().length }} bounds = {{ totalEstimatedStorage }}
              </span>
            </div>
          </div>
        </div>

        <div v-else class="d-flex align-items-center justify-content-center text-muted p-3" style="min-height: 300px;">
          <div class="text-center">
            <i class="bi bi-mouse2 fs-3 d-block mb-2"></i>
            <p>Select a compressor variant to configure FFCz correction.</p>
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="px-3 pb-3 d-grid gap-2 correction-actions">
          <button
            class="btn btn-primary"
            @click="applyCorrectionToSelected"
            :disabled="!isAnyChecked || !isValid || status === 'running' || batchStatus.running"
          >
            <i class="bi bi-play-fill me-1"></i>
            Run FFCz Sweep for Selected ({{ checkedVariants.length }})
          </button>

          <button
            v-if="allVariants.length > 1"
            class="btn btn-outline-info"
            :disabled="status === 'running' || batchStatus.running"
            @click="applyBatchCorrection"
          >
            <i class="bi bi-stack me-1"></i>
            Batch Sweep All ({{ allVariants.length }})
          </button>

          <div v-if="batchStatus.running" class="mt-2">
            <div class="progress" style="height: 6px;">
              <div class="progress-bar progress-bar-striped progress-bar-animated bg-info" :style="{ width: (batchStatus.processed / batchStatus.total * 100) + '%' }"></div>
            </div>
            <div class="text-center small mt-1 text-muted">Processing {{ batchStatus.processed }}/{{ batchStatus.total }}</div>
          </div>

          <div v-if="statusMessage" class="mt-2 small px-2 py-1 rounded" :class="{'bg-success-subtle text-success': status === 'success', 'bg-danger-subtle text-danger': status === 'error', 'bg-warning-subtle text-warning': status === 'running'}">
            {{ statusMessage }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { requestWithFallback } from '@/utils/datasetUtils';

export default {
  name: 'FFCzCorrection',
  props: {
    config: {
      type: Object,
      default: () => ({})
    },
    nodeId: {
      type: String,
      required: true
    },
    inputData: {
      type: Object,
      default: () => ({})
    }
  },
  data() {
    return {
      localConfig: {
        spatial_mode: 'REL',
        spatial_value: 0.001,
        freq_mode: 'REL',
        freq_bounds: [1e-5, 2e-5, 5e-5, 1e-4, 2e-4, 5e-4, 1e-3],
        return_corrected_data: false,
        ...this.config
      },
      freqBoundsText: '',
      selectedVariantId: null,
      variantConfigs: {},
      variantResults: {},
      checkedVariants: [],
      status: null,
      statusMessage: '',
      batchStatus: {
        running: false,
        processed: 0,
        total: 0,
        results: []
      }
    };
  },
  computed: {
    allChecked() {
      return this.allVariants.length > 0 && this.checkedVariants.length === this.allVariants.length;
    },
    isAnyChecked() {
      return this.checkedVariants.length > 0;
    },
    isValid() {
      const bounds = this.parseFreqBounds();
      return bounds.length > 0 &&
             this.localConfig.spatial_value > 0 &&
             this.hasRequiredInputs;
    },
    hasRequiredInputs() {
      const in0 = this.inputData['in-0'];
      const orig = this.inputData['original'];
      return in0 && !in0.is_placeholder && orig && !orig.is_placeholder;
    },
    originalDataset() {
      return this.inputData['original'] || null;
    },
    compressedDataset() {
      return this.inputData['in-0'] || null;
    },
    sourceNodeId() {
      return this.getConfigBaseId();
    },
    allVariants() {
      const baseId = this.sourceNodeId;
      if (!baseId) return [];

      const comparisonData = this.$store.state.comparisonData || {};
      const derivedMap = this.$store.state.derivedConfigurations?.[baseId] || {};
      const results = [];

      const baseResult = comparisonData[baseId];
      if (baseResult && !baseResult.error) {
        results.push({
          id: baseId,
          isBase: true,
          ...baseResult
        });
      }

      Object.keys(derivedMap).forEach(key => {
        const variant = comparisonData[key];
        if (variant && !variant.error && !results.some(r => r.id === key)) {
          results.push({
            id: key,
            isBase: false,
            ...variant
          });
        }
      });

      return results;
    },
    selectedVariant() {
      return this.allVariants.find(v => v.id === this.selectedVariantId) || null;
    },
    estimatedStorageSize() {
      // Estimate storage size based on original dataset dimensions
      const orig = this.originalDataset;
      if (!orig || !orig.meta?.dimensions) return null;

      const dims = orig.meta.dimensions;
      const numElements = dims.reduce((a, b) => a * b, 1);
      const bytesPerElement = 4; // float32
      const sizeBytes = numElements * bytesPerElement;

      // Format size in human-readable format
      if (sizeBytes < 1024) return `${sizeBytes}B`;
      if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)}KB`;
      if (sizeBytes < 1024 * 1024 * 1024) return `${(sizeBytes / (1024 * 1024)).toFixed(1)}MB`;
      return `${(sizeBytes / (1024 * 1024 * 1024)).toFixed(2)}GB`;
    },
    totalEstimatedStorage() {
      if (!this.estimatedStorageSize) return null;
      const numBounds = this.parseFreqBounds().length;

      // Extract numeric value and unit from estimatedStorageSize
      const match = this.estimatedStorageSize.match(/^([\d.]+)(\w+)$/);
      if (!match) return `× ${numBounds} bounds`;

      const [, value, unit] = match;
      const total = parseFloat(value) * numBounds;
      return `~${total.toFixed(1)}${unit} total`;
    }
  },
  methods: {
    getConfigBaseId() {
      const compressed = this.compressedDataset;
      const comparisonData = this.$store.state.comparisonData || {};
      const baseConfigurations = this.$store.state.baseConfigurations || {};
      const derivedConfigurations = this.$store.state.derivedConfigurations || {};

      const directId = compressed?.base_name || compressed?.sourceNodeId || null;
      if (directId && (baseConfigurations[directId] || derivedConfigurations[directId])) {
        return directId;
      }

      if (directId) {
        const containingBase = Object.keys(derivedConfigurations).find(baseName => derivedConfigurations[baseName]?.[directId]);
        if (containingBase) {
          return containingBase;
        }
      }

      if (compressed?.data_key) {
        const matchedSourceId = Object.keys(comparisonData).find(key => comparisonData[key].data_key === compressed.data_key);
        if (matchedSourceId) {
          const matched = comparisonData[matchedSourceId];
          if (matched?.base_name && (baseConfigurations[matched.base_name] || derivedConfigurations[matched.base_name])) {
            return matched.base_name;
          }
          const containingBase = Object.keys(derivedConfigurations).find(baseName => derivedConfigurations[baseName]?.[matchedSourceId]);
          if (containingBase) {
            return containingBase;
          }
          if (baseConfigurations[matchedSourceId] || derivedConfigurations[matchedSourceId]) {
            return matchedSourceId;
          }
        }
      }

      return directId;
    },
    getVariantLabel(v) {
      if (v.isBase) return 'Current Base Setting';
      return v.id;
    },
    getVariantConfigSummary(v) {
      const config = v.compressor_config || {};
      const parts = [];
      if (v.compressor_id) parts.push(v.compressor_id.toUpperCase());

      if (config['sz3:abs_error_bound'] !== undefined) parts.push(`abs: ${config['sz3:abs_error_bound']}`);
      if (config['sz3:rel_error_bound'] !== undefined) parts.push(`rel: ${config['sz3:rel_error_bound']}`);
      if (config['zfp:accuracy'] !== undefined) parts.push(`acc: ${config['zfp:accuracy']}`);
      if (config['zfp:rate'] !== undefined) parts.push(`rate: ${config['zfp:rate']}`);
      return parts.join(' | ') || 'No config details';
    },
    getCorrectionStatus(id) {
      return this.variantResults[id] || null;
    },
    initializeVariantSpatialValue(id) {
      const v = this.allVariants.find(item => item.id === id);
      if (!v || !v.compressor_config) return;

      const cfg = v.compressor_config;
      let eb = null;

      if (v.compressor_id === 'sz3') {
        const mode = cfg['sz3:error_bound_mode_str'];
        if (mode === 'ABS' && cfg['sz3:abs_error_bound'] !== undefined) eb = Number(cfg['sz3:abs_error_bound']);
        else if (mode === 'REL' && cfg['sz3:rel_error_bound'] !== undefined) eb = Number(cfg['sz3:rel_error_bound']);
        else eb = cfg['sz3:abs_error_bound'] || cfg['sz3:rel_error_bound'] || null;
      } else if (v.compressor_id === 'zfp') {
        if (cfg['zfp:accuracy'] !== undefined) eb = Number(cfg['zfp:accuracy']);
      }

      if (eb !== null) {
        this.localConfig.spatial_value = eb;
      }
    },
    resetToCompressorEB() {
      if (this.selectedVariantId) {
        this.initializeVariantSpatialValue(this.selectedVariantId);
      }
    },
    parseFreqBounds() {
      const text = this.freqBoundsText.trim();
      if (!text) return [];

      const parts = text.split(',').map(s => s.trim()).filter(s => s.length > 0);
      const bounds = [];

      for (const part of parts) {
        const num = parseFloat(part);
        if (!isNaN(num) && num > 0) {
          bounds.push(num);
        }
      }

      return bounds;
    },
    setPreset(type) {
      if (type === 'fine') {
        this.freqBoundsText = '1e-5, 2e-5, 5e-5, 1e-4, 2e-4, 5e-4, 1e-3';
      } else if (type === 'coarse') {
        this.freqBoundsText = '1e-4, 5e-4, 1e-3';
      } else if (type === 'single') {
        this.freqBoundsText = '1e-4';
      }
    },
    toggleSelectAll() {
      if (this.allChecked) {
        this.checkedVariants = [];
      } else {
        this.checkedVariants = this.allVariants.map(v => v.id);
      }
    },
    async applyCorrectionToSelected() {
      if (this.checkedVariants.length === 0) return;

      const ids = [...this.checkedVariants];
      this.batchStatus = {
        running: true,
        total: ids.length,
        processed: 0,
        results: []
      };

      this.status = 'running';
      this.statusMessage = `Running FFCz sweep for ${ids.length} selected variants...`;

      for (const id of ids) {
        const variant = this.allVariants.find(v => v.id === id);
        if (!variant) {
          this.batchStatus.processed++;
          continue;
        }

        this.variantResults = { ...this.variantResults, [id]: 'running' };

        try {
          const results = await this.runFFCzSweep(variant, this.nodeId, id);
          if (results && results.length > 0) {
            this.variantResults = { ...this.variantResults, [id]: 'done' };
            this.batchStatus.results.push(id);

            // Store each frequency bound result as a separate comparison entry
            const comparisonUpdates = {};
            results.forEach((result) => {
              const resultId = `${id}-ffcz-${result.freq_bound}`;
              comparisonUpdates[resultId] = result;
            });
            this.$store.commit('setComparisonData', comparisonUpdates);
          } else {
            this.variantResults = { ...this.variantResults, [id]: 'error' };
          }
        } catch (err) {
          this.variantResults = { ...this.variantResults, [id]: 'error' };
          console.error(`Error running FFCz for variant ${id}:`, err);
        }

        this.batchStatus.processed++;
      }

      this.batchStatus.running = false;
      this.status = 'success';
      this.statusMessage = `Completed FFCz sweep for ${this.batchStatus.results.length}/${ids.length} variants.`;

      if (this.batchStatus.results.length > 0) {
        this.$emit('success', {
          nodeId: this.nodeId,
          resultCount: this.batchStatus.results.length
        });
      }
    },
    async runFFCzSweep(dataset, nodeId, variantId = null) {
      if (!dataset || !this.originalDataset) return null;

      this.status = 'running';
      try {
        const freq_bounds = this.parseFreqBounds();
        if (freq_bounds.length === 0) {
          throw new Error('No valid frequency bounds specified');
        }

        const formData = new FormData();
        const config = {
          spatial_mode: this.localConfig.spatial_mode,
          spatial_value: this.localConfig.spatial_value,
          freq_mode: this.localConfig.freq_mode,
          freq_bounds: freq_bounds,
          return_corrected_data: this.localConfig.return_corrected_data || false
        };

        formData.append('original_key', this.originalDataset.data_key || '');
        formData.append('compressed_key', dataset.data_key || '');
        formData.append('config', JSON.stringify(config));
        formData.append('metadata', JSON.stringify({
          ...(this.originalDataset.meta || this.originalDataset.dataset_meta || {}),
          compressed_metrics: dataset.metrics || {}
        }));

        const datasets = { [this.originalDataset.data_key]: this.originalDataset, [dataset.data_key]: dataset };
        const response = await requestWithFallback({ method: 'post', url: '/api/correction/ffcz', data: formData }, datasets);
        const result = response.data;

        if (result.error) throw new Error(result.error);

        // Transform results to match comparison data format
        const sweepResults = [];
        for (const r of result.results) {
          const sweepResult = {
            freq_bound: r.freq_bound,
            ffcz_bytes: r.ffcz_bytes,
            compression_ratio: r.compression_ratio,
            total_bytes: r.total_bytes,
            metrics: {
              ...(dataset.metrics || {}),
              ...(r.metrics || {})
            },
            compressor_id: dataset.compressor_id,
            compressor_config: dataset.compressor_config,
            base_variant_id: variantId
          };

          // Fetch corrected data if available
          if (r.data_key) {
            try {
              const dataResp = await requestWithFallback({
                method: 'get',
                url: `/api/decompressed/${r.data_key}`,
                responseType: 'arraybuffer'
              }, {});
              sweepResult.decp_data = dataResp.data;
              sweepResult.data_key = r.data_key;
            } catch (err) {
              console.warn(`Failed to fetch corrected data for freq_bound ${r.freq_bound}:`, err);
            }
          }

          sweepResults.push(sweepResult);
        }

        return sweepResults;
      } catch (error) {
        this.status = 'error';
        this.statusMessage = error.message || 'FFCz sweep failed';
        console.error('FFCz error:', error);
        return null;
      }
    },
    async applyBatchCorrection() {
      const vars = this.allVariants;
      this.batchStatus = { running: true, total: vars.length, processed: 0, results: [] };

      for (const v of vars) {
        this.selectedVariantId = v.id;
        const results = await this.runFFCzSweep(v, this.nodeId, v.id);
        if (results && results.length > 0) {
          this.variantResults = { ...this.variantResults, [v.id]: 'done' };

          const comparisonUpdates = {};
          results.forEach((result) => {
            const resultId = `${v.id}-ffcz-${result.freq_bound}`;
            comparisonUpdates[resultId] = result;
          });
          this.$store.commit('setComparisonData', comparisonUpdates);
          this.batchStatus.results.push(v.id);
        } else {
          this.variantResults = { ...this.variantResults, [v.id]: 'error' };
        }
        this.batchStatus.processed++;
      }

      this.batchStatus.running = false;
      this.status = 'success';
      this.statusMessage = `Batch complete: ${this.batchStatus.results.length}/${vars.length} succeeded.`;
    }
  },
  watch: {
    allVariants: {
      immediate: true,
      handler(newVariants) {
        if (newVariants.length > 0 && !this.selectedVariantId) {
          this.selectedVariantId = newVariants[0].id;
        }
      }
    },
    selectedVariantId(id) {
      if (id) {
        this.initializeVariantSpatialValue(id);
      }
    },
    'localConfig.freq_bounds': {
      immediate: true,
      handler(bounds) {
        if (Array.isArray(bounds)) {
          this.freqBoundsText = bounds.join(', ');
        }
      }
    }
  }
};
</script>

<style scoped>
.ffcz-correction {
  background: white;
}
.correction-content {
  min-height: 600px;
}
.correction-sidebar {
  max-height: 600px;
  overflow-y: auto;
}
.correction-detail {
  max-height: 600px;
  overflow-y: auto;
}
.variant-config-form {
  animation: fadeIn 0.3s ease-out;
}
.correction-actions {
  background: white;
  border-top: 1px solid #dee2e6;
  margin-top: 1rem;
  padding-top: 1rem;
}
.list-group-item.active {
  background-color: #0d6efd;
  border-color: #0d6efd;
}
.list-group-item {
  transition: all 0.2s;
  border-left: 4px solid transparent;
}
.list-group-item:hover:not(.active) {
  background-color: #f8f9fa;
  border-left-color: #dee2e6;
}
.list-group-item.active {
  border-left-color: #0a58ca;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
