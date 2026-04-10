<template>
  <div class="card shadow-sm">
    <div class="card-body">
      <div class="mb-3">
        <div class="gap-2 mb-2">
          <h5 class="card-title mb-2">Threshold Mask</h5>
          <p class="card-subtitle text-muted small mb-0">Mask out samples by replacing values that fall below, between, or above your thresholds.</p>
        </div>
        <div class="btn-group w-100 flex-wrap" role="group" aria-label="Threshold mode">
          <input
            type="radio"
            class="btn-check"
            name="thresholdMode"
            id="mode-below"
            autocomplete="off"
            value="below"
            :checked="mode === 'below'"
            @change="setMode('below')"
          />
          <label class="btn btn-outline-primary" for="mode-below">Below lower</label>

          <input
            type="radio"
            class="btn-check"
            name="thresholdMode"
            id="mode-between"
            autocomplete="off"
            value="between"
            :checked="mode === 'between'"
            @change="setMode('between')"
          />
          <label class="btn btn-outline-primary" for="mode-between">Between</label>

          <input
            type="radio"
            class="btn-check"
            name="thresholdMode"
            id="mode-above"
            autocomplete="off"
            value="above"
            :checked="mode === 'above'"
            @change="setMode('above')"
          />
          <label class="btn btn-outline-primary" for="mode-above">Above upper</label>
        </div>
      </div>

      <div class="row g-3">
        <div class="col-md-6">
          <label for="lowerThreshold" class="form-label">Lower threshold</label>
          <input
            id="lowerThreshold"
            type="number"
            step="any"
            class="form-control"
            :value="lower"
            @input="onLowerInput($event.target.value)"
            :disabled="mode === 'above'"
            :placeholder="lowerPlaceholder"
          />
        </div>
        <div class="col-md-6">
          <label for="upperThreshold" class="form-label">Upper threshold</label>
          <input
            id="upperThreshold"
            type="number"
            step="any"
            class="form-control"
            :value="upper"
            @input="onUpperInput($event.target.value)"
            :disabled="mode === 'below'"
            :placeholder="upperPlaceholder"
          />
        </div>
        <div class="col-12">
          <label for="replacementValue" class="form-label">Replacement value</label>
          <input
            id="replacementValue"
            type="number"
            step="any"
            class="form-control"
            :value="replacement"
            @input="onReplacementInput($event.target.value)"
            placeholder="Value to assign to matched samples"
          />
        </div>
      </div>

      <div class="mt-3 d-flex justify-content-between align-items-center">
        <div class="text-muted small">
          <template v-if="datasetSummary">
            Dataset: {{ datasetSummary.width }}×{{ datasetSummary.height }}×{{ datasetSummary.depth }} ({{ datasetSummary.precision || 'unknown' }})
          </template>
          <template v-else>
            No dataset summary available.
          </template>
        </div>
        <div class="d-flex align-items-center gap-2">
          <button
            type="button"
            class="btn btn-outline-secondary"
            @click="resetForm"
          >
            Reset
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!hasDataset || isApplying || !isFormValid"
            @click="applyThresholdMask"
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
import { getDatasetMinMax } from '../../utils/datasetUtils.js';

