<template>
  <div class="card shadow-sm">
    <div class="card-body">
      <div class="mb-3">
        <h5 class="card-title mb-2">Normalize Dataset</h5>
        <p class="card-subtitle text-muted small mb-0">
          Apply min-max normalization into your desired output range.
        </p>
      </div>

      <div class="row g-3">
        <div class="col-md-6">
          <label for="targetMin" class="form-label">Output minimum</label>
          <input
            id="targetMin"
            type="number"
            step="any"
            class="form-control"
            :value="targetMin"
            @input="onTargetMinInput($event.target.value)"
            :placeholder="targetMinPlaceholder"
          />
        </div>
        <div class="col-md-6">
          <label for="targetMax" class="form-label">Output maximum</label>
          <input
            id="targetMax"
            type="number"
            step="any"
            class="form-control"
            :value="targetMax"
            @input="onTargetMaxInput($event.target.value)"
            :placeholder="targetMaxPlaceholder"
          />
        </div>
      </div>

      <div class="mt-3 d-flex flex-column flex-md-row justify-content-between gap-3">
        <div class="text-muted small">
          <div v-if="datasetSummary">
            Dataset: {{ datasetSummary.width }}×{{ datasetSummary.height }}×{{ datasetSummary.depth }} ({{ datasetSummary.precision || 'unknown' }})
          </div>
          <div v-else>No dataset loaded.</div>
          <div v-if="autoRange" class="mt-1">
            Source range: [{{ autoRange.min }}, {{ autoRange.max }}]
          </div>
        </div>
        <div class="d-flex gap-2 justify-content-end">
          <button type="button" class="btn btn-outline-secondary" @click="resetForm" :disabled="isApplying">
            Reset
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!canApply"
            @click="applyNormalization"
          >
            Apply
          </button>
        </div>
      </div>

      <p v-if="errorMessage" class="text-danger small mt-2 mb-0">{{ errorMessage }}</p>
    </div>
  </div>
</template>

<script>
import BaseDataFilter from './BaseDataFilter.vue';
import { getDatasetMinMax, toNumericArray } from '../../utils/datasetUtils.js';

