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
  emits: ['run-compressor', 'generate-configs', 'config-change'],
  data() {
    return {
      zfpMode: 'accuracy', // default to accuracy
      rateValue: 8.0,
      precisionValue: 32,
      accuracyValue: 0.001,
      nthreads: 1,
      exploreEnabled: false,
      exploreMaxCombos: 64,
      exploreSelections: {
        rate: [],
        precision: [],
        accuracy: [],
      },
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
    },
    exploreCombinationCount() {
      const count = (this.exploreSelections.rate?.length || 0) +
        (this.exploreSelections.precision?.length || 0) +
        (this.exploreSelections.accuracy?.length || 0);
      return count;
    },
    isPromoted() {
      return Boolean(this.$store?.state?.baseConfigurations?.[this.nodeId]);
    },
  },
  methods: {
    buildBaseConfig() {
      const compressorConfig = {};
      if (this.zfpMode === 'rate') {
        compressorConfig['zfp:rate'] = this.rateValue;
      } else if (this.zfpMode === 'precision') {
        compressorConfig['zfp:precision'] = this.precisionValue;
      } else if (this.zfpMode === 'accuracy') {
        compressorConfig['zfp:accuracy'] = this.accuracyValue;
      }
      compressorConfig['pressio:nthreads'] = this.nthreads;
      return {
        compressor_id: 'zfp',
        compressor_config: compressorConfig,
        early_config: {
          'pressio:metric': 'composite',
          'composite:plugins': ['time', 'size', 'error_stat'],
        }
      };
    },
    generateCombinations() {
      const total = this.exploreCombinationCount;
      if (!total) {
        this.setStatus('warning', 'Select at least one value to generate.');
        return;
      }
      if (total > this.exploreMaxCombos) {
        this.setStatus('warning', `Selection produces ${total} configurations; limit is ${this.exploreMaxCombos}.`);
        return;
      }
      const configs = [];
      const pushConfig = (key, value) => {
        const compressorConfig = { 'pressio:nthreads': this.nthreads };
        compressorConfig[key] = value;
        configs.push({
          compressor_id: 'zfp',
          compressor_config: compressorConfig,
          early_config: {
            'pressio:metric': 'composite',
            'composite:plugins': ['time', 'size', 'error_stat'],
          }
        });
      };
      this.exploreSelections.rate.forEach(v => pushConfig('zfp:rate', v));
      this.exploreSelections.precision.forEach(v => pushConfig('zfp:precision', v));
      this.exploreSelections.accuracy.forEach(v => pushConfig('zfp:accuracy', v));

      const baseConfig = this.buildBaseConfig();
      this.$emit('generate-configs', { baseConfig, configs });
      this.setStatus('success', `Generated ${configs.length} configurations for exploration.`);
    },
    emitConfigChange() {
      const compressorConfig = {};
      if (this.zfpMode === 'rate') {
        compressorConfig['zfp:rate'] = this.rateValue;
      } else if (this.zfpMode === 'precision') {
        compressorConfig['zfp:precision'] = this.precisionValue;
      } else if (this.zfpMode === 'accuracy') {
        compressorConfig['zfp:accuracy'] = this.accuracyValue;
      }
      compressorConfig['pressio:nthreads'] = this.nthreads;
      this.$emit('config-change', {
        compressor_id: 'zfp',
        compressor_config: compressorConfig
      });
    },
    runCompressor() {
      const base = this.buildBaseConfig();
      const config = {
        ...base,
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
  watch: {
    zfpMode() { this.emitConfigChange(); },
    rateValue() { this.emitConfigChange(); },
    precisionValue() { this.emitConfigChange(); },
    accuracyValue() { this.emitConfigChange(); },
    nthreads() { this.emitConfigChange(); },
  },
  mounted() {
    this.emitConfigChange();
  }
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

    <div class="options-panel p-3 mb-3">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h6 class="fw-bold mb-0 d-flex align-items-center">
          <i class="bi bi-compass me-2"></i>Novice Exploration
        </h6>
        <div class="form-check form-switch">
          <input class="form-check-input" type="checkbox" id="zfpExploreToggle" v-model="exploreEnabled">
          <label class="form-check-label small text-muted" for="zfpExploreToggle">Enable</label>
        </div>
      </div>
      <p class="text-muted x-small mb-2">
        Choose multiple values for each mode. Each selection becomes a configuration.
      </p>
      <div v-if="exploreEnabled">
        <div class="row gx-3 gy-2">
          <div class="col-md-4">
            <label class="form-label small fw-semibold text-muted mb-1">Accuracy</label>
            <input
              type="text"
              class="form-control form-control-sm"
              placeholder="e.g. 0.001,0.0001"
              @change="exploreSelections.accuracy = $event.target.value.split(',').map(v => Number(v.trim())).filter(v => Number.isFinite(v) && v > 0)"
            >
          </div>
          <div class="col-md-4">
            <label class="form-label small fw-semibold text-muted mb-1">Rate</label>
            <input
              type="text"
              class="form-control form-control-sm"
              placeholder="e.g. 8,12,16"
              @change="exploreSelections.rate = $event.target.value.split(',').map(v => Number(v.trim())).filter(v => Number.isFinite(v) && v > 0)"
            >
          </div>
          <div class="col-md-4">
            <label class="form-label small fw-semibold text-muted mb-1">Precision</label>
            <input
              type="text"
              class="form-control form-control-sm"
              placeholder="e.g. 16,24,32"
              @change="exploreSelections.precision = $event.target.value.split(',').map(v => Number(v.trim())).filter(v => Number.isFinite(v) && v > 0)"
            >
          </div>
        </div>
        <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mt-2">
          <div class="d-flex align-items-center gap-2">
            <label class="form-label small fw-semibold text-muted mb-0">Max configurations</label>
            <input
              type="number"
              class="form-control form-control-sm"
              v-model.number="exploreMaxCombos"
              min="1"
              max="500"
              style="width: 120px;"
            >
          </div>
          <div class="text-muted x-small">
            Estimated configurations: <strong>{{ exploreCombinationCount }}</strong>
          </div>
          <button
            type="button"
            class="btn btn-outline-primary btn-sm"
            :disabled="exploreCombinationCount === 0"
            @click="generateCombinations"
          >
            Generate configurations
          </button>
        </div>
      </div>
    </div>

    <div class="alert alert-info d-flex justify-content-between align-items-center">
      <div>
        <i class="bi bi-info-circle me-2"></i>
        <span v-if="!isPromoted">Configure the ZFP mode above and click Run to compress the data.</span>
        <span v-else>This node is <strong>promoted</strong> to the Config Graph for bulk generation.</span>
      </div>
      <button 
        v-if="!isPromoted"
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
