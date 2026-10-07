<template>
  <div class="netcdf-controls" v-if="dataset && dataset.vars">
    <!-- NetCDF file explorer -->
    <table class="table mt-2">
      <thead>
        <tr>
          <th></th>
          <th>name</th>
          <th>type</th>
          <th>dimensions</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(props, name) in dataset.vars"
          :key="name"
          :class="ncSelectedVar === name ? 'table-primary' : ''"
        >
          <td style="vertical-align: middle; text-align: center;">
            <input
              class="form-check-input"
              type="radio"
              name="netcdf-var-select"
              :value="name"
              v-model="ncSelectedVar"
            />
          </td>
          <td style="vertical-align: middle;">{{ name }}</td>
          <td style="vertical-align: middle;">{{ props.dtype }}</td>
          <td>
            <a
              class="text-decoration-underline text-dark"
              v-tooltip:right="'[' + props.dimensions + ']'"
            >
              {{ props.shape }}
            </a>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Slicing filter -->
    <div v-show="ncSelectedVar" class="slice-controls-container mt-3">
      <!-- Checkbox & apply button -->
      <div class="d-flex align-items-center gap-3">
        <div class="form-check ms-1">
          <input
            class="form-check-input"
            type="checkbox"
            id="showSliceControls"
            v-model="showSliceControls"
            @change="initSliceParams"
          />
          <label class="form-check-label mb-2" for="showSliceControls">
            Enable slicing
          </label>
        </div>
        <button
          class="btn btn-primary"
          :disabled="!ncSelectedVar || isDownloading"
          @click="selectNetCDFVariable"
        >
          <span
            v-if="isDownloading"
            class="spinner-border spinner-border-sm me-1"
            role="status"
            aria-hidden="true"
          ></span>
          Apply
        </button>
      </div>

      <!-- Parameter settings -->
      <div v-if="showSliceControls" class="card mt-2">
        <div class="card-header">
          <h5 class="mb-0">Slice variable: {{ ncSelectedVar }}</h5>
        </div>
        <div class="card-body">
          <template v-for="(dimSize, dimIndex) in currentVarShape" :key="dimIndex">
            <div v-if="dimSize > 1" class="mb-3">
              <label class="form-label">Dimension {{ dimIndex }} (size: {{ dimSize }})</label>
              <div class="row g-2">
                <div class="col">
                  <div class="form-floating">
                    <input
                      type="number"
                      class="form-control"
                      :id="'start-' + dimIndex"
                      :min="0"
                      :max="dimSize - 1"
                      v-model.number="sliceParams[dimIndex].start"
                    />
                    <label :for="'start-' + dimIndex">Start</label>
                  </div>
                </div>
                <div class="col">
                  <div class="form-floating">
                    <input
                      type="number"
                      class="form-control"
                      :id="'end-' + dimIndex"
                      min="1"
                      :max="dimSize"
                      v-model.number="sliceParams[dimIndex].end"
                    />
                    <label :for="'end-' + dimIndex">End</label>
                  </div>
                </div>
                <div class="col">
                  <div class="form-floating">
                    <input
                      type="number"
                      class="form-control"
                      :id="'step-' + dimIndex"
                      min="1"
                      v-model.number="sliceParams[dimIndex].step"
                    />
                    <label :for="'step-' + dimIndex">Step</label>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <div v-if="!hasSlicableDimensions" class="alert alert-info mb-0">
            This variable has no dimensions with size > 1 available for slicing.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { downloadNetCDFVariable } from '@/api/datasets';

