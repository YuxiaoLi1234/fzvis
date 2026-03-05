<script>
import BaseCompressorConfig from './BaseCompressorConfig.vue';

export default {
  name: 'ZFPConfig',
  extends: BaseCompressorConfig,
  props: {
    status: {
      type: String,
      default: 'pending',
    },
  },
  emits: ['run-compressor'],
  data() {
    return {
      zfpMode: 'accuracy', // default to accuracy
      rateValue: 8.0,
      precisionValue: 32,
      accuracyValue: 0.001,
      nthreads: 1,
      modeOptions: [
        { label: 'Fixed Accuracy', value: 'accuracy', description: 'Guarantees absolute error bound.' },
        { label: 'Fixed Rate', value: 'rate', description: 'Guarantees bits per value (fixed size).' },
        { label: 'Fixed Precision', value: 'precision', description: 'Guarantees number of bit planes.' },
      ],
    };
  },
  computed: {
    isReadyToRun() {
      if (this.zfpMode === 'rate') return this.rateValue > 0;
      if (this.zfpMode === 'precision') return this.precisionValue > 0;
      if (this.zfpMode === 'accuracy') return this.accuracyValue > 0;
      return false;
    },
    isRunning() {
      return this.status === 'running';
    },
    currentModeDescription() {
      return this.modeOptions.find(m => m.value === this.zfpMode)?.description || '';
    }
  },
  methods: {
    runCompressor() {
      const compressorConfig = {};
      
      // ZFP High-level settings
      if (this.zfpMode === 'rate') {
        compressorConfig['zfp:rate'] = this.rateValue;
      } else if (this.zfpMode === 'precision') {
        compressorConfig['zfp:precision'] = this.precisionValue;
      } else if (this.zfpMode === 'accuracy') {
        compressorConfig['zfp:accuracy'] = this.accuracyValue;
      }
      
      // Common settings
      compressorConfig['pressio:nthreads'] = this.nthreads;

      const config = {
        compressor_id: 'zfp',
        compressor_config: compressorConfig,
        data_key: this.$store?.state?.dataset?.data_key || null,
        dataset_meta: {
          name: this.$store?.state?.dataset?.name,
          dimensions: this.$store?.state?.dataset?.dimensions,
          precision: this.$store?.state?.dataset?.precision,
        },
        early_config: {
          'pressio:metric': 'composite',
          'composite:plugins': ['time', 'size', 'error_stat'],
        }
      };
      
      this.$emit('run-compressor', config);
    }
  },
};
</script>

<template>
  <div class="bg-light p-3 my-3 rounded shadow-sm w-100">
    <div class="options-panel p-3 mb-3">
      <h6 class="fw-bold mb-3 d-flex align-items-center">
        <i class="bi bi-gear-fill me-2"></i>ZFP Configuration
      </h6>
      
      <div class="row gx-3 gy-2">
        <!-- Mode Selection -->
        <div class="col-md-12">
          <label class="form-label small fw-semibold text-muted mb-1">Compression Mode</label>
          <div class="d-flex gap-2 mb-2">
            <button 
              v-for="mode in modeOptions" 
              :key="mode.value"
              type="button"
              class="btn btn-sm"
              :class="zfpMode === mode.value ? 'btn-primary' : 'btn-outline-primary'"
              @click="zfpMode = mode.value"
            >
              {{ mode.label }}
            </button>
          </div>
          <p class="text-muted x-small mb-1">
            <i class="bi bi-info-circle me-1"></i>{{ currentModeDescription }}
          </p>
        </div>

        <!-- Dynamic Value Input -->
        <div class="col-md-8">
          <div v-if="zfpMode === 'rate'">
            <label class="form-label small fw-semibold text-muted mb-1">Rate (bits per value)</label>
            <div class="input-group input-group-sm">
              <input type="number" class="form-control" v-model.number="rateValue" step="0.1" min="0">
              <span class="input-group-text">bits</span>
            </div>
          </div>
          
          <div v-if="zfpMode === 'precision'">
            <label class="form-label small fw-semibold text-muted mb-1">Precision (bit planes)</label>
            <div class="input-group input-group-sm">
              <input type="number" class="form-control" v-model.number="precisionValue" step="1" min="1">
              <span class="input-group-text">planes</span>
            </div>
          </div>
          
          <div v-if="zfpMode === 'accuracy'">
            <label class="form-label small fw-semibold text-muted mb-1">Accuracy (max absolute error)</label>
            <div class="input-group input-group-sm">
              <input type="number" class="form-control" v-model.number="accuracyValue" step="0.000001" min="0">
              <span class="input-group-text">tolerance</span>
            </div>
          </div>
        </div>

        <!-- Common Settings -->
        <div class="col-md-4">
          <label class="form-label small fw-semibold text-muted mb-1">Threads</label>
          <input 
            type="number" 
            class="form-control form-control-sm" 
            v-model.number="nthreads" 
            min="1"
          >
        </div>
      </div>
    </div>

    <div class="alert alert-info d-flex justify-content-between align-items-center">
      <div>
        <i class="bi bi-info-circle me-2"></i>
        Configure the ZFP mode above and click Run to compress the data.
      </div>
      <button 
        type="button"
        class="btn btn-primary shadow-sm px-4"
        :disabled="!isReadyToRun || isRunning"
        @click="runCompressor"
      >
        <span v-if="isRunning" class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
        <i v-else class="bi bi-play-fill me-1"></i>
        {{ isRunning ? 'Running...' : 'Run' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.options-panel {
  background: #ffffff;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.x-small {
  font-size: 0.75rem;
}
</style>
