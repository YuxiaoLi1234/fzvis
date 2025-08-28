<script>
import { Modal } from 'bootstrap';
import InputDataset from './InputDataset.vue';
import axios from 'axios';

export default {
  name: 'PipelineView',
  components: { InputDataset },
  emits: ['moduleSelected'],
  data() {
    return {
      pipeline: [
        { id: 'input', label: 'Input Data', value: '' },
        { id: 'preprocessor', label: 'Preprocessor', value: '' },
        { id: 'predictor', label: 'Predictor', value: '' },
        { id: 'quantizer', label: 'Quantizer', value: '' },
        { id: 'encoder', label: 'Encoder', value: '' },
        { id: 'lossless', label: 'Lossless Compressor', value: '' },
      ],
      selectedModuleIdx: null,
      draggingOption: null,
      moduleOptions: {
        input: ['File upload', 'Remote Server', 'API'],
        preprocessor: ['Bypass', 'Normalize', 'Logarithmic Transform'],
        predictor: ['Lorenzo', 'Pattern-based', 'Lorenzo+Regression'],
        quantizer: ['Residual Coding', 'Linear-scale', 'Element-wise'],
        encoder: ['Arithmetic', 'Huffman', 'Fixed Huffman'],
        lossless: ['Bypass', 'GZIP', 'ZSTD'],
      },
      // For remote server dataset list
      uploadedDatasets: [],
      datasetToChange: null,
      datasetsToDelete: [],
      isLoadingDatasets: false,
      pendingInputOption: null,
      showRemoteDatasets: false,
    };
  },
  methods: {
    selectModule(idx) {
      // Toggle selection: clicking the same module deselects it
      if (this.selectedModuleIdx === idx) {
        this.selectedModuleIdx = null;
        this.$emit('moduleSelected', null);
        return;
      }
      this.selectedModuleIdx = idx;
      const module = this.pipeline[idx];
      // Notify parent so it can render options in the Properties pane
      this.$emit('moduleSelected', {
        idx,
        id: module.id,
        label: module.label,
        options: this.getOptionsForModule(module.id),
      });
    },
    getOptionsForModule(moduleId) {
      return this.moduleOptions[moduleId] || [];
    },
    onDragStart(option, moduleId) {
      this.draggingOption = { option, moduleId };
      event.dataTransfer.setData('text/plain', option);
      event.dataTransfer.setData('module-id', moduleId);
      this.$store.commit('addHistory', { kind: 'pipeline', text: `Started dragging '${option}' for ${moduleId}`, timestamp: Date.now() });
    },
    onDropOption(idx, event) {
      let dragging = this.draggingOption;
      if (!dragging && event.dataTransfer) {
        dragging = {
          option: event.dataTransfer.getData('text/plain'),
          moduleId: event.dataTransfer.getData('module-id'),
        };
      }
      const targetModuleId = this.pipeline[idx].id;
      if (dragging && dragging.moduleId === targetModuleId) {
        if (targetModuleId === 'input') {
          this.pendingInputOption = dragging.option;
          this.showRemoteDatasets = dragging.option === 'Remote Server';
          const modal = new Modal(document.getElementById('inputDataModal'));
          modal.show();
        } else {
          this.pipeline[idx].value = dragging.option;
          this.$store.commit('addHistory', { kind: 'pipeline', text: `Set ${this.pipeline[idx].label} -> ${dragging.option}` , timestamp: Date.now() });
        }
      }
      this.draggingOption = null;
    },
    fetchRemoteDatasets() {
      this.isLoadingDatasets = true;
      axios.get(localStorage.getItem('fzvis_server_address') + '/listDatasets')
        .then(response => {
          this.uploadedDatasets = response.data.datasets || [];
        })
        .catch(() => {
          this.uploadedDatasets = [];
        })
        .finally(() => {
          this.isLoadingDatasets = false;
        });
    },
    onSelectRemoteDataset(dataset) {
      this.datasetToChange = dataset;
    },
    onToggleDeleteRemoteDataset(key) {
      const idx = this.datasetsToDelete.indexOf(key);
      if (idx >= 0) this.datasetsToDelete.splice(idx, 1);
      else this.datasetsToDelete.push(key);
    },
    onSaveRemoteDatasets() {
      // Implement save logic if needed
    },
    onInputModalClose() {
      this.pendingInputOption = null;
      this.showRemoteDatasets = false;
    },
    onInputConfigured() {
      this.pipeline[0].value = this.pendingInputOption;
      const modal = Modal.getInstance(document.getElementById('inputDataModal'));
      modal.hide();
      this.$store.commit('addHistory', { kind: 'pipeline', text: `Input configured: ${this.pendingInputOption}`, timestamp: Date.now() });
      this.pendingInputOption = null;
    },
  },
};
</script>

<template>
  <div class="bg-light p-3 mb-4 rounded shadow-sm w-100">
    <h5 class="mb-2">Workflow Pipeline</h5>
    <div class="mb-2 text-muted small">Click a module to configure. Drag an option onto a module to set it.</div>
    <div class="d-flex flex-row align-items-center flex-wrap gap-3 w-100 pipeline-row" style="min-height: 100px;">
      <template v-for="(module, idx) in pipeline" :key="module.id">
        <div
          class="pipeline-node card text-center border-2"
          :class="{'border-primary shadow': selectedModuleIdx === idx, 'border-secondary': selectedModuleIdx !== idx}"
          style="min-width: 140px; height: 72px; cursor: pointer;"
          @click="selectModule(idx)"
          @dragover.prevent
          @drop="onDropOption(idx, $event)"
        >
          <div class="card-body py-2 d-flex flex-column justify-content-center">
            <span class="fw-bold small text-truncate" :title="module.label">{{ module.label }}</span>
            <div v-if="module.value" class="mt-1 small text-success text-truncate" :title="module.value">{{ module.value }}</div>
          </div>
        </div>
        <div v-if="idx < pipeline.length - 1" class="pipeline-connector" aria-hidden="true"></div>
      </template>
    </div>

    <!-- Input Data settings as modal -->
    <div class="modal fade" id="inputDataModal" data-bs-backdrop="static" tabindex="-1" aria-labelledby="inputDataModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="inputDataModalLabel">Configure Input Data</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close" @click="onInputModalClose"></button>
          </div>
          <div class="modal-body">
            <InputDataset
              v-if="pendingInputOption === 'File upload' || pendingInputOption === 'Remote Server'"
              :showRemoteDatasets="pendingInputOption === 'Remote Server'"
              @configured="onInputConfigured"
            />
            <div v-else class="text-warning">Function not implemented.</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pipeline-row { position: relative; }
.pipeline-node { flex: 0 0 auto; }
.pipeline-connector {
  position: relative;
  width: 56px;
  height: 2px;
  background-color: var(--bs-border-color, #dee2e6);
}
.pipeline-connector::after {
  content: '';
  position: absolute;
  right: -2px;
  top: 50%;
  transform: translateY(-50%);
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 6px solid var(--bs-border-color, #dee2e6);
}
/* Highlight connector near active module */
.pipeline-node.border-primary + .pipeline-connector { background-color: rgba(13,110,253,.5); }
.pipeline-node.border-primary + .pipeline-connector::after { border-left-color: rgba(13,110,253,.5); }
</style>
