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
import { getDatasetMinMax, computeMinMax, toNumericArray } from '../../utils/datasetUtils.js';

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
      return getDatasetMinMax(ds || this.datasetBuffer, this.datasetPrecision, ds?.endianness || this.$store?.state?.dataset?.endianness);
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
      // Use the improved toNumericArray which now handles endianness
      const sourceData = toNumericArray(this.$store?.state?.dataset || this.datasetBuffer, this.datasetPrecision);
      if (!sourceData) {
        throw new Error('Dataset buffer unavailable.');
      }
      
      // Always use Float32Array for normalization results to avoid truncation
      const array = Float32Array.from(sourceData);

      // Re-compute range from the actual correct-endian numeric data to be absolutely sure
      const { min: srcMin, max: srcMax } = computeMinMax(array) || { min: 0, max: 1 };
      
      console.log(`[Normalization] Source precision: ${this.datasetPrecision}, endianness: ${this.$store?.state?.dataset?.endianness || 'little'}`);
      console.log(`[Normalization] Source range (computed from correct-endian data): [${srcMin}, ${srcMax}]`);
      
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

      // Final range check
      let actualMin = Infinity;
      let actualMax = -Infinity;
      for (let i = 0; i < array.length; i++) {
        const v = array[i];
        if (Number.isFinite(v)) {
          if (v < actualMin) actualMin = v;
          if (v > actualMax) actualMax = v;
        }
      }
      console.log(`[Normalization] Target range: [${targetMin}, ${targetMax}], Actual result range: [${actualMin}, ${actualMax}]`);

      const buffer = array.buffer;
      this.$store.commit('setFileData', {
        content: buffer,
        dimensions: Array.isArray(this.datasetDimensions) ? [...this.datasetDimensions] : null,
        precision: 'f', // Normalization output is now float32
        endianness: 'little', // Filtered result in JS is native endian (typically little)
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
    
    // Use the improved toNumericArray helper
    const sourceData = toNumericArray(dataset, dataset.precision, dataset.endianness);
    if (!sourceData) throw new Error('Failed to interpret source data');

    // Always use Float32Array for results to prevent truncation
    const resultData = Float32Array.from(sourceData);
    
    // Compute data range from correctly-interpreted data
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
      console.error('[Normalization Static] Invalid dataset range:', { srcMin, srcMax });
      throw new Error('Invalid dataset range for normalization');
    }
    
    console.log(`[Normalization Static] Source range: [${srcMin}, ${srcMax}], Target: [${targetMin}, ${targetMax}]`);
    
    // Apply normalization
    const scale = (targetMax - targetMin) / (srcMax - srcMin);
    for (let i = 0; i < resultData.length; i++) {
      const v = resultData[i];
      if (Number.isFinite(v)) {
        resultData[i] = targetMin + (v - srcMin) * scale;
      }
    }
    
    // Actual resulting range check
    let actualMin = Infinity;
    let actualMax = -Infinity;
    for (let i = 0; i < resultData.length; i++) {
      const v = resultData[i];
      if (Number.isFinite(v)) {
        if (v < actualMin) actualMin = v;
        if (v > actualMax) actualMax = v;
      }
    }
    console.log(`[Normalization Static] Result actual range: [${actualMin}, ${actualMax}]`);

    return {
      content: resultData.buffer,
      dimensions: dataset.dimensions,
      precision: 'f',
      endianness: 'little', // Result buffer is native endian
      name: dataset.name,
      type: dataset.type,
    };
  },
};
</script>