export default {
  name: 'DataThresholdMask',
  extends: BaseDataFilter,
  props: {
    filterName: {
      type: String,
      default: 'Threshold Mask',
    },
    filterType: {
      type: String,
      default: 'filter.threshold_mask',
    },
  },
  data() {
    return {
      mode: 'between',
      lower: null,
      upper: null,
      replacement: 0,
      autoRange: null,
    };
  },
  watch: {
    datasetBuffer: {
      immediate: true,
      handler() {
        this.syncThresholdsWithDataset();
      },
    },
    datasetPrecision() {
      this.syncThresholdsWithDataset();
    },
  },
  computed: {
    isFormValid() {
      if (!this.isFiniteNumber(this.replacement)) return false;
      if (this.mode === 'below') {
        return this.isFiniteNumber(this.lower);
      }
      if (this.mode === 'above') {
        return this.isFiniteNumber(this.upper);
      }
      // between
      return this.isFiniteNumber(this.lower) && this.isFiniteNumber(this.upper) && Number(this.lower) <= Number(this.upper);
    },
    lowerPlaceholder() {
      if (this.autoRange) return String(this.autoRange.min ?? '');
      return '0.0';
    },
    upperPlaceholder() {
      if (this.autoRange) return String(this.autoRange.max ?? '');
      return '1.0';
    },
  },
  methods: {
    syncThresholdsWithDataset() {
      if (!this.hasDataset) {
        this.autoRange = null;
        if (!this.formDirty) {
          this.lower = null;
          this.upper = null;
        }
        return;
      }
      const range = this.getDatasetRange();
      if (!range) {
        this.autoRange = null;
        return;
      }
      this.autoRange = range;
      if (!this.formDirty) {
        if (this.mode !== 'above') this.lower = range.min;
        if (this.mode !== 'below') this.upper = range.max;
      }
    },
    getDatasetRange() {
      // Try using store dataset object if available
      const ds = this.$store?.state?.dataset || null;
      const mm = getDatasetMinMax(ds || this.datasetBuffer, this.datasetPrecision);
      return mm; // { min, max } or null
    },
    setMode(next) {
      if (this.mode !== next) {
        this.mode = next;
        this.markDirty();
      }
    },
    onLowerInput(val) {
      const num = this.toNumberOrNull(val);
      this.lower = num;
      this.markDirty();
    },
    onUpperInput(val) {
      const num = this.toNumberOrNull(val);
      this.upper = num;
      this.markDirty();
    },
    resetForm() {
      this.lower = null;
      this.upper = null;
      this.replacement = 0;
      this.errorMessage = '';
      this.clearDirty();
      this.syncThresholdsWithDataset();
    },
    isFiniteNumber(val) {
      const num = Number(val);
      return Number.isFinite(num);
    },
    toNumberOrNull(val) {
      const num = Number(val);
      return Number.isFinite(num) ? num : null;
    },
    onReplacementInput(val) {
      const num = this.toNumberOrNull(val);
      this.replacement = num;
      this.markDirty();
    },

    applyThresholdMask() {
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

      this.applyOperation({
        mode: this.mode,
        lower: this.lower,
        upper: this.upper,
        replacement: this.replacement,
      }).catch((error) => {
        console.error('Failed to apply threshold mask:', error);
      });
    },

    async validateOperation() {
      // Ensure thresholds are set appropriately
      if (!this.hasDataset) return 'No dataset loaded.';
      if (!this.isFiniteNumber(this.replacement)) return 'Replacement value is required.';
      if (this.mode === 'below') {
        return this.isFiniteNumber(this.lower) ? true : 'Lower threshold is required.';
      }
      if (this.mode === 'above') {
        return this.isFiniteNumber(this.upper) ? true : 'Upper threshold is required.';
      }
      if (!this.isFiniteNumber(this.lower) || !this.isFiniteNumber(this.upper)) {
        return 'Lower and upper thresholds are required.';
      }
      if (Number(this.lower) > Number(this.upper)) {
        return 'Lower threshold must be less than or equal to upper threshold.';
      }
      return true;
    },

    async performOperation() {
      const sourceArray = this.toNumericArrayFromDataset();
      if (!sourceArray) {
        throw new Error('Dataset buffer unavailable.');
      }

      // Create a copy of the array to avoid mutating the original store data
      const array = sourceArray.slice();

      const lower = this.isFiniteNumber(this.lower) ? Number(this.lower) : -Infinity;
      const upper = this.isFiniteNumber(this.upper) ? Number(this.upper) : Infinity;
      const replacement = Number(this.replacement);
      const mode = this.mode;

      let affected = 0;
      const total = array.length;

      if (total > 0) {
        if (mode === 'below') {
          for (let i = 0; i < total; i++) {
            const v = array[i];
            if (Number.isFinite(v) && v < lower) {
              array[i] = replacement;
              affected++;
            }
          }
        } else if (mode === 'above') {
          for (let i = 0; i < total; i++) {
            const v = array[i];
            if (Number.isFinite(v) && v > upper) {
              array[i] = replacement;
              affected++;
            }
          }
        } else if (mode === 'between') {
          for (let i = 0; i < total; i++) {
            const v = array[i];
            if (Number.isFinite(v) && v >= lower && v <= upper) {
              array[i] = replacement;
              affected++;
            }
          }
        }
      }

      // Use the modified copy's buffer
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
        mode,
        lower: this.mode === 'above' ? null : (this.isFiniteNumber(this.lower) ? lower : null),
        upper: this.mode === 'below' ? null : (this.isFiniteNumber(this.upper) ? upper : null),
        replacement,
        affected,
        total,
        percent: total ? affected / total : 0,
        dimensions: Array.isArray(this.datasetDimensions) ? [...this.datasetDimensions] : null,
        range: this.getDatasetRange(),
      };
    },

    toNumericArrayFromDataset() {
      const buf = this.datasetBuffer;
      if (!buf) return null;
      try {
        // TypedArray
        if (ArrayBuffer.isView(buf)) {
          return buf;
        }
        // Raw ArrayBuffer
        if (buf instanceof ArrayBuffer) {
          const prec = this.datasetPrecision;
          if (prec === 'd') return new Float64Array(buf);
          return new Float32Array(buf);
        }
        // Plain array
        if (Array.isArray(buf)) {
          return Float64Array.from(buf);
        }
      } catch (_) {
        // Fall through
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
   * Pure function that applies threshold masking without side effects.
   * @param {Object} dataset - Current dataset { content, dimensions, precision }
   * @param {Object} params - Filter parameters { mode, lower, upper, replacement }
   * @returns {Promise<Object>} Filtered dataset
   */
  applyFilter: async function(dataset, params) {
    const { mode, lower, upper, replacement } = params;
    
    // Get TypedArray based on precision
    const precisionMap = {
      f: Float32Array,
      d: Float64Array,
      i8: Int8Array,
      u8: Uint8Array,
      i16: Int16Array,
      u16: Uint16Array,
      i32: Int32Array,
      u32: Uint32Array,
    };
    const TypedArray = precisionMap[dataset.precision] || Float32Array;
    const bytesPerElement = TypedArray.BYTES_PER_ELEMENT || 1;
    const buffer = (dataset.endianness === 'big' && bytesPerElement > 1)
      ? (() => {
          const src = new Uint8Array(dataset.content);
          const out = new Uint8Array(src.length);
          for (let i = 0; i < src.length; i += bytesPerElement) {
            for (let j = 0; j < bytesPerElement; j += 1) {
              out[i + j] = src[i + bytesPerElement - 1 - j];
            }
          }
          return out.buffer;
        })()
      : dataset.content;
    const sourceData = new TypedArray(buffer);
    const resultData = sourceData.slice(); // Create a copy
    
    const lowerThreshold = lower ?? -Infinity;
    const upperThreshold = upper ?? Infinity;
    const replaceValue = replacement ?? 0;
    
    // Apply threshold masking based on mode
    for (let i = 0; i < resultData.length; i++) {
      const v = resultData[i];
      if (!Number.isFinite(v)) continue;
      
      let shouldReplace = false;
      if (mode === 'below') {
        shouldReplace = v < lowerThreshold;
      } else if (mode === 'above') {
        shouldReplace = v > upperThreshold;
      } else if (mode === 'between') {
        shouldReplace = v >= lowerThreshold && v <= upperThreshold;
      }
      
      if (shouldReplace) {
        resultData[i] = replaceValue;
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

<style scoped>
.btn-group :deep(.btn) {
  min-width: 0;
}
</style>
