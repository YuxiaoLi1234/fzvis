<template>
  <div class="critical-points-preservation">
    <div class="card-body">
      <h6 class="card-subtitle mb-3 text-muted">Critical Points Preservation Configuration</h6>
      
      <div class="mb-3">
        <label for="threshold" class="form-label">Relative Error Bound</label>
        <input
          type="number"
          class="form-control"
          id="threshold"
          v-model.number="localConfig.threshold"
          @input="emitConfigChange"
          step="0.0001"
          min="0"
          max="1"
        />
        <div class="form-text">
          Relative error bound for topology preservation (rel_err_bound)
        </div>
      </div>

      <div class="mb-3">
        <label for="connectivity" class="form-label">Connectivity Type</label>
        <select 
          class="form-select" 
          id="connectivity"
          v-model.number="localConfig.connectivityType"
          @change="emitConfigChange"
        >
          <option :value="0">Piecewise Linear (0)</option>
          <option :value="1">Full Connectivity (1)</option>
        </select>
        <div class="form-text">
          Grid connectivity model for critical point detection
        </div>
      </div>

      <div class="mb-3">
        <label for="accelerator" class="form-label">Accelerator</label>
        <select 
          class="form-select" 
          id="accelerator"
          v-model="localConfig.accelerator"
          @change="emitConfigChange"
        >
          <option value="">None</option>
          <option value="omp">OpenMP</option>
          <option value="cuda">CUDA</option>
          <!-- <option value="hip">HIP</option>
          <option value="sycl">SYCL</option> -->
        </select>
        <div class="form-text">
          Hardware accelerator for computational optimization
        </div>
      </div>

      <div class="mb-3">
        <label class="form-label d-block">Preservation Mode</label>
        <div class="form-check">
          <input
            class="form-check-input"
            type="checkbox"
            id="preserveMin"
            v-model="localConfig.preserveMin"
            @change="emitConfigChange"
          />
          <label class="form-check-label" for="preserveMin">
            Preserve Local Minima
          </label>
        </div>
        <div class="form-check">
          <input
            class="form-check-input"
            type="checkbox"
            id="preserveMax"
            v-model="localConfig.preserveMax"
            @change="emitConfigChange"
          />
          <label class="form-check-label" for="preserveMax">
            Preserve Local Maxima
          </label>
        </div>
        <div class="form-check">
          <input
            class="form-check-input"
            type="checkbox"
            id="preservePath"
            v-model="localConfig.preservePath"
            @change="emitConfigChange"
          />
          <label class="form-check-label" for="preservePath">
            Preserve Integratal Paths
          </label>
        </div>
        <div class="form-text">
          Features to preserve in the topology-preserving edits
        </div>
      </div>

      <div class="alert alert-info" role="alert">
        <i class="bi bi-info-circle me-2"></i>
        <strong>Note:</strong> MSz derives edits to fix topological faults 
        within the specified relative error bound.
      </div>

      <button 
        class="btn btn-primary w-100"
        @click="applyCorrection"
        :disabled="!isValid"
      >
        <i class="bi bi-play-fill me-1"></i>
        Apply MSz Correction
      </button>

      <div v-if="status" class="mt-3">
        <div 
          class="alert" 
          :class="{
            'alert-success': status === 'success',
            'alert-danger': status === 'error',
            'alert-warning': status === 'running'
          }"
          role="alert"
        >
          {{ statusMessage }}
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
      status: null,
      statusMessage: ''
    };
  },
  computed: {
    isValid() {
      return this.localConfig.threshold >= 0 && 
             this.localConfig.threshold <= 1 &&
             this.hasRequiredInputs;
    },
    hasRequiredInputs() {
      return this.inputData['in-0'] && this.inputData['original'];
    },
    originalDataset() {
      return this.inputData['original'] || null;
    },
    compressedDataset() {
      return this.inputData['in-0'] || null;
    }
  },
  methods: {
    emitConfigChange() {
      this.$emit('config-change', this.localConfig);
    },
    async applyCorrection() {
      if (!this.hasRequiredInputs) {
        this.status = 'error';
        this.statusMessage = 'Missing required inputs. Please connect both Original Data and Compressed Data.';
        return;
      }

      this.status = 'running';
      this.statusMessage = 'Applying critical points preservation...';
      this.$emit('start', this.nodeId);

      try {
        const formData = new FormData();
        const originalKey = this.originalDataset.data_key || '';
        const compressedKey = this.compressedDataset.data_key || '';
        const meta = this.originalDataset.meta || this.originalDataset.dataset_meta || {};

        formData.append('original_key', originalKey);
        formData.append('compressed_key', compressedKey);
        formData.append('config', JSON.stringify(this.localConfig));
        formData.append('metadata', JSON.stringify(meta));
        
        // Prepare datasets map for fallback
        const datasets = {};
        if (originalKey) datasets[originalKey] = this.originalDataset;
        if (compressedKey) datasets[compressedKey] = this.compressedDataset;

        const response = await requestWithFallback({
          method: 'post',
          url: '/api/correction/critical_points',
          data: formData
        }, datasets);

        const result = response.data;
        if (result.error) throw new Error(result.error);

        // Fetch the corrected binary data
        if (result.data_key) {
          const dataResp = await requestWithFallback({
            method: 'get',
            url: `/api/decompressed/${result.data_key}`,
            responseType: 'arraybuffer'
          }, {}); // No fallback mapping for newly generated keys (they should be on server)
          result.decp_data = dataResp.data;
        }

        this.status = 'success';
        this.statusMessage = 'Critical points preservation applied successfully';
        
        // Ensure result has metadata for visualization
        const finalResult = { 
          ...result, 
          config: this.localConfig,
          meta: meta, // Include meta passed to API
          dimensions: meta.dimensions,
          precision: meta.precision
        };

        this.$emit('success', {
          nodeId: this.nodeId,
          result: finalResult
        });
      } catch (error) {
        console.error('Correction error:', error);
        this.status = 'error';
        this.statusMessage = error.response?.data?.message || error.message || 'Failed to apply correction';
        this.$emit('error', { nodeId: this.nodeId, error });
      } finally {
        this.$emit('finish', this.nodeId);
      }
    }
  },
  watch: {
    config: {
      deep: true,
      handler(newConfig) {
        this.localConfig = { ...this.localConfig, ...newConfig };
      }
    }
  }
};
</script>

<style scoped>
.critical-points-preservation {
  width: 100%;
}

.form-label {
  font-weight: 500;
  font-size: 0.9rem;
}

.form-text {
  font-size: 0.85rem;
}
</style>
