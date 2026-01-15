<template>
  <div class="card shadow-sm">
    <div class="card-body">
      <div class="mb-3">
        <div class="gap-2 mb-2">
          <h5 class="card-title mb-2">Thresholding</h5>
          <p class="card-subtitle text-muted small mb-0">Choose a threshold mode.</p>
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
        <div class="col-6">
          <label for="lowerThreshold" class="form-label">Lower threshold</label>
          <input
            id="lowerThreshold"
            type="number"
            step="any"
            class="form-control"
            :value="lower"
            @input="onLowerInput($event.target.value)"
            :disabled="mode === 'above'"
            placeholder="0.0"
          />
        </div>
        <div class="col-6">
          <label for="upperThreshold" class="form-label">Upper threshold</label>
          <input
            id="upperThreshold"
            type="number"
            step="any"
            class="form-control"
            :value="upper"
            @input="onUpperInput($event.target.value)"
            :disabled="mode === 'below'"
            placeholder="1.0"
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
            @click="applyOperation({ mode, lower, upper })"
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
  name: 'DataThresholding',
  extends: BaseDataFilter,
  props: {
    filterName: {
      type: String,
      default: 'Threshold',
    },
    filterType: {
      type: String,
      default: 'filter.thresholding',
    },
  },
  data() {
    return {
      mode: 'between',
      lower: null,
      upper: null,
    };
  },
  computed: {
    isFormValid() {
      if (this.mode === 'below') {
        return this.isFiniteNumber(this.lower);
      }
      if (this.mode === 'above') {
        return this.isFiniteNumber(this.upper);
      }
      // between
      return this.isFiniteNumber(this.lower) && this.isFiniteNumber(this.upper) && Number(this.lower) <= Number(this.upper);
    },
  },
  methods: {
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
      this.errorMessage = '';
      this.clearDirty();
    },
    isFiniteNumber(val) {
      const num = Number(val);
      return Number.isFinite(num);
    },
    toNumberOrNull(val) {
      const num = Number(val);
      return Number.isFinite(num) ? num : null;
    },

    async validateOperation() {
      // Ensure thresholds are set appropriately
      if (!this.hasDataset) return 'No dataset loaded.';
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
      // Build a light-weight summary using the dataset buffer when available
      const arr = this.toNumericArrayFromDataset();
      let affected = 0;
      const total = arr ? arr.length : 0;
      const lower = Number(this.lower);
      const upper = Number(this.upper);

      if (arr && total > 0) {
        if (this.mode === 'below') {
          for (let i = 0; i < total; i++) {
            const v = arr[i];
            if (Number.isFinite(v) && v < lower) affected++;
          }
        } else if (this.mode === 'above') {
          for (let i = 0; i < total; i++) {
            const v = arr[i];
            if (Number.isFinite(v) && v > upper) affected++;
          }
        } else {
          for (let i = 0; i < total; i++) {
            const v = arr[i];
            if (Number.isFinite(v) && v >= lower && v <= upper) affected++;
          }
        }
      }

      return {
        mode: this.mode,
        lower: this.isFiniteNumber(this.lower) ? lower : null,
        upper: this.isFiniteNumber(this.upper) ? upper : null,
        affected,
        total,
        percent: total ? affected / total : 0,
        dimensions: Array.isArray(this.datasetDimensions) ? this.datasetDimensions : null,
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
  },
};
</script>

<style scoped>
.btn-group :deep(.btn) {
  min-width: 0;
}
</style>
