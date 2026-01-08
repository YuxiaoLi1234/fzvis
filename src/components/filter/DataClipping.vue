<template>
  <div class="data-clipping card shadow-sm">
    <div class="card-body">
      <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2 mb-3">
        <div>
          <h5 class="card-title mb-1">Clip Dataset</h5>
          <p class="card-subtitle text-muted small mb-0">Specify inclusive index ranges per axis.</p>
        </div>
        <div v-if="datasetSummary" class="text-muted small">
          Original size: {{ datasetSummary.width }} × {{ datasetSummary.height }} × {{ datasetSummary.depth }}
        </div>
      </div>

      <div v-if="!datasetSummary" class="alert alert-info mb-0">
        Load a dataset to enable clipping.
      </div>

      <form v-else @submit.prevent="applyClipping" class="d-flex flex-column gap-3">
        <div class="row g-3">
          <div
            v-for="field in dimensionFields"
            :key="field.key"
            class="col-12 col-md-4"
          >
            <div class="range-card border rounded h-100 p-3">
              <div class="d-flex justify-content-between align-items-baseline mb-2">
                <span class="fw-semibold">{{ field.label }}</span>
                <span class="text-muted small">
                  0 – {{ field.size > 0 ? field.size - 1 : 0 }}
                </span>
              </div>
              <div class="mb-2">
                <label class="form-label form-label-sm mb-1">Start</label>
                <input
                  type="number"
                  class="form-control form-control-sm"
                  :min="0"
                  :max="Math.max(field.size - 1, 0)"
                  v-model.number="ranges[field.key].start"
                  @input="onRangeInput(field.key)"
                >
              </div>
              <div>
                <label class="form-label form-label-sm mb-1">End (inclusive)</label>
                <input
                  type="number"
                  class="form-control form-control-sm"
                  :min="0"
                  :max="Math.max(field.size - 1, 0)"
                  v-model.number="ranges[field.key].end"
                  @input="onRangeInput(field.key)"
                >
              </div>
              <div class="text-muted small mt-3">
                Selection length: {{ Math.max(field.outputLength, 0) }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="validationError" class="alert alert-warning py-2 px-3 mb-0">
          {{ validationError }}
        </div>

        <div class="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-3">
          <div v-if="clippedDimensions" class="text-muted small">
            Result size: {{ clippedDimensions.width }} × {{ clippedDimensions.height }} × {{ clippedDimensions.depth }}
          </div>
          <div class="d-flex gap-2">
            <button
              type="button"
              class="btn btn-outline-secondary"
              @click="resetRanges"
              :disabled="isApplying"
            >
              Reset ranges
            </button>
            <button
              type="submit"
              class="btn btn-primary"
              :disabled="!canApply"
            >
              <span
                v-if="isApplying"
                class="spinner-border spinner-border-sm me-2"
                role="status"
                aria-hidden="true"
              ></span>
              Apply clipping
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import BaseDataFilter from './BaseDataFilter.vue';

export default {
  name: 'DataClipping',
  extends: BaseDataFilter,
  props: {
    filterName: {
      type: String,
      default: 'Clipping',
    },
  },
  data() {
    return {
      ranges: {
        width: { start: 0, end: 0 },
        height: { start: 0, end: 0 },
        depth: { start: 0, end: 0 },
      },
      isUpdatingRanges: false,
      originalDimensions: null,
    };
  },
  computed: {
    dimensionFields() {
      const summary = this.datasetSummary;
      const normalized = this.normalizedRanges;
      const base = [
        { key: 'width', label: 'Width (X)' },
        { key: 'height', label: 'Height (Y)' },
        { key: 'depth', label: 'Depth (Z)' },
      ];
      return base.map((entry) => {
        const size = summary ? Number(summary[entry.key]) || 0 : 0;
        const outputLength = normalized ? normalized[entry.key].length : 0;
        return {
          ...entry,
          size,
          outputLength,
        };
      });
    },
    normalizedRanges() {
      if (!this.datasetSummary) return null;
      return {
        width: this.normalizeRange(this.ranges.width, this.datasetSummary.width),
        height: this.normalizeRange(this.ranges.height, this.datasetSummary.height),
        depth: this.normalizeRange(this.ranges.depth, this.datasetSummary.depth),
      };
    },
    clippedDimensions() {
      if (!this.normalizedRanges) return null;
      return {
        width: this.normalizedRanges.width.length,
        height: this.normalizedRanges.height.length,
        depth: this.normalizedRanges.depth.length,
      };
    },
    validationError() {
      if (!this.datasetSummary) {
        return 'No dataset loaded.';
      }
      if (!this.normalizedRanges) {
        return 'Invalid clipping ranges.';
      }
      const issues = [];
      for (const field of this.dimensionFields) {
        if (field.size <= 0) {
          issues.push(`${field.label} has no data available.`);
        } else if (field.outputLength <= 0) {
          issues.push(`${field.label} range must include at least one value.`);
        }
      }
      return issues.length ? issues[0] : '';
    },
    canApply() {
      return Boolean(this.datasetSummary) && !this.validationError && !this.isApplying;
    },
  },
  watch: {
    datasetSummary: {
      handler(summary) {
        // Save the first seen dataset dimensions as the original baseline
        if (summary && !this.originalDimensions) {
          this.originalDimensions = {
            width: Number(summary.width) || 0,
            height: Number(summary.height) || 0,
            depth: Number(summary.depth) || 0,
          };
        }
        this.resetRanges();
      },
      immediate: true,
    },
    ranges: {
      deep: true,
      handler() {
        if (this.isUpdatingRanges) return;
        if (this.datasetSummary) {
          this.markDirty();
        }
      },
    },
  },
  methods: {
    onRangeInput(key) {
      if (!['width', 'height', 'depth'].includes(key)) return;
      const range = this.ranges[key];
      if (!range) return;
      range.start = this.toSafeIndex(range.start);
      range.end = this.toSafeIndex(range.end);
      if (!this.isUpdatingRanges) {
        this.markDirty();
      }
    },
    resetRanges(summaryOverride) {
      // Prefer original dimensions if available; else use provided summary or current
      const base = this.originalDimensions || summaryOverride || this.datasetSummary;
      const summary = base ? {
        width: Number(base.width) || 0,
        height: Number(base.height) || 0,
        depth: Number(base.depth) || 0,
      } : null;
      this.isUpdatingRanges = true;
      try {
        const defaults = {
          width: summary ? Math.max(Number(summary.width) - 1, 0) : 0,
          height: summary ? Math.max(Number(summary.height) - 1, 0) : 0,
          depth: summary ? Math.max(Number(summary.depth) - 1, 0) : 0,
        };
        for (const key of ['width', 'height', 'depth']) {
          if (!this.ranges[key]) {
            this.ranges[key] = { start: 0, end: defaults[key] };
          } else {
            this.ranges[key].start = 0;
            this.ranges[key].end = defaults[key];
          }
        }
      } finally {
        this.isUpdatingRanges = false;
      }
      this.clearDirty();
    },
    toSafeIndex(value) {
      const num = Number(value);
      if (!Number.isFinite(num)) return 0;
      return Math.max(0, Math.floor(num));
    },
    normalizeRange(range, size) {
      const sizeInt = Math.max(Number(size) || 0, 0);
      if (sizeInt <= 0) {
        return { start: 0, end: -1, length: 0 };
      }
      const maxIndex = sizeInt - 1;
      const rawStart = this.toSafeIndex(range?.start ?? 0);
      const rawEnd = this.toSafeIndex(range?.end ?? maxIndex);
      const clampedStart = Math.min(Math.max(rawStart, 0), maxIndex);
      const clampedEnd = Math.min(Math.max(rawEnd, 0), maxIndex);
      const start = Math.min(clampedStart, clampedEnd);
      const end = Math.max(clampedStart, clampedEnd);
      const length = end - start + 1;
      return { start, end, length };
    },
    cloneRanges(ranges) {
      if (!ranges) return null;
      return {
        width: { ...ranges.width },
        height: { ...ranges.height },
        depth: { ...ranges.depth },
      };
    },
    applyClipping() {
      if (!this.canApply || !this.normalizedRanges) return;
      const context = {
        ranges: this.cloneRanges(this.normalizedRanges),
        originalDimensions: this.datasetSummary
          ? { ...this.datasetSummary }
          : null,
      };
      this.applyOperation(context).catch((error) => {
        console.error('Failed to apply clipping:', error);
      });
    },
    getTypedArrayConstructor(precision) {
      const map = {
        f: Float32Array,
        d: Float64Array,
        i8: Int8Array,
        u8: Uint8Array,
        i16: Int16Array,
        u16: Uint16Array,
        i32: Int32Array,
        u32: Uint32Array,
      };
      return map[precision] || null;
    },
    validateOperation(context) {
      if (!this.datasetSummary) {
        return 'No dataset loaded.';
      }
      if (!context?.ranges) {
        return 'Missing clipping ranges.';
      }
      const ranges = context.ranges;
      if ([ranges.width, ranges.height, ranges.depth].some((r) => !r || r.length <= 0)) {
        return 'Each dimension must retain at least one element.';
      }
      return true;
    },
    async performOperation(context) {
      if (!this.datasetSummary) {
        throw new Error('Dataset summary unavailable.');
      }
      if (!this.datasetBuffer) {
        throw new Error('Dataset buffer is empty.');
      }
      const summary = this.datasetSummary;
      const { width, height, depth } = summary;
      const precision = this.datasetPrecision;
      const ctor = this.getTypedArrayConstructor(precision);
      if (!ctor) {
        throw new Error(`Unsupported precision "${precision}".`);
      }
      const expectedLength = width * height * depth;
      const source = new ctor(this.datasetBuffer);
      if (source.length < expectedLength) {
        throw new Error('Dataset buffer size does not match recorded dimensions.');
      }

      const widthRange = context.ranges.width;
      const heightRange = context.ranges.height;
      const depthRange = context.ranges.depth;

      const clippedWidth = widthRange.length;
      const clippedHeight = heightRange.length;
      const clippedDepth = depthRange.length;
      const resultLength = clippedWidth * clippedHeight * clippedDepth;

      const result = new ctor(resultLength);
      let destOffset = 0;
      const rowStride = width;
      const sliceStride = width * height;

      for (let z = depthRange.start; z <= depthRange.end; z += 1) {
        const sliceBase = z * sliceStride;
        for (let y = heightRange.start; y <= heightRange.end; y += 1) {
          const rowBase = sliceBase + y * rowStride + widthRange.start;
          const rowEnd = rowBase + clippedWidth;
          result.set(source.subarray(rowBase, rowEnd), destOffset);
          destOffset += clippedWidth;
        }
      }

      const newDimensions = [clippedWidth, clippedHeight, clippedDepth];
      this.$store.commit('setFileData', {
        content: result.buffer,
        dimensions: newDimensions,
        precision,
      });
      if (this.$store?.state?.comparisonData) {
        this.$store.commit('setComparisonData', null);
      }

      return {
        dimensions: newDimensions,
        ranges: this.cloneRanges(context.ranges),
        originalDimensions: context.originalDimensions,
      };
    },
    formatDimensions(dimensions) {
      if (!dimensions) return '';
      if (Array.isArray(dimensions)) {
        return dimensions.map((val) => `${val ?? '?'}`).join('×');
      }
      return [dimensions.width, dimensions.height, dimensions.depth]
        .map((val) => `${val ?? '?'}`)
        .join('×');
    },
    buildHistoryEntry(result, context) {
      const original = context?.originalDimensions || result?.originalDimensions;
      const newDims = result?.dimensions;
      let text = `${this.filterName} applied`;
      if (original && newDims) {
        text = `${this.filterName}: ${this.formatDimensions(original)} → ${this.formatDimensions(newDims)}`;
      }
      return {
        kind: this.filterType,
        text,
        timestamp: Date.now(),
        context: {
          ranges: this.cloneRanges(result?.ranges),
          originalDimensions: original ? { ...original } : null,
          newDimensions: newDims ? [...newDims] : null,
        },
        result: {
          dimensions: newDims ? [...newDims] : null,
        },
      };
    },
    buildSuccessStatusMessage(result) {
      const dims = result?.dimensions;
      if (dims) {
        return `${this.filterName} complete: ${this.formatDimensions(dims)} retained.`;
      }
      return `${this.filterName} completed successfully.`;
    },
  },
};
</script>

<style scoped>
.data-clipping .card-title {
  font-size: 1rem;
}
.range-card {
  background-color: #f8f9fa;
}
.form-label-sm {
  font-size: 0.75rem;
  font-weight: 600;
}
</style>
