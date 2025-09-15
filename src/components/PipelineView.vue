<script>
export default {
  name: 'PipelineView',
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
      moduleOptions: {
        error_bound: [
          { label: 'Absolute', state: 'available', value: 'sz3:abs_error_bound' },
          { label: 'Relative', state: 'available', value: 'sz3:rel_error_bound' },
          { label: 'PSNR', state: 'available', value: 'sz3:psnr_error_bound' },
          { label: 'L2_NORM', state: 'available', value: 'sz3:l2_norm_error_bound' },
          { label: 'ABS_AND_REL', state: 'unavailable', value: 'sz3:abs_and_rel_error_bound' },
          { label: 'ABS_OR_REL', state: 'unavailable', value: 'sz3:abs_or_rel_error_bound' },
        ],
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
          { label: 'Default', state: 'available', value: '1' },
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
        this.$emit('pipeline-modules-updated', this.compressor.modules);
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
      this.$emit('pipeline-modules-updated', this.compressor.modules);
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

    <div class="row">
      <div class="col-md-5">
        <div class="vertical-pipeline d-flex flex-column align-items-start">
          <template v-for="(module, moduleIdx) in compressor.modules" :key="module.id">
            <div :class="['pipeline-item d-flex align-items-center', moduleIdx < compressor.modules.length - 1 ? 'mb-4' : 'mb-1']" style="position: relative;">
              <div v-if="moduleIdx > 0" class="pipeline-vertical-connector"></div>
              <div
                class="pipeline-module card text-center border-2"
                :class="{'border-primary shadow': selectedModule && selectedModule.type === 'compressor' && 
                  selectedModule.idx && selectedModule.idx.moduleIdx === moduleIdx, 
                  'border-secondary': !selectedModule || selectedModule.type !== 'compressor' || 
                  !selectedModule.idx || selectedModule.idx.moduleIdx !== moduleIdx}"
                style="min-width: 120px; cursor: pointer;"
                @click="selectCompressorModule({moduleIdx})"
                @dragover.prevent="onModuleDragOver(module.id, $event)"
                @dragleave="onModuleDragLeave($event)"
                @drop="onDropCompressorOption({moduleIdx}, $event)"
                @mouseenter="onModuleMouseEnter(moduleIdx)"
                @mouseleave="onModuleMouseLeave(moduleIdx)"
              >
                <div class="card-body d-flex flex-column justify-content-center">
                  <span class="fw-bold" :title="module.label">{{ module.label }}</span>
                  <div v-if="Object.keys(module.value).length" class="mt-2 position-relative">
                    <div class="bg-light border rounded px-2 py-1 text-success w-100 d-flex align-items-center justify-content-center">
                      <span class="small">{{ Object.keys(module.value)[0] }}</span>
                      <button
                        type="button"
                        class="btn btn-link btn-sm text-danger ms-1 p-0"
                        title="Remove option"
                        @click.stop="removeModuleValue(moduleIdx)"
                      >
                        <span aria-hidden="true">&times;</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
      <div class="col-md-7">
        <div v-if="hoverModuleIdx !== null || (selectedModule && selectedModule.type === 'compressor')" class="options-panel card p-3">
          <h6 class="fw-bold mb-3">Available Options</h6>
          <div v-for="option in getOptionsForModule(compressor.modules[(selectedModule && selectedModule.type === 'compressor') ? selectedModule.idx.moduleIdx : hoverModuleIdx].id)" :key="option.label" class="option-item mb-2">
            <span
              class="badge px-3 py-2"
              :class="{
                'bg-info text-dark': option.state === 'available',
                'bg-warning text-dark': option.state === 'experimental',
                'bg-secondary': option.state === 'unavailable'
              }"
              draggable="true"
              :style="option.state === 'unavailable' ? 'pointer-events:none;opacity:0.6;' : option.state === 'unavailable' ? '' : 'cursor:pointer;'"
              @dragstart="option.state !== 'unavailable' && onOptionDragStart(option, compressor.modules[(selectedModule && selectedModule.type === 'compressor') ? selectedModule.idx.moduleIdx : hoverModuleIdx].id, $event)"
            >{{ option.label }}
              <span v-if="option.state === 'experimental'" class="small fst-italic">(experimental)</span>
              <span v-if="option.state === 'unavailable'" class="small fst-italic">(not supported)</span>
            </span>
          </div>
        </div>
        <div v-else class="text-muted">Select a module to view options.</div>
      </div>
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
  background: #f8f9fa;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.option-item .badge {
  white-space: normal;
  word-break: break-word;
  text-align: left;
}
</style>
