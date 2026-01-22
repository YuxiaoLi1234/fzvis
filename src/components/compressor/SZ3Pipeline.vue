<script>
import BaseCompressorConfig from './BaseCompressorConfig.vue';

export default {
  name: 'PipelineView',
  extends: BaseCompressorConfig,
  props: {
    focusedModuleIdx: {
      type: Number,
      default: null,
    },
    modules: {
      type: Array,
      default: null,
    },
  },
  emits: ['moduleSelected', 'pipeline-modules-updated'],
  data() {
    return {
      compressor: {
        id: 'sz3',
        label: 'SZ3 Compressor',
        modules: [
          { id: 'predictor', label: 'Predictor', key: 'sz3:algorithm_str', value: {} },
          { id: 'quantizer', label: 'Quantizer', key: 'sz3:quant_bin_size', value: {} },
          { id: 'encoder', label: 'Encoder', key: 'sz3:encoder', value: {} },
          { id: 'lossless', label: 'Lossless', key: 'sz3:lossless', value: {} },
        ]
      },
      selectedModule: null,
      hoverModuleIdx: null,
      draggingOption: null,
      selectedOption: null,
      pendingChanges: false,
      moduleOptions: {
        predictor: [
          { label: 'Bypass', state: 'available', value: 'ALGO_NOPRED' },
          { label: 'Interpolation', state: 'available', value: 'ALGO_INTERP' },
          { label: 'Lorenzo', state: 'available', value: 'ALGO_INTERP_LORENZO' },
          { label: 'Adaptive', state: 'available', value: 'ALGO_LORENZO_REG' },
        ],
        quantizer: [
          { label: 'Linear-scaling', state: 'available', value: 65536 },
        ],
        encoder: [
          { label: 'Bypass', state: 'available', value: '0' },
          { label: 'Huffman', state: 'available', value: '1' },
        ],
        lossless: [
          { label: 'Bypass', state: 'available', value: '0' },
          { label: 'Zstd', state: 'available', value: '1' },
        ],
      },
      uploadedDatasets: [],
      datasetToChange: null,
      datasetsToDelete: [],
      isLoadingDatasets: false,
      pendingInputOption: null,
      showRemoteDatasets: false,
      showUnsupportedModal: false,
      unsupportedModalMessage: '',
      unsupportedModalType: '',
    };
  },
  created() {
    // Ensure base lifecycle still runs
    if (typeof BaseCompressorConfig?.created === 'function') {
      BaseCompressorConfig.created.call(this);
    }
    if (this.modules && this.modules.length) {
      this.compressor.modules = this.modules;
    }
  },
  mounted() {
    // Emit initial modules so the parent can show the expand button
    this.$emit('pipeline-modules-updated', this.compressor.modules);
  },
  watch: {
    modules: {
      handler(newModules) {
        if (newModules && newModules.length) {
          this.compressor.modules = newModules;
        }
      },
      deep: true,
    },
  },
  computed: {
    unsupportedModalTitle() {
      if (this.unsupportedModalType === 'unsupported') {
        return 'Unsupported Option';
      } else if (this.unsupportedModalType === 'experimental') {
        return 'Experimental Option';
      }
      return 'Option Info';
    }
  },
  methods: {
    getCurrentModules() {
      return this.compressor.modules;
    },
    selectCompressorModule(idxObj) {
      const { moduleIdx } = idxObj;
      if (this.selectedModule &&
          this.selectedModule.type === 'compressor' &&
          this.selectedModule.idx &&
          this.selectedModule.idx.moduleIdx === moduleIdx) {
        this.selectedModule = null;
        this.$emit('moduleSelected', null);
      } else {
        this.selectedModule = {
          type: 'compressor',
          idx: { moduleIdx }
        };
        const module = this.compressor.modules[moduleIdx];
        this.$emit('moduleSelected', {
          id: module.id,
          label: module.label,
          options: this.getOptionsForModule(module.id),
        });
      }
    },
    
    getOptionsForModule(moduleId) {
      return this.moduleOptions[moduleId] || [];
    },
    
    onDropCompressorOption(idxObj, event) {
      let dragging = this.draggingOption;
      if (!dragging && event.dataTransfer) {
        dragging = {
          label: event.dataTransfer.getData('text/plain'),
          moduleId: event.dataTransfer.getData('module-id'),
          state: event.dataTransfer.getData('option-state'),
        };
      }
      const targetModuleId = this.compressor.modules[idxObj.moduleIdx].id;
      const optionObj = (this.moduleOptions[targetModuleId] || []).find(opt => opt.label === dragging.label);
      if (!optionObj) {
        this.draggingOption = null;
        return;
      }
      if (optionObj.state === 'unavailable') {
        this.unsupportedModalMessage = `Option '<strong>${optionObj.label}</strong>' is <strong>not supported</strong> for <strong>${this.compressor.modules[idxObj.moduleIdx].label}</strong>.`;
        this.unsupportedModalType = 'unsupported';
        this.showUnsupportedModal = true;
        this.draggingOption = null;
        return;
      }
      else if (optionObj.state === 'experimental') {
        this.unsupportedModalMessage = `Option '<strong>${optionObj.label}</strong>' is currently in implementation for <strong>${this.compressor.modules[idxObj.moduleIdx].label}</strong>. Use with caution.`;
        this.unsupportedModalType = 'experimental';
        this.showUnsupportedModal = true;
      }
      if (dragging && dragging.moduleId === targetModuleId && optionObj.state !== 'unavailable') {
        this.compressor.modules[idxObj.moduleIdx].value = { [optionObj.label]: optionObj.value };
        // Notify via base helper to also set status/history
        this.onModulesUpdated(this.compressor.modules);
      }
      this.draggingOption = null;
    },

    onOptionDragStart(option, moduleId, event) {
      event.dataTransfer.setData('text/plain', option.label);
      event.dataTransfer.setData('module-id', moduleId);
      event.dataTransfer.setData('option-state', option.state);
      this.draggingOption = {
        label: option.label,
        moduleId,
        state: option.state
      };
    },

    onModuleDragOver(moduleId, event) {
      const dragging = this.draggingOption;
      let draggedModuleId = dragging ? dragging.moduleId : null;
      if (!draggedModuleId && event.dataTransfer) {
        draggedModuleId = event.dataTransfer.getData('module-id');
      }
      if (draggedModuleId !== moduleId) {
        event.dataTransfer.dropEffect = 'none';
        event.preventDefault();
        event.stopPropagation();
        event.currentTarget.style.cursor = 'not-allowed';
      } else {
        event.dataTransfer.dropEffect = 'copy';
        event.currentTarget.style.cursor = 'copy';
      }
    },

    onModuleDragLeave(event) {
      event.currentTarget.style.cursor = 'pointer';
    },

    onModuleMouseEnter(moduleIdx) {
      if (!this.selectedModule || this.selectedModule.idx.moduleIdx !== moduleIdx) {
        this.hoverModuleIdx = moduleIdx;
      }
    },

    onModuleMouseLeave(moduleIdx) {
      if (!this.selectedModule || this.selectedModule.idx.moduleIdx !== moduleIdx) {
        this.hoverModuleIdx = null;
      }
    },

    closeUnsupportedModal() {
      this.showUnsupportedModal = false;
      this.unsupportedModalMessage = '';
      this.unsupportedModalType = '';
    },

    removeModuleValue(moduleIdx) {
      this.compressor.modules[moduleIdx].value = {};
      this.onModulesUpdated(this.compressor.modules);
    },

    selectOption(option) {
      if (option.state === 'unavailable') {
        this.unsupportedModalMessage = `Option '<strong>${option.label}</strong>' is <strong>not supported</strong> for <strong>${this.compressor.modules[this.focusedModuleIdx].label}</strong>.`;
        this.unsupportedModalType = 'unsupported';
        this.showUnsupportedModal = true;
        return;
      }
      if (option.state === 'experimental') {
        this.unsupportedModalMessage = `Option '<strong>${option.label}</strong>' is currently in implementation for <strong>${this.compressor.modules[this.focusedModuleIdx].label}</strong>. Use with caution.`;
        this.unsupportedModalType = 'experimental';
        this.showUnsupportedModal = true;
      }
      this.selectedOption = option;
      this.pendingChanges = true;
    },

    applyConfiguration() {
      if (this.focusedModuleIdx === null || !this.selectedOption) return;
      
      this.compressor.modules[this.focusedModuleIdx].value = { 
        [this.selectedOption.label]: this.selectedOption.value 
      };
      this.onModulesUpdated(this.compressor.modules);
      this.pendingChanges = false;
    },

    getCurrentSelection() {
      if (this.focusedModuleIdx === null) return null;
      const moduleValue = this.compressor.modules[this.focusedModuleIdx].value;
      if (!moduleValue || !Object.keys(moduleValue).length) return null;
      const [label] = Object.keys(moduleValue);
      return label;
    },

    isOptionSelected(option) {
      if (this.pendingChanges) {
        return this.selectedOption?.label === option.label;
      }
      return this.getCurrentSelection() === option.label;
    },
  },
};
</script>

