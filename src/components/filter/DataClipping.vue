<template>
  <div class="data-clipping card shadow-sm">
    <div class="card-body pt-2">
      <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2 mb-2">
        <div>
          <h5 class="card-title mb-2">Clip Dataset</h5>
          <p class="card-subtitle text-muted small mb-0">Specify index ranges per dimension.<br/>[start, end)</p>
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
                  [0 – {{ field.size > 0 ? field.size : 0 }})
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
                <label class="form-label form-label-sm mb-1">End (exclusive)</label>
                <input
                  type="number"
                  class="form-control form-control-sm"
                  :min="0"
                  :max="field.size"
                  v-model.number="ranges[field.key].end"
                  @input="onRangeInput(field.key)"
                >
              </div>
              <div class="text-muted small mt-3">
                Length: {{ Math.max(field.outputLength, 0) }}
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
              type="button"
              class="btn btn-outline-info"
              @click="openPreview"
              :disabled="!canApply"
            >
              <i class="bi bi-eye me-1"></i>Preview
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

      <!-- Preview Modal -->
      <div
        v-if="showPreview"
        class="modal fade show d-block"
        tabindex="-1"
        role="dialog"
        @click.self="closePreview"
      >
        <div class="modal-dialog modal-xl modal-dialog-centered" role="document">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Clipping Preview</h5>
              <button type="button" class="btn-close" @click="closePreview" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div v-if="previewData && datasetSummary">
                <!-- Slice Selector -->
                <div class="mb-3">
                  <div class="d-flex justify-content-between align-items-center mb-2">
                    <label class="form-label mb-0">
                      <strong>Depth Slice:</strong> {{ previewSliceIndex }} / {{ maxSliceIndex }}
                    </label>
                    <div class="d-flex align-items-center gap-2">
                      <small class="text-muted">
                        Clipping: [{{ normalizedRanges.depth.start }} – {{ normalizedRanges.depth.end }})
                      </small>
                      <span
                        v-if="previewSliceIndex >= normalizedRanges.depth.start &&
                              previewSliceIndex < normalizedRanges.depth.end"
                        class="badge bg-success"
                      >
                        <i class="bi bi-check-circle me-1"></i>Inside clipping range
                      </span>
                      <span v-else class="badge bg-danger">
                        <i class="bi bi-x-circle me-1"></i>Outside clipping range
                      </span>
                    </div>
                  </div>
                  <input
                    type="range"
                    class="form-range"
                    :min="0"
                    :max="maxSliceIndex"
                    v-model.number="previewSliceIndex"
                    @input="updatePreviewSlice"
                  />
                  <div class="text-muted small mt-2 text-center">
                    <i class="bi bi-hand-index me-1"></i>
                    Click and drag on the image to select clipping region
                  </div>
                </div>

                <!-- Data Visualization -->
                <div class="preview-visualization-container">
                  <div class="position-relative d-inline-block">
                    <canvas
                      ref="previewCanvas"
                      class="preview-canvas"
                      :class="{ 'canvas-drawing': isDrawing }"
                      @mousedown="onCanvasMouseDown"
                      @mousemove="onCanvasMouseMove"
                      @mouseup="onCanvasMouseUp"
                      @mouseleave="onCanvasMouseLeave"
                      @load="renderPreviewCanvas"
                    ></canvas>

                    <!-- Active drawing selection -->
                    <div
                      v-if="getActiveSelectionBox()"
                      class="drawing-selection-overlay"
                      :style="{
                        left: getActiveSelectionBox().x + '%',
                        top: getActiveSelectionBox().y + '%',
                        width: getActiveSelectionBox().width + '%',
                        height: getActiveSelectionBox().height + '%',
                      }"
                    >
                      <div class="drawing-selection-border"></div>
                    </div>

                    <!-- Clipping box overlay (when not drawing) -->
                    <div
                      v-if="!isDrawing && clippingBoxCoordinates"
                      class="clipping-box-overlay"
                      :style="{
                        left: clippingBoxCoordinates.x + '%',
                        top: clippingBoxCoordinates.y + '%',
                        width: clippingBoxCoordinates.width + '%',
                        height: clippingBoxCoordinates.height + '%',
                      }"
                    >
                      <div class="clipping-box-border"></div>
                      <div class="clipping-box-label">
                        Clipped Region
                      </div>
                    </div>

                  </div>
                </div>

                <!-- Data Range Info -->
                <div class="mt-3">
                  <div class="row g-2">
                    <div class="col-md-4">
                      <div class="small">
                        <strong>Data Range:</strong>
                        {{ previewData.min.toExponential(3) }} to {{ previewData.max.toExponential(3) }}
                      </div>
                    </div>
                    <div class="col-md-4 text-center">
                      <div v-if="isDrawing && selectionStart && selectionCurrent" class="small text-success fw-semibold">
                        <i class="bi bi-cursor me-1"></i>
                        Drawing: {{ Math.abs(selectionCurrent.x - selectionStart.x) + 1 }} ×
                        {{ Math.abs(selectionCurrent.y - selectionStart.y) + 1 }}
                      </div>
                    </div>
                    <div class="col-md-4">
                      <div class="small text-end">
                        <strong>Result Size:</strong>
                        {{ clippedDimensions.width }} ×
                        {{ clippedDimensions.height }} ×
                        {{ clippedDimensions.depth }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Legend -->
                <div class="d-flex flex-wrap gap-3 small text-muted mt-3">
                  <div>
                    <span class="legend-box" style="background-color: rgba(13, 110, 253, 0.3); border: 2px solid #0d6efd;"></span>
                    Current clipping region
                  </div>
                  <div>
                    <span class="legend-box" style="background-color: rgba(40, 167, 69, 0.3); border: 2px dashed #28a745;"></span>
                    Drawing new selection
                  </div>
                  <div>
                    <span class="legend-box" style="background-color: rgba(220, 53, 69, 0.1);"></span>
                    Will be removed
                  </div>
                </div>
              </div>
              <div v-else class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                  <span class="visually-hidden">Loading preview...</span>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" @click="resetRanges">
                <i class="bi bi-arrow-counterclockwise me-1"></i>Reset to Full
              </button>
              <div class="flex-grow-1"></div>
              <button type="button" class="btn btn-secondary" @click="closePreview">Close</button>
              <button type="button" class="btn btn-primary" @click="closePreview(); applyClipping();">
                <i class="bi bi-check-circle me-1"></i>Apply Clipping
              </button>
            </div>
          </div>
        </div>
      </div>
      <div v-if="showPreview" class="modal-backdrop fade show"></div>
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
      showPreview: false,
      previewSliceIndex: 0,
      previewData: null,
      // Interactive selection state
      isDrawing: false,
      selectionStart: null,
      selectionCurrent: null,
      canvasScale: 1,
    };
  },

  computed: {
    dimensionFields() {
      const summary = this.datasetSummary;
      const normalized = this.normalizedRanges;
      const base = [
        { key: 'width', label: 'Width' },
        { key: 'height', label: 'Height' },
        { key: 'depth', label: 'Depth' },
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

    maxSliceIndex() {
      if (!this.datasetSummary) return 0;
      return Math.max(0, this.datasetSummary.depth - 1);
    },

    clippingBoxCoordinates() {
      if (!this.normalizedRanges || !this.datasetSummary) return null;

      const { width, height } = this.datasetSummary;

      return {
        x: (this.normalizedRanges.width.start / width) * 100,
        y: (this.normalizedRanges.height.start / height) * 100,
        width: (this.normalizedRanges.width.length / width) * 100,
        height: (this.normalizedRanges.height.length / height) * 100,
      };
    },
  },

  watch: {
    datasetSummary: {
      handler(summary, oldSummary) {
        // Save the first seen dataset dimensions as the original baseline
        if (summary && !this.originalDimensions) {
          this.originalDimensions = {
            width: Number(summary.width) || 0,
            height: Number(summary.height) || 0,
            depth: Number(summary.depth) || 0,
          };
          this.resetRanges();
        } else if (summary && oldSummary) {
          // Dataset changed (e.g., after applying filter) - update range limits but keep current values
          this.adjustRangesToNewDimensions(summary);
        } else if (summary && !oldSummary) {
          this.resetRanges();
        }
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

    previewData: {
      handler() {
        this.renderPreviewCanvas();
      },
    },
  },

  methods: {
    onRangeInput(key) {
      if (!['width', 'height', 'depth'].includes(key)) return;
      const range = this.ranges[key];
      if (!range) return;
      const safeStart = this.toSafeIndex(range.start);
      const safeEnd = this.toSafeIndex(range.end);
      
      // Force reactive update by reassigning the entire range object
      this.ranges[key] = {
        start: safeStart,
        end: safeEnd,
      };
      
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
          width: summary ? Math.max(Number(summary.width), 0) : 0,
          height: summary ? Math.max(Number(summary.height), 0) : 0,
          depth: summary ? Math.max(Number(summary.depth), 0) : 0,
        };
        for (const key of ['width', 'height', 'depth']) {
          // Force reactive update by reassigning the entire range object
          // Vue doesn't detect nested property mutations (this.ranges[key].start = x)
          this.ranges[key] = { start: 0, end: defaults[key] };
        }
      } finally {
        this.isUpdatingRanges = false;
      }
      this.clearDirty();
    },

    adjustRangesToNewDimensions(summary) {
      // Adjust ranges if new dimensions are smaller than current values
      const newDims = {
        width: Number(summary.width) || 0,
        height: Number(summary.height) || 0,
        depth: Number(summary.depth) || 0,
      };
      
      this.isUpdatingRanges = true;
      try {
        for (const key of ['width', 'height', 'depth']) {
          const newSize = newDims[key];
          if (this.ranges[key]) {
            // Clamp end to new size if needed
            if (this.ranges[key].end > newSize) {
              this.ranges[key].end = newSize;
            }
            // Clamp start if needed
            if (this.ranges[key].start >= newSize) {
              this.ranges[key].start = Math.max(0, newSize - 1);
            }
          }
        }
      } finally {
        this.isUpdatingRanges = false;
      }
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
      const clampedEnd = Math.min(Math.max(rawEnd, 0), sizeInt);
      const start = Math.min(clampedStart, clampedEnd);
      const end = Math.max(clampedStart, clampedEnd);
      const length = end - start;
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
      
      // Store original dataset if this is the first filter operation
      if (!this.$store.state.originalDataset && this.$store.state.dataset) {
        this.$store.commit('setOriginalDataset', {
          name: this.$store.state.dataset.name,
          type: this.$store.state.dataset.type,
          content: this.$store.state.dataset.content,
          dimensions: this.$store.state.dataset.dimensions,
          precision: this.$store.state.dataset.precision,
          size: this.$store.state.dataset.size,
          vars: this.$store.state.dataset.vars,
        });
      }
      
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
      
      // Data is stored in row-major order as [depth, height, width]
      // So the strides are: width is fastest, then height, then depth
      const widthStride = 1;
      const heightStride = width;
      const depthStride = width * height;

      for (let z = depthRange.start; z < depthRange.end; z += 1) {
        for (let y = heightRange.start; y < heightRange.end; y += 1) {
          for (let x = widthRange.start; x < widthRange.end; x += 1) {
            const sourceIndex = z * depthStride + y * heightStride + x * widthStride;
            result[destOffset] = source[sourceIndex];
            destOffset += 1;
          }
        }
      }

      const newDimensions = [clippedWidth, clippedHeight, clippedDepth];
      this.$store.commit('setFileData', {
        content: result.buffer,
        dimensions: newDimensions,
        precision,
        isFilterResult: true, // Mark as filter result to prevent clearing original dataset
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

    openPreview() {
      if (!this.canApply) return;

      // Initialize slice to middle of depth range
      const depthRange = this.normalizedRanges.depth;
      this.previewSliceIndex = Math.floor((depthRange.start + depthRange.end) / 2);

      // Extract data for visualization
      this.extractPreviewData();
      this.showPreview = true;
    },

    closePreview() {
      this.showPreview = false;
      this.previewData = null;
    },

    extractPreviewData() {
      if (!this.datasetBuffer || !this.datasetSummary) return;

      const { width, height } = this.datasetSummary;
      const precision = this.datasetPrecision;
      const ctor = this.getTypedArrayConstructor(precision);

      if (!ctor) return;

      const sourceData = new ctor(this.datasetBuffer);

      // Extract 2D slice at current depth index
      const sliceData = new Float32Array(width * height);
      const depthStride = width * height;
      const sliceOffset = this.previewSliceIndex * depthStride;

      for (let i = 0; i < width * height; i++) {
        sliceData[i] = sourceData[sliceOffset + i];
      }

      // Find min/max for color mapping
      let min = Infinity;
      let max = -Infinity;
      for (let i = 0; i < sliceData.length; i++) {
        if (sliceData[i] < min) min = sliceData[i];
        if (sliceData[i] > max) max = sliceData[i];
      }

      this.previewData = {
        data: sliceData,
        width,
        height,
        min,
        max,
      };
    },

    updatePreviewSlice() {
      this.extractPreviewData();
    },

    getDataValueAt(x, y) {
      if (!this.previewData) return null;
      const idx = y * this.previewData.width + x;
      return this.previewData.data[idx];
    },

    renderPreviewCanvas() {
      this.$nextTick(() => {
        const canvas = this.$refs.previewCanvas;
        if (!canvas || !this.previewData) return;

        const { data, width, height, min, max } = this.previewData;
        const ctx = canvas.getContext('2d');

        // Set canvas size
        canvas.width = width;
        canvas.height = height;

        // Create image data
        const imageData = ctx.createImageData(width, height);
        const range = max - min;

        for (let y = 0; y < height; y++) {
          for (let x = 0; x < width; x++) {
            const idx = y * width + x;
            const value = data[idx];

            // Normalize to 0-1
            const normalized = range > 0 ? (value - min) / range : 0.5;

            // Apply colormap (grayscale for now, can be enhanced)
            const intensity = Math.floor(normalized * 255);

            const pixelIdx = idx * 4;
            imageData.data[pixelIdx] = intensity;     // R
            imageData.data[pixelIdx + 1] = intensity; // G
            imageData.data[pixelIdx + 2] = intensity; // B
            imageData.data[pixelIdx + 3] = 255;       // A
          }
        }

        ctx.putImageData(imageData, 0, 0);

        // Update canvas scale for mouse coordinate conversion
        const rect = canvas.getBoundingClientRect();
        this.canvasScale = width / rect.width;
      });
    },

    onCanvasMouseDown(event) {
      const canvas = this.$refs.previewCanvas;
      if (!canvas || !this.previewData) return;

      const rect = canvas.getBoundingClientRect();
      const x = (event.clientX - rect.left) * this.canvasScale;
      const y = (event.clientY - rect.top) * this.canvasScale;

      this.isDrawing = true;
      this.selectionStart = { x: Math.floor(x), y: Math.floor(y) };
      this.selectionCurrent = { x: Math.floor(x), y: Math.floor(y) };

      event.preventDefault();
    },

    onCanvasMouseMove(event) {
      if (!this.isDrawing || !this.previewData) return;

      const canvas = this.$refs.previewCanvas;
      const rect = canvas.getBoundingClientRect();
      const x = (event.clientX - rect.left) * this.canvasScale;
      const y = (event.clientY - rect.top) * this.canvasScale;

      this.selectionCurrent = {
        x: Math.max(0, Math.min(Math.floor(x), this.previewData.width - 1)),
        y: Math.max(0, Math.min(Math.floor(y), this.previewData.height - 1)),
      };

      event.preventDefault();
    },

    onCanvasMouseUp() {
      if (!this.isDrawing || !this.selectionStart || !this.selectionCurrent) return;

      this.isDrawing = false;

      // Calculate the selection bounds
      const x1 = Math.min(this.selectionStart.x, this.selectionCurrent.x);
      const x2 = Math.max(this.selectionStart.x, this.selectionCurrent.x);
      const y1 = Math.min(this.selectionStart.y, this.selectionCurrent.y);
      const y2 = Math.max(this.selectionStart.y, this.selectionCurrent.y);

      // Update the clipping ranges
      // Force reactive update by reassigning entire objects
      // Vue doesn't detect nested property mutations
      this.isUpdatingRanges = true;
      try {
        this.ranges.width = { start: x1, end: x2 + 1 }; // exclusive end
        this.ranges.height = { start: y1, end: y2 + 1 }; // exclusive end
      } finally {
        this.isUpdatingRanges = false;
      }

      // Clear selection
      this.selectionStart = null;
      this.selectionCurrent = null;

      this.markDirty();
    },

    onCanvasMouseLeave() {
      if (this.isDrawing) {
        this.onCanvasMouseUp();
      }
    },

    getActiveSelectionBox() {
      if (this.isDrawing && this.selectionStart && this.selectionCurrent) {
        const x1 = Math.min(this.selectionStart.x, this.selectionCurrent.x);
        const x2 = Math.max(this.selectionStart.x, this.selectionCurrent.x);
        const y1 = Math.min(this.selectionStart.y, this.selectionCurrent.y);
        const y2 = Math.max(this.selectionStart.y, this.selectionCurrent.y);

        return {
          x: (x1 / this.previewData.width) * 100,
          y: (y1 / this.previewData.height) * 100,
          width: ((x2 - x1 + 1) / this.previewData.width) * 100,
          height: ((y2 - y1 + 1) / this.previewData.height) * 100,
        };
      }
      return null;
    },
  },
  
  /**
   * Static method for pipeline replay.
   * Pure function that applies clipping without side effects.
   * @param {Object} dataset - Current dataset { content, dimensions, precision }
   * @param {Object} params - Filter parameters { ranges: {width, height, depth} }
   * @returns {Promise<Object>} Filtered dataset
   */
  applyFilter: async function(dataset, params) {
    const { ranges } = params;
    const [origWidth, origHeight] = dataset.dimensions;
    
    // Extract clipping ranges
    const widthRange = ranges.width;
    const heightRange = ranges.height;
    const depthRange = ranges.depth;
    
    const clippedWidth = widthRange.length;
    const clippedHeight = heightRange.length;
    const clippedDepth = depthRange.length;
    
    // Get TypedArray constructor
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
    
    const sourceData = new TypedArray(dataset.content);
    const resultLength = clippedWidth * clippedHeight * clippedDepth;
    const resultData = new TypedArray(resultLength);
    
    // Perform clipping
    let destIdx = 0;
    const widthStride = 1;
    const heightStride = origWidth;
    const depthStride = origWidth * origHeight;
    
    for (let z = depthRange.start; z < depthRange.end; z++) {
      for (let y = heightRange.start; y < heightRange.end; y++) {
        for (let x = widthRange.start; x < widthRange.end; x++) {
          const srcIdx = z * depthStride + y * heightStride + x * widthStride;
          resultData[destIdx++] = sourceData[srcIdx];
        }
      }
    }
    
    return {
      content: resultData.buffer,
      dimensions: [clippedWidth, clippedHeight, clippedDepth],
      precision: dataset.precision,
      name: dataset.name,
      type: dataset.type,
    };
  },
};
</script>

<style scoped>
.range-card {
  background-color: #f8f9fa;
}
.form-label-sm {
  font-size: 0.75rem;
  font-weight: 600;
}

/* Preview Modal Styles */
.preview-visualization-container {
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  overflow: auto;
}

.preview-canvas {
  max-width: 100%;
  max-height: 500px;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  border: 2px solid #dee2e6;
  background-color: white;
  display: block;
  cursor: crosshair;
  user-select: none;
}

.preview-canvas.canvas-drawing {
  cursor: grabbing;
}

.drawing-selection-overlay {
  position: absolute;
  pointer-events: none;
  background-color: rgba(40, 167, 69, 0.2);
  animation: pulse-selection 0.5s ease-in-out infinite alternate;
}

.drawing-selection-border {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 3px dashed #28a745;
  box-shadow: 0 0 0 2px rgba(40, 167, 69, 0.4);
}

@keyframes pulse-selection {
  from {
    background-color: rgba(40, 167, 69, 0.15);
  }
  to {
    background-color: rgba(40, 167, 69, 0.3);
  }
}

.clipping-box-overlay {
  position: absolute;
  pointer-events: none;
  background-color: rgba(13, 110, 253, 0.15);
}

.clipping-box-border {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 3px solid #0d6efd;
  box-shadow: 0 0 0 2px rgba(13, 110, 253, 0.3);
}

.clipping-box-label {
  position: absolute;
  top: -25px;
  left: 0;
  background-color: #0d6efd;
  color: white;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 3px;
  white-space: nowrap;
}

.legend-box {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 2px;
  margin-right: 5px;
  vertical-align: middle;
}

.modal-backdrop {
  background-color: rgba(0, 0, 0, 0.5);
}
</style>