export default {
  name: 'NetCDFControls',
  props: {
    dataset: {
      type: Object,
      default: null,
    },
  },
  emits: ['variable-loaded'],

  data() {
    return {
      ncSelectedVar: '',
      showSliceControls: false,
      sliceParams: [],
      isDownloading: false,
    };
  },

  computed: {
    currentVarShape() {
      if (!this.ncSelectedVar || !this.dataset?.vars?.[this.ncSelectedVar]) {
        return [];
      }
      return this.dataset.vars[this.ncSelectedVar].shape || [];
    },

    // Check if there is a slicable dimension for the selected variable
    hasSlicableDimensions() {
      if (!this.ncSelectedVar || !this.dataset?.vars?.[this.ncSelectedVar]) {
        return false;
      }
      return this.dataset.vars[this.ncSelectedVar].shape.some(size => size > 1);
    },
  },

  watch: {
    ncSelectedVar(newVal) {
      this.showSliceControls = false;
      this.sliceParams = [];

      if (newVal) {
        this.initSliceParams();
      }
    },

    dataset(newVal, oldVal) {
      if (newVal?.name !== oldVal?.name) {
        this.ncSelectedVar = '';
        this.showSliceControls = false;
        this.sliceParams = [];
      }
    },
  },

  methods: {

    initSliceParams() {
      if (!this.ncSelectedVar || !this.dataset?.vars?.[this.ncSelectedVar]) return;
      const shape = this.dataset.vars[this.ncSelectedVar].shape;
      this.sliceParams = shape.map(size => ({
        start: 0,
        end: size,
        step: 1,
      }));
    },

    async selectNetCDFVariable() {
      if (!this.ncSelectedVar || !this.dataset?.vars?.[this.ncSelectedVar]) return;

      const varMeta = this.dataset.vars[this.ncSelectedVar];
      const timeDimensionIndex = (varMeta.dimensions || []).findIndex(
        dim => dim.toLowerCase() === 'time'
      );

      if (timeDimensionIndex >= 0) {
        this.$store.commit('setTimeVarying', true);
      }

      // Map dtype to precision
      const dtypeMap = {
        float32: 'f',
        float64: 'd',
        int8: 'i8',
        uint8: 'u8',
        int16: 'i16',
        uint16: 'u16',
        int32: 'i32',
        uint32: 'u32',
      };
      const precision = dtypeMap[varMeta.dtype] || 'f';

      // Calculate sliced dimensions
      const dims = varMeta.shape;
      const slicedDims = dims.map((size, dimIndex) => {
        if (size === 1) return 1;
        const slice = this.sliceParams[dimIndex];
        if (!slice) return size;

        const start = slice.start || 0;
        const end = slice.end !== undefined ? slice.end : size;
        const step = slice.step || 1;

        return Math.ceil((end - start) / step);
      });

      let width = null;
      let height = null;
      let depth = null;

      if (slicedDims.length === 2) {
        height = slicedDims[0];
        width = slicedDims[1];
        depth = 1;
      } else if (slicedDims.length === 3) {
        if (timeDimensionIndex >= 0) {
          const spatialIdx = [0, 1, 2].filter(i => i !== timeDimensionIndex);
          depth = slicedDims[timeDimensionIndex];
          height = slicedDims[spatialIdx[0]];
          width = slicedDims[spatialIdx[1]];
        } else {
          depth = slicedDims[0];
          height = slicedDims[1];
          width = slicedDims[2];
        }
      }

      const slices = this.sliceParams
        .filter(param => param != null)
        .map(param => ({
          start: param.start,
          end: param.end,
          step: param.step,
        }));

      this.isDownloading = true;
      this.$store.commit('setProgress', { active: true, percent: 0, message: 'Downloading variable data...' });
      this.$store.commit('setStatus', { type: 'info', message: 'Downloading variable data...' });

      try {
        const fileContent = await downloadNetCDFVariable(
          {
            filename: this.dataset.name,
            variable: this.ncSelectedVar,
            slices,
          },
          eventData => {
            if (eventData.lengthComputable) {
              const percent = Math.round((eventData.loaded / eventData.total) * 100);
              this.$store.commit('setProgress', {
                active: true,
                percent,
                message: `Downloading... ${percent}%`,
              });
            }
          }
        );

        this.$emit('variable-loaded', {
          fileContent,
          precision,
          width,
          height,
          depth,
          variable: this.ncSelectedVar,
        });

        this.$store.commit('setProgress', { active: false, percent: 100, message: 'Download complete' });
        this.$store.commit('setStatus', { type: 'success', message: 'Downloaded variable data successfully!' });
      } catch (error) {
        this.$store.commit('setProgress', { active: false, percent: 0, message: 'Download failed' });
        this.$store.commit('setStatus', { type: 'danger', message: `Download file failed. ${error}` });
      } finally {
        this.isDownloading = false;
      }
    },
  },
};
</script>