<template>
  <div class="bg-light p-2 my-3 rounded shadow-sm w-100">
    <div v-if="showUnsupportedModal">
      <div class="modal fade show" tabindex="-1" role="dialog" style="display: block;">
        <div class="modal-dialog modal-dialog-centered" role="document">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">{{ unsupportedModalTitle }}</h5>
              <button type="button" class="btn-close" @click="closeUnsupportedModal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div v-html="unsupportedModalMessage"></div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" @click="closeUnsupportedModal">Close</button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop fade show"></div>
    </div>

    <!-- Show options panel only when a module is focused -->
    <div v-if="focusedModuleIdx !== null">
      <div class="alert alert-primary mb-3">
        <i class="bi bi-bullseye me-2"></i>
        <strong>Configuring:</strong> {{ compressor.modules[focusedModuleIdx]?.label }}
      </div>
      
      <div class="options-panel p-3">
        <h6 class="fw-bold mb-2">Available Options</h6>
        <p class="text-muted small mb-3">Select an option and click Apply to configure this module.</p>
        
        <div class="d-flex flex-wrap gap-2 mb-3">
          <button
            v-for="option in getOptionsForModule(compressor.modules[focusedModuleIdx].id)"
            :key="option.label"
            type="button"
            class="btn"
            :class="{
              'btn-primary': isOptionSelected(option) && option.state === 'available',
              'btn-outline-primary': !isOptionSelected(option) && option.state === 'available',
              'btn-warning': isOptionSelected(option) && option.state === 'experimental',
              'btn-outline-warning': !isOptionSelected(option) && option.state === 'experimental',
              'btn-secondary': option.state === 'unavailable'
            }"
            :disabled="option.state === 'unavailable'"
            @click="selectOption(option)"
          >
            {{ option.label }}
            <span v-if="option.state === 'experimental'" class="small fst-italic"> (exp)</span>
            <i v-if="isOptionSelected(option)" class="bi bi-check-lg ms-1"></i>
          </button>
        </div>

        <div class="d-flex justify-content-between align-items-center">
          <div class="text-muted small">
            <span v-if="getCurrentSelection()">
              Current: <strong>{{ getCurrentSelection() }}</strong>
            </span>
            <span v-else class="text-warning">
              <i class="bi bi-exclamation-triangle me-1"></i>Not configured
            </span>
          </div>
          <button
            type="button"
            class="btn btn-success"
            :disabled="!pendingChanges"
            @click="applyConfiguration"
          >
            <i class="bi bi-check-circle me-1"></i>Apply
          </button>
        </div>
      </div>
    </div>
    <div v-else class="alert alert-info">
      <i class="bi bi-info-circle me-2"></i>
      <strong>Click the expand button</strong> on the compressor node in the graph to view and configure pipeline modules.
    </div>
  </div>
</template>

<style scoped>
.vertical-pipeline {
  width: 100%;
}
.pipeline-item {
  width: 100%;
}
.pipeline-vertical-connector {
  position: absolute;
  left: 50px;
  top: -25px;
  width: 3px;
  height: 30px;
  background-color: #dee2e6;
  z-index: 0;
}
.pipeline-module .card-body span {
  white-space: normal;
  word-break: break-word;
  text-align: center;
}
.options-panel {
  background: #ffffff;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.options-panel .btn {
  white-space: nowrap;
}
.options-panel .btn.btn-outline-primary:hover,
.options-panel .btn.btn-outline-warning:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
</style>