export default {
  name: 'DataNormalization',
  extends: BaseDataFilter,
  props: {
    filterName: {
      type: String,
      default: 'Normalization',
    },
    filterType: {
      type: String,
      default: 'filter.normalization',
    },
  },
  data() {
    return {
      targetMin: null,
      targetMax: null,
      autoRange: null,
    };
  },
  computed: {
    canApply() {
      return this.hasDataset && this.isFiniteNumber(this.targetMin) && this.isFiniteNumber(this.targetMax) && Number(this.targetMin) !== Number(this.targetMax) && !this.isApplying;
    },
    targetMinPlaceholder() {
      if (this.autoRange) return String(this.autoRange.min ?? 0);
      return '0.0';
    },
    targetMaxPlaceholder() {
      if (this.autoRange) return String(this.autoRange.max ?? 1);
      return '1.0';
    },
  },
  watch: {
    datasetBuffer: {
      immediate: true,
      handler() {
        this.computeAutoRange();
      },
    },
    datasetPrecision() {
      this.computeAutoRange();
    },
  },
  methods: {
    isFiniteNumber(val) {
      const num = Number(val);
      return Number.isFinite(num);
    },
    toNumberOrNull(val) {
      const num = Number(val);
      return Number.isFinite(num) ? num : null;
    },
    onTargetMinInput(val) {
      this.targetMin = this.toNumberOrNull(val);
      this.markDirty();
    },
    onTargetMaxInput(val) {
      this.targetMax = this.toNumberOrNull(val);
      this.markDirty();
    },
    resetForm() {
      this.targetMin = null;
      this.targetMax = null;
      this.errorMessage = '';
      this.clearDirty();
      this.computeAutoRange();
    },
    computeAutoRange() {
      if (!this.hasDataset) {
        this.autoRange = null;
        if (!this.formDirty) {
          this.targetMin = null;
          this.targetMax = null;
        }
        return;
      }
      const range = this.getDatasetRange();
      this.autoRange = range;
      if (!range) return;
      if (!this.formDirty) {
        this.targetMin = 0;
        this.targetMax = 1;
      }
    },
    getDatasetRange() {
      const ds = this.$store?.state?.dataset || null;
      return getDatasetMinMax(ds || this.datasetBuffer, this.datasetPrecision);
    },
    applyNormalization() {
      if (!this.canApply) return;
      if (this.$store && !this.$store.state.originalDataset && this.$store.state.dataset) {
        const current = this.$store.state.dataset;
        this.$store.commit('setOriginalDataset', {
          name: current.name ?? null,
          type: current.type ?? 'raw',
          content: current.content ?? null,
          dimensions: current.dimensions ?? null,
          precision: current.precision ?? null,
          size: current.size,
          vars: current.vars,
        });
      }
      const context = {
        targetMin: Number(this.targetMin),
        targetMax: Number(this.targetMax),
      };
      this.applyOperation(context).catch((error) => {
        console.error('Failed to apply normalization:', error);
      });
    },
    async validateOperation(context) {
      if (!this.hasDataset) return 'No dataset loaded.';
      if (!context || !this.isFiniteNumber(context.targetMin) || !this.isFiniteNumber(context.targetMax)) {
        return 'Both output bounds are required.';
      }
      if (Number(context.targetMin) === Number(context.targetMax)) {
        return 'Output min and max cannot be equal.';
      }
      const range = this.autoRange || this.getDatasetRange();
      if (!range || !Number.isFinite(range.min) || !Number.isFinite(range.max)) {
        return 'Unable to compute dataset range.';
      }
      if (range.min === range.max) {
        return 'Dataset range is zero; normalization is undefined.';
      }
      return true;
    },
    async performOperation(context) {
      const sourceArray = toNumericArray(this.$store?.state?.dataset, this.datasetPrecision)
        || toNumericArray(this.datasetBuffer, this.datasetPrecision)
        || this.toNumericArrayFromDataset();
      if (!sourceArray) {
        throw new Error('Dataset buffer unavailable.');
      }

      const array = typeof sourceArray.slice === 'function'
        ? sourceArray.slice()
        : Float64Array.from(sourceArray);

      const range = this.autoRange || this.getDatasetRange();
      const srcMin = range?.min;
      const srcMax = range?.max;
      if (!Number.isFinite(srcMin) || !Number.isFinite(srcMax) || srcMin === srcMax) {
        throw new Error('Invalid dataset range for normalization.');
      }

      const targetMin = Number(context.targetMin);
      const targetMax = Number(context.targetMax);
      const scale = (targetMax - targetMin) / (srcMax - srcMin);

      for (let i = 0; i < array.length; i++) {
        const v = array[i];
        if (Number.isFinite(v)) {
          array[i] = targetMin + (v - srcMin) * scale;
        } else {
          array[i] = v;
        }
      }

      const buffer = array.buffer;
      this.$store.commit('setFileData', {
        content: buffer,
        dimensions: Array.isArray(this.datasetDimensions) ? [...this.datasetDimensions] : null,
        precision: this.datasetPrecision,
        isFilterResult: true,
      });

      if (this.$store?.state?.comparisonData) {
        this.$store.commit('setComparisonData', null);
      }

      return {
        targetMin,
        targetMax,
        sourceRange: { min: srcMin, max: srcMax },
        dimensions: Array.isArray(this.datasetDimensions) ? [...this.datasetDimensions] : null,
      };
    },
    toNumericArrayFromDataset() {
      const buf = this.datasetBuffer;
      if (!buf) return null;
      try {
        if (ArrayBuffer.isView(buf)) {
          return buf;
        }
        if (buf instanceof ArrayBuffer) {
          return this.datasetPrecision === 'd' ? new Float64Array(buf) : new Float32Array(buf);
        }
        if (Array.isArray(buf)) {
          return Float64Array.from(buf);
        }
      } catch (_) {
        return null;
      }
      return null;
    },
    onFilterNodeDestroyed() {
      if (!this.$store) return;
      const original = this.$store.state.originalDataset;
      if (!original || !original.content) return;
      this.$store.commit('setFileData', {
        content: original.content,
        dimensions: original.dimensions,
        precision: original.precision,
        name: original.name,
        type: original.type,
      });
    },
  },
  
  /**
   * Static method for pipeline replay.
   * Pure function that applies normalization without side effects.
   * @param {Object} dataset - Current dataset { content, dimensions, precision }
   * @param {Object} params - Filter parameters { targetMin, targetMax }
   * @returns {Promise<Object>} Filtered dataset
   */
  applyFilter: async function(dataset, params) {
    const { targetMin, targetMax } = params;
    
    // Get TypedArray based on precision
    const TypedArray = dataset.precision === 'd' ? Float64Array : Float32Array;
    const sourceData = new TypedArray(dataset.content);
    const resultData = sourceData.slice(); // Create a copy
    
    // Compute data range
    let srcMin = Infinity;
    let srcMax = -Infinity;
    for (let i = 0; i < resultData.length; i++) {
      const v = resultData[i];
      if (Number.isFinite(v)) {
        if (v < srcMin) srcMin = v;
        if (v > srcMax) srcMax = v;
      }
    }
    
    if (!Number.isFinite(srcMin) || !Number.isFinite(srcMax) || srcMin === srcMax) {
      throw new Error('Invalid dataset range for normalization');
    }
    
    // Apply normalization
    const scale = (targetMax - targetMin) / (srcMax - srcMin);
    for (let i = 0; i < resultData.length; i++) {
      const v = resultData[i];
      if (Number.isFinite(v)) {
        resultData[i] = targetMin + (v - srcMin) * scale;
      }
    }
    
    return {
      content: resultData.buffer,
      dimensions: dataset.dimensions,
      precision: dataset.precision,
      name: dataset.name,
      type: dataset.type,
    };
  },
};
</script>
