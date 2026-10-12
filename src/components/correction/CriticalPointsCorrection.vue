<template>
  <div class="critical-points-preservation">
    <div class="card-header bg-light py-2 px-3 border-bottom d-flex align-items-center justify-content-between">
      <div class="d-flex align-items-center gap-3">
        <h6 class="mb-0 text-muted small fw-bold">Preservation Filter</h6>
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

          <div class="mb-3">
            <label class="form-label text-muted small fw-semibold">Relative Error Bound (Per Variant)</label>
            <div class="input-group input-group-sm">
              <input
                v-if="variantConfigs[selectedVariantId]"
                type="number"
                class="form-control"
                v-model.number="variantConfigs[selectedVariantId].threshold"
                step="0.0001"
                min="0"
                max="1"
              />
              <input
                v-else
                type="number"
                class="form-control"
                v-model.number="localConfig.threshold"
                step="0.0001"
                min="0"
                max="1"
              />
              <button class="btn btn-outline-secondary" type="button" @click="resetToCompressorEB" title="Reset to compressor's error bound">
                <i class="bi bi-arrow-counterclockwise"></i>
              </button>
            </div>
            <div class="form-text">MSz fixes topological faults within this bound.</div>
          </div>

          <div class="row g-2">
            <div class="col-6 mb-3">
              <label class="form-label text-muted small fw-semibold">Connectivity</label>
              <select class="form-select form-select-sm" v-model.number="localConfig.connectivityType">
                <option :value="0">Linear (0)</option>
                <option :value="1">Full (1)</option>
              </select>
            </div>
            <div class="col-6 mb-3">
              <label class="form-label text-muted small fw-semibold">Accelerator</label>
              <select class="form-select form-select-sm" v-model="localConfig.accelerator">
                <option value="">None (CPU)</option>
                <option value="omp">OpenMP</option>
                <option value="cuda">CUDA</option>
              </select>
            </div>
          </div>

          <div class="mb-3">
            <label class="form-label d-block text-muted small fw-bold">Preserve Features (Global)</label>
            <div class="d-flex flex-wrap gap-3 p-2 border rounded bg-light-subtle">
              <div class="form-check form-check-inline small mb-0">
                <input class="form-check-input" type="checkbox" id="v-min" v-model="localConfig.preserveMin"/>
                <label class="form-check-label" for="v-min">Minima</label>
              </div>
              <div class="form-check form-check-inline small mb-0">
                <input class="form-check-input" type="checkbox" id="v-max" v-model="localConfig.preserveMax"/>
                <label class="form-check-label" for="v-max">Maxima</label>
              </div>
              <div class="form-check form-check-inline small mb-0">
                <input class="form-check-input" type="checkbox" id="v-path" v-model="localConfig.preservePath"/>
                <label class="form-check-label" for="v-path">Paths</label>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="d-flex align-items-center justify-content-center text-muted p-3" style="min-height: 300px;">
          <div class="text-center">
            <i class="bi bi-mouse2 fs-3 d-block mb-2"></i>
            <p>Select a compressor variant to configure its correction.</p>
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
            Apply to Selected ({{ checkedVariants.length }})
          </button>

          <button
            v-if="allVariants.length > 1"
            class="btn btn-outline-info"
            :disabled="status === 'running' || batchStatus.running"
            @click="applyBatchCorrection"
          >
            <i class="bi bi-stack me-1"></i>
            Batch Correct All ({{ allVariants.length }})
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
  name: 'CriticalPointsCorrection',
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
        threshold: 0.001,
        connectivityType: 0,
        accelerator: '',
        preserveMin: true,
        preserveMax: true,
        preservePath: false,
        ...this.config
      },
      selectedVariantId: null,
      variantConfigs: {}, // Map of variantId -> config object
      variantResults: {}, // Map of variantId -> status ('done', 'running', 'error')
      checkedVariants: [], // IDs of variants selected via checkbox
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
      const target = this.localConfig;
      return target && target.threshold >= 0 &&
             target.threshold <= 1 &&
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
      console.log('[CriticalPointsCorrection] Debug sourceNodeId:');
      console.log('  - compressedDataset:', this.compressedDataset);
      console.log('  - inputData:', this.inputData);
      console.log('  - comparisonData keys:', Object.keys(this.$store.state.comparisonData || {}));

      return this.getConfigBaseId();
    },
    allVariants() {
      const baseId = this.sourceNodeId;
      console.log('[CriticalPointsCorrection] Debug allVariants:');
      console.log('  - resolved baseId:', baseId);

      if (!baseId) {
        console.log('  - No baseId, returning empty array');
        return [];
      }

      const comparisonData = this.$store.state.comparisonData || {};
      const derivedMap = this.$store.state.derivedConfigurations?.[baseId] || {};
      console.log('  - comparisonData keys:', Object.keys(comparisonData));
      console.log('  - derivedMap keys:', Object.keys(derivedMap));
      const results = [];

      const baseResult = comparisonData[baseId];
      if (baseResult && !baseResult.error) {
        console.log('  - Adding base compressor:', baseId);
        results.push({
          id: baseId,
          isBase: true,
          ...baseResult
        });
      } else {
        console.log('  - Base compressor not found in comparisonData');
      }

      Object.keys(derivedMap).forEach(key => {
        const variant = comparisonData[key];
        if (variant && !variant.error && !results.some(r => r.id === key)) {
          console.log('  - Adding variant:', key);
          results.push({
            id: key,
            isBase: false,
            ...variant
          });
        }
      });

      console.log('  - Total variants found:', results.length);
      return results;
    },
    selectedVariant() {
      return this.allVariants.find(v => v.id === this.selectedVariantId) || null;
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
        console.log('  - Using direct config base:', directId);
        return directId;
      }

      if (directId) {
        const containingBase = Object.keys(derivedConfigurations).find(baseName => derivedConfigurations[baseName]?.[directId]);
        if (containingBase) {
          console.log('  - Mapped source node to containing base:', containingBase);
          return containingBase;
        }
      }

      if (compressed?.data_key) {
        const matchedSourceId = Object.keys(comparisonData).find(key => comparisonData[key].data_key === compressed.data_key);
        if (matchedSourceId) {
          const matched = comparisonData[matchedSourceId];
          if (matched?.base_name && (baseConfigurations[matched.base_name] || derivedConfigurations[matched.base_name])) {
            console.log('  - Resolved base from matched result:', matched.base_name);
            return matched.base_name;
          }
          const containingBase = Object.keys(derivedConfigurations).find(baseName => derivedConfigurations[baseName]?.[matchedSourceId]);
          if (containingBase) {
            console.log('  - Resolved base from matched variant:', containingBase);
            return containingBase;
          }
          if (baseConfigurations[matchedSourceId] || derivedConfigurations[matchedSourceId]) {
            console.log('  - Matched base by data_key:', matchedSourceId);
            return matchedSourceId;
          }
        }
      }

      const compressorId = compressed?.compressor_id;
      if (compressorId) {
        const matchingBases = Object.keys(baseConfigurations).filter(baseName => {
          return baseConfigurations[baseName]?.compressor_id === compressorId;
        });
        if (matchingBases.length === 1) {
          console.log('  - Resolved unique base by compressor:', matchingBases[0]);
          return matchingBases[0];
        }
      }

      console.log('  - Could not resolve config base id');
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

      // Look for specific error bound keys from SZ3 and ZFP
      if (config['sz3:abs_error_bound'] !== undefined) parts.push(`abs: ${config['sz3:abs_error_bound']}`);
      if (config['sz3:rel_error_bound'] !== undefined) parts.push(`rel: ${config['sz3:rel_error_bound']}`);
      if (config['zfp:accuracy'] !== undefined) parts.push(`acc: ${config['zfp:accuracy']}`);
      if (config['zfp:rate'] !== undefined) parts.push(`rate: ${config['zfp:rate']}`);
      return parts.join(' | ') || 'No config details';
    },
    getCorrectionStatus(id) {
      return this.variantResults[id] || null;
    },
    initializeVariantThreshold(id) {
      const v = this.allVariants.find(item => item.id === id);
      if (!v || !v.compressor_config) return;

      const cfg = v.compressor_config;
      let eb = null;

      // Propagate SZ3 error bounds
      if (v.compressor_id === 'sz3') {
        const mode = cfg['sz3:error_bound_mode_str'];
        if (mode === 'ABS' && cfg['sz3:abs_error_bound'] !== undefined) eb = Number(cfg['sz3:abs_error_bound']);
        else if (mode === 'REL' && cfg['sz3:rel_error_bound'] !== undefined) eb = Number(cfg['sz3:rel_error_bound']);
        else if (mode === 'PSNR' && cfg['sz3:psnr_error_bound'] !== undefined) eb = Number(cfg['sz3:psnr_error_bound']);
        // Fallback to any detected bound if mode is missing
        else eb = cfg['sz3:abs_error_bound'] || cfg['sz3:rel_error_bound'] || cfg['sz3:psnr_error_bound'] || null;
      }
      // Propagate ZFP accuracy
      else if (v.compressor_id === 'zfp') {
        if (cfg['zfp:accuracy'] !== undefined) eb = Number(cfg['zfp:accuracy']);
      }

      if (eb !== null) {
        this.variantConfigs = {
          ...this.variantConfigs,
          [id]: { ...this.variantConfigs[id], threshold: eb }
        };
      }
    },
    resetToCompressorEB() {
      if (this.selectedVariantId) {
        this.initializeVariantThreshold(this.selectedVariantId);
      }
    },
    toggleSelectAll() {
      if (this.allChecked) {
        this.checkedVariants = [];
      } else {
        this.checkedVariants = this.allVariants.map(v => v.id);
      }
    },
    emitConfigChange() {
      this.$emit('config-change', this.localConfig);
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
      this.statusMessage = `Processing ${ids.length} selected variants...`;

      for (const id of ids) {
        const variant = this.allVariants.find(v => v.id === id);
        if (!variant) {
          this.batchStatus.processed++;
          continue;
        }

        this.variantResults = { ...this.variantResults, [id]: 'running' };
        const vThreshold = this.variantConfigs[id]?.threshold ?? this.localConfig.threshold;

        try {
          const result = await this.runCorrectionTask(variant, this.nodeId, id, vThreshold);
          if (result) {
            this.variantResults = { ...this.variantResults, [id]: 'done' };
            this.batchStatus.results.push(id);
            const resultId = `${id}-corrected`;
            this.$store.commit('setComparisonData', { [resultId]: result });
          } else {
            this.variantResults = { ...this.variantResults, [id]: 'error' };
          }
        } catch (err) {
          this.variantResults = { ...this.variantResults, [id]: 'error' };
          console.error(`Error correcting variant ${id}:`, err);
        }

        this.batchStatus.processed++;
      }

      this.batchStatus.running = false;
      this.status = 'success';
      this.statusMessage = `Completed ${this.batchStatus.results.length}/${ids.length} corrections.`;

      if (this.batchStatus.results.length > 0) {
        this.$emit('success', {
          nodeId: this.nodeId,
          resultCount: this.batchStatus.results.length
        });
      }
    },
    async runCorrectionTask(dataset, nodeId, variantId = null, overrideThreshold = null) {
      if (!dataset || !this.originalDataset) return null;
      this.status = 'running';
      try {
        const formData = new FormData();
        // Consolidate shared settings with either variant-specific threshold or override
        const config = { ...this.localConfig };
        if (overrideThreshold !== null) {
          config.threshold = overrideThreshold;
        } else if (variantId && this.variantConfigs[variantId]) {
          config.threshold = this.variantConfigs[variantId].threshold;
        }

        formData.append('original_key', this.originalDataset.data_key || '');
        formData.append('compressed_key', dataset.data_key || '');
        formData.append('config', JSON.stringify(config));
        formData.append('metadata', JSON.stringify({
          ...(this.originalDataset.meta || this.originalDataset.dataset_meta || {}),
          compressed_metrics: dataset.metrics || {}
        }));

        const datasets = { [this.originalDataset.data_key]: this.originalDataset, [dataset.data_key]: dataset };
        const response = await requestWithFallback({ method: 'post', url: '/api/correction/critical_points', data: formData }, datasets);
        const result = response.data;
        if (result.error) throw new Error(result.error);
        if (result.data_key) {
          const dataResp = await requestWithFallback({ method: 'get', url: `/api/decompressed/${result.data_key}`, responseType: 'arraybuffer' }, {});
          result.decp_data = dataResp.data;
        }

        // Supplement the correction results with the original compressor's metrics
        result.metrics = {
          ...(dataset.metrics || {}),
          ...(result.metrics || {})
        };

        return { ...result, config, compressor_id: dataset.compressor_id, compressor_config: dataset.compressor_config };
      } catch (error) {
        this.status = 'error';
        this.statusMessage = error.message || 'Correction failed';
        return null;
      }
    },
    async applyBatchCorrection() {
      const vars = this.allVariants;
      this.batchStatus = { running: true, total: vars.length, processed: 0, results: [] };

      for (const v of vars) {
        this.selectedVariantId = v.id;
        const result = await this.runCorrectionTask(v, this.nodeId, v.id);
        if (result) {
          this.variantResults = { ...this.variantResults, [v.id]: 'done' };
          this.$store.commit('setComparisonData', { [`${v.id}-corrected`]: result });
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
        if (newVariants.length > 0) {
          if (!this.selectedVariantId) {
            this.selectedVariantId = newVariants[0].id;
          }
          // Initialize threshold for all variants if not already done
          newVariants.forEach(v => {
            if (!this.variantConfigs[v.id]) {
              this.initializeVariantThreshold(v.id);
            }
          });
        }
      }
    },
    selectedVariantId(id) {
      if (id && !this.variantConfigs[id]) {
        this.initializeVariantThreshold(id);
      }
    }
  }
};
</script>

<style scoped>
.critical-points-preservation {
  background: white;
}
.correction-content {
  min-height: 600px; /* Ensure enough height for the two-column layout */
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
.status-indicator {
  width: 20px;
  text-align: center;
}
</style>
