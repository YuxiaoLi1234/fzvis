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
    status: {
      type: String,
      default: 'pending',
    },
    config: {
      type: Object,
      default: null,
    },
    exploreState: {
      type: Object,
      default: null,
    },
  },
  emits: ['moduleSelected', 'pipeline-modules-updated', 'run-compressor', 'config-change', 'generate-configs', 'explore-state-changed'],
  data() {
    return {
      compressor: {
        id: 'sz3',
        label: 'SZ3 Compressor',
        modules: [
          { id: 'predictor', label: 'Predictor', key: 'sz3:algorithm_str', value: { 'Interpolation': 'ALGO_INTERP' } },
          { id: 'quantizer', label: 'Quantizer', key: 'sz3:quant_bin_size', value: { 'Linear-scaling': 65536 } },
          { id: 'encoder', label: 'Encoder', key: 'sz3:encoder', value: { 'Bypass': '0' } },
          { id: 'lossless', label: 'Lossless', key: 'sz3:lossless', value: { 'Bypass': '0' } },
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
          { label: 'Arithmetic', state: 'available', value: '2' },
        ],
        lossless: [
          { label: 'Bypass', state: 'available', value: '0' },
          { label: 'Zstd', state: 'available', value: '1' },
        ],
      },
      exploreEnabled: false,
      exploreSelections: {
        predictor: [],
        quantizer: [],
        encoder: [],
        lossless: [],
      },
      applyingExploreState: false,
      errorBoundMode: 'ABS',
      errorBoundValue: 1e-3,
      errorBoundOptions: [
        { label: 'Absolute (ABS)', value: 'ABS' },
        { label: 'Relative (REL)', value: 'REL' },
        { label: 'PSNR', value: 'PSNR' },
      ],
      nthreads: 1,
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
    this.applyConfig(this.config);
    this.seedExploreDefaults();
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
    config: {
      handler(newConfig) {
        this.applyConfig(newConfig);
      },
      deep: true,
    },
    errorBoundMode() { this.emitConfigChange(); },
    errorBoundValue() { this.emitConfigChange(); },
    nthreads() { this.emitConfigChange(); },
    exploreEnabled(enabled) {
      if (enabled) this.seedExploreDefaults();
      this.emitExploreState();
    },
    exploreSelections: {
      handler() {
        this.emitExploreState();
      },
      deep: true,
    },
    exploreState: {
      handler(state) {
        if (!state) return;
        this.applyExploreState(state);
      },
      immediate: true,
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
    },
    isReadyToRun() {
      const modulesReady = this.compressor.modules && this.compressor.modules.length > 0 && 
             this.compressor.modules.every(m => m.value && Object.keys(m.value).length > 0);
      const errorBoundReady = this.errorBoundValue !== null && this.errorBoundValue !== '';
      return modulesReady && errorBoundReady;
    },
    isRunning() {
      return this.status === 'running';
    },
    exploreCombinationCount() {
      const modules = this.compressor?.modules || [];
      if (!modules.length) return 0;
      let total = 1;
      for (const mod of modules) {
        const selected = this.exploreSelections?.[mod.id] || [];
        const current = this.getModuleCurrentValue(mod);
        const count = selected.length || (current !== null ? 1 : 0);
        if (count === 0) return 0;
        total *= count;
      }
      return total;
    },
    exploreAxes() {
      const modules = this.compressor?.modules || [];
      return modules.map((mod) => ({
        id: mod.id,
        key: mod.key,
        label: mod.label || mod.id,
        options: this.getOptionsForModule(mod.id) || [],
      }));
    },
    exploreSvgWidth() {
      const axisCount = this.exploreAxes.length || 1;
      return Math.max(560, 140 + (axisCount - 1) * 150);
    },
    exploreSvgHeight() {
      const maxOptions = Math.max(1, ...this.exploreAxes.map(axis => axis.options.length || 1));
      const padded = 70 + (maxOptions - 1) * 18;
      return Math.max(260, padded);
    },
    exploreSvgPadding() {
      return 50;
    },
    isPromoted() {
      return Boolean(this.$store?.state?.baseConfigurations?.[this.nodeId]);
    },
  },
  methods: {
    applyExploreState(state) {
      this.applyingExploreState = true;
      if (typeof state.enabled === 'boolean') this.exploreEnabled = state.enabled;
      if (Number.isFinite(state.maxCombos)) this.exploreMaxCombos = state.maxCombos;
      if (state.selections && typeof state.selections === 'object') {
        this.exploreSelections = JSON.parse(JSON.stringify(state.selections));
      }
      this.$nextTick(() => {
        this.applyingExploreState = false;
      });
    },
    emitExploreState() {
      if (this.applyingExploreState) return;
      this.$emit('explore-state-changed', {
        enabled: this.exploreEnabled,
        maxCombos: this.exploreMaxCombos,
        selections: JSON.parse(JSON.stringify(this.exploreSelections)),
      });
    },
    seedExploreDefaults() {
      const modules = this.compressor?.modules || [];
      modules.forEach((mod) => {
        const options = this.getOptionsForModule(mod.id);
        if (options.length === 1 && (!this.exploreSelections[mod.id] || this.exploreSelections[mod.id].length === 0)) {
          this.exploreSelections[mod.id] = [options[0].value];
        }
      });
    },
    getModuleCurrentValue(module) {
      if (!module?.value || !Object.keys(module.value).length) return null;
      const label = Object.keys(module.value)[0];
      return module.value[label];
    },
    buildBaseConfigFromCurrent() {
      const compressorConfig = {};
      for (const mod of this.compressor.modules) {
        const val = this.getModuleCurrentValue(mod);
        if (val === null || val === undefined) return null;
        compressorConfig[mod.key] = val;
      }
      if (this.errorBoundMode && this.errorBoundValue !== null) {
        compressorConfig['sz3:error_bound_mode_str'] = this.errorBoundMode;
        if (this.errorBoundMode === 'ABS') {
          compressorConfig['sz3:abs_error_bound'] = this.errorBoundValue;
        } else if (this.errorBoundMode === 'REL') {
          compressorConfig['sz3:rel_error_bound'] = this.errorBoundValue;
        } else if (this.errorBoundMode === 'PSNR') {
          compressorConfig['sz3:psnr_error_bound'] = this.errorBoundValue;
        }
      }
      if (this.nthreads) {
        compressorConfig['pressio:nthreads'] = this.nthreads;
      }
      return {
        compressor_id: this.compressor.id,
        compressor_config: compressorConfig,
        early_config: {
          'pressio:metric': 'composite',
          'composite:plugins': ['time', 'size', 'error_stat'],
        },
      };
    },
    generateCombinations() {
      const modules = this.compressor?.modules || [];
      if (!modules.length) return;

      const selectionsPerModule = [];
      for (const mod of modules) {
        const selected = this.exploreSelections?.[mod.id] || [];
        if (selected.length) {
          selectionsPerModule.push({ key: mod.key, values: selected });
          continue;
        }
        const currentVal = this.getModuleCurrentValue(mod);
        if (currentVal === null || currentVal === undefined) {
          this.setStatus('warning', `Select at least one option for ${mod.label}.`);
          return;
        }
        selectionsPerModule.push({ key: mod.key, values: [currentVal] });
      }

      const total = selectionsPerModule.reduce((acc, item) => acc * item.values.length, 1);
      if (total > this.exploreMaxCombos) {
        this.setStatus('warning', `Selection produces ${total} combinations; limit is ${this.exploreMaxCombos}.`);
        return;
      }

      const configs = [];
      const buildConfigs = (idx, current) => {
        if (idx === selectionsPerModule.length) {
          const compressorConfig = { ...current };
          if (this.errorBoundMode && this.errorBoundValue !== null) {
            compressorConfig['sz3:error_bound_mode_str'] = this.errorBoundMode;
            if (this.errorBoundMode === 'ABS') {
              compressorConfig['sz3:abs_error_bound'] = this.errorBoundValue;
            } else if (this.errorBoundMode === 'REL') {
              compressorConfig['sz3:rel_error_bound'] = this.errorBoundValue;
            } else if (this.errorBoundMode === 'PSNR') {
              compressorConfig['sz3:psnr_error_bound'] = this.errorBoundValue;
            }
          }
          if (this.nthreads) {
            compressorConfig['pressio:nthreads'] = this.nthreads;
          }
          configs.push({
            compressor_id: this.compressor.id,
            compressor_config: compressorConfig,
            early_config: {
              'pressio:metric': 'composite',
              'composite:plugins': ['time', 'size', 'error_stat'],
            },
          });
          return;
        }
        const { key, values } = selectionsPerModule[idx];
        values.forEach((val) => {
          buildConfigs(idx + 1, { ...current, [key]: val });
        });
      };
      buildConfigs(0, {});

      const baseConfig = this.buildBaseConfigFromCurrent() || configs[0] || null;
      if (!baseConfig) {
        this.setStatus('warning', 'Unable to build a base configuration from current settings.');
        return;
      }
      this.$emit('generate-configs', { baseConfig, configs });
      this.setStatus('success', `Generated ${configs.length} configurations for exploration.`);
    },
    exploreAxisX(index, width, padding) {
      const count = this.exploreAxes.length || 1;
      if (count <= 1) return padding;
      const span = width - padding * 2;
      return padding + (span * index) / (count - 1);
    },
    exploreOptionY(axis, index, height, padding) {
      const span = height - padding * 2;
      const count = axis?.options?.length || 0;
      if (count <= 1) return padding + span / 2;
      const t = index / (count - 1);
      return height - padding - t * span;
    },
    toggleExploreOption(axis, option) {
      const selected = this.exploreSelections[axis.id] || [];
      const value = option.value;
      const idx = selected.findIndex(v => v === value);
      if (idx >= 0) {
        selected.splice(idx, 1);
      } else {
        selected.push(value);
      }
      this.exploreSelections[axis.id] = [...selected];
    },
    isExploreOptionSelected(axis, option) {
      return (this.exploreSelections[axis.id] || []).includes(option.value);
    },
    exploreSelectedPath(width, height, padding) {
      const axes = this.exploreAxes;
      if (!axes.length) return null;
      const points = [];
      for (let i = 0; i < axes.length; i++) {
        const axis = axes[i];
        const selected = this.exploreSelections[axis.id] || [];
        const chosenValue = selected.length ? selected[0] : null;
        if (chosenValue === null) return null;
        const optIdx = axis.options.findIndex(opt => opt.value === chosenValue);
        if (optIdx < 0) return null;
        const x = this.exploreAxisX(i, width, padding);
        const y = this.exploreOptionY(axis, optIdx, height, padding);
        points.push(`${x},${y}`);
      }
      return `M ${points.join(' L ')}`;
    },
    exploreAllPaths(width, height, padding) {
      const axes = this.exploreAxes;
      if (!axes.length) return [];
      const selectionsPerAxis = axes.map(axis => ({
        axis,
        values: (this.exploreSelections[axis.id] || []).slice(),
      }));
      if (selectionsPerAxis.some(s => s.values.length === 0)) return [];

      const total = selectionsPerAxis.reduce((acc, s) => acc * s.values.length, 1);
      if (total > this.exploreMaxCombos) return [];

      const paths = [];
      const build = (idx, currentPoints) => {
        if (idx === selectionsPerAxis.length) {
          paths.push(`M ${currentPoints.join(' L ')}`);
          return;
        }
        const { axis, values } = selectionsPerAxis[idx];
        values.forEach((val) => {
          const optIdx = axis.options.findIndex(opt => opt.value === val);
          if (optIdx < 0) return;
          const x = this.exploreAxisX(idx, width, padding);
          const y = this.exploreOptionY(axis, optIdx, height, padding);
          build(idx + 1, [...currentPoints, `${x},${y}`]);
        });
      };
      build(0, []);
      return paths;
    },
    applyConfig(config) {
      if (!config || !config.compressor_config) return;
      const cfg = config.compressor_config;
      const mode = cfg['sz3:error_bound_mode_str'];
      if (mode) this.errorBoundMode = mode;
      if (cfg['sz3:abs_error_bound'] !== undefined) {
        this.errorBoundValue = Number(cfg['sz3:abs_error_bound']);
      } else if (cfg['sz3:rel_error_bound'] !== undefined) {
        this.errorBoundValue = Number(cfg['sz3:rel_error_bound']);
      } else if (cfg['sz3:psnr_error_bound'] !== undefined) {
        this.errorBoundValue = Number(cfg['sz3:psnr_error_bound']);
      }
      if (cfg['pressio:nthreads'] !== undefined) {
        this.nthreads = Number(cfg['pressio:nthreads']);
      }
    },
    emitConfigChange() {
      const compressorConfig = {};
      if (this.errorBoundMode && this.errorBoundValue !== null) {
        compressorConfig['sz3:error_bound_mode_str'] = this.errorBoundMode;
        if (this.errorBoundMode === 'ABS') {
          compressorConfig['sz3:abs_error_bound'] = this.errorBoundValue;
        } else if (this.errorBoundMode === 'REL') {
          compressorConfig['sz3:rel_error_bound'] = this.errorBoundValue;
        } else if (this.errorBoundMode === 'PSNR') {
          compressorConfig['sz3:psnr_error_bound'] = this.errorBoundValue;
        }
      }
      if (this.nthreads) {
        compressorConfig['pressio:nthreads'] = this.nthreads;
      }
      this.$emit('config-change', {
        compressor_id: this.compressor.id,
        compressor_config: compressorConfig,
      });
    },
    getCurrentModules() {
      return this.compressor.modules;
    },
    runCompressor() {
      const compressorConfig = {};
      this.compressor.modules.forEach(m => {
        if (m.value && Object.keys(m.value).length) {
          const [label] = Object.keys(m.value);
          compressorConfig[m.key] = m.value[label];
        }
      });

      // Add error bound configuration
      if (this.errorBoundMode && this.errorBoundValue !== null) {
        compressorConfig['sz3:error_bound_mode_str'] = this.errorBoundMode;
        if (this.errorBoundMode === 'ABS') {
          compressorConfig['sz3:abs_error_bound'] = this.errorBoundValue;
        } else if (this.errorBoundMode === 'REL') {
          compressorConfig['sz3:rel_error_bound'] = this.errorBoundValue;
        } else if (this.errorBoundMode === 'PSNR') {
          compressorConfig['sz3:psnr_error_bound'] = this.errorBoundValue;
        }
      }
      
      // Add nthreads
      if (this.nthreads) {
        compressorConfig['pressio:nthreads'] = this.nthreads;
      }

      const config = {
        compressor_id: this.compressor.id,
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
    <div v-else>
      <!-- Global Settings Section -->
      <div class="options-panel p-3 mb-3">
        <h6 class="fw-bold mb-3 d-flex align-items-center">
          <i class="bi bi-sliders me-2"></i>Global Settings
        </h6>
        <div class="row g-3">
          <div class="col-md-5">
            <label class="form-label small fw-semibold text-muted mb-1">Error Bound Mode</label>
            <select class="form-select form-select-sm" v-model="errorBoundMode">
              <option v-for="opt in errorBoundOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
          <div class="col-md-4">
            <label class="form-label small fw-semibold text-muted mb-1">Value</label>
            <input 
              type="number" 
              class="form-control form-control-sm" 
              v-model.number="errorBoundValue" 
              step="0.0001" 
              min="0"
            >
          </div>
          <div class="col-md-3">
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
            <input class="form-check-input" type="checkbox" id="sz3ExploreToggle" v-model="exploreEnabled">
            <label class="form-check-label small text-muted" for="sz3ExploreToggle">Enable</label>
          </div>
        </div>
        <p class="text-muted small mb-2">
          Pick multiple values per module and generate combinations automatically.
        </p>
        <div v-if="exploreEnabled">
          <div class="explore-parcoords mb-3">
            <svg :width="exploreSvgWidth" :height="exploreSvgHeight">
              <g>
                <line
                  v-for="(axis, idx) in exploreAxes"
                  :key="`explore-axis-${axis.id}`"
                  :x1="exploreAxisX(idx, exploreSvgWidth, exploreSvgPadding)"
                  y1="30"
                  :x2="exploreAxisX(idx, exploreSvgWidth, exploreSvgPadding)"
                  :y2="exploreSvgHeight - 30"
                  stroke="#adb5bd"
                  stroke-width="1"
                />
                <text
                  v-for="(axis, idx) in exploreAxes"
                  :key="`explore-axis-label-${axis.id}`"
                  :x="exploreAxisX(idx, exploreSvgWidth, exploreSvgPadding)"
                  y="18"
                  text-anchor="middle"
                  font-size="14"
                  fill="#495057"
                >
                  {{ axis.label }}
                </text>
                <g v-for="(axis, idx) in exploreAxes" :key="`explore-axis-options-${axis.id}`">
                  <text
                    v-for="(opt, optIdx) in axis.options"
                    :key="`explore-opt-${axis.id}-${opt.label}`"
                    :x="exploreAxisX(idx, exploreSvgWidth, exploreSvgPadding) + 6"
                    :y="exploreOptionY(axis, optIdx, exploreSvgHeight, exploreSvgPadding)"
                    text-anchor="start"
                    font-size="13"
                    :fill="isExploreOptionSelected(axis, opt) ? '#0d6efd' : '#6c757d'"
                    :font-weight="isExploreOptionSelected(axis, opt) ? '700' : '400'"
                    style="cursor: pointer;"
                    @click="toggleExploreOption(axis, opt)"
                  >
                    {{ opt.label }}
                  </text>
                </g>
                <path
                  v-for="(path, idx) in exploreAllPaths(exploreSvgWidth, exploreSvgHeight, exploreSvgPadding)"
                  :key="`explore-path-${idx}`"
                  :d="path"
                  :stroke="idx === 0 ? '#0d6efd' : 'rgba(13,110,253,0.25)'"
                  :stroke-width="idx === 0 ? 2 : 1"
                  fill="none"
                />
              </g>
            </svg>
          </div>
          <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
            <!-- <div class="d-flex align-items-center gap-2">
              <label class="form-label small fw-semibold text-muted mb-0">Max combinations</label>
              <input
                type="number"
                class="form-control form-control-sm"
                v-model.number="exploreMaxCombos"
                min="1"
                max="500"
                style="width: 110px;"
              >
            </div> -->
            <div class="text-muted small">
              Estimated combinations: <strong>{{ exploreCombinationCount }}</strong>
            </div>
            <button
              type="button"
              class="btn btn-outline-primary btn-sm"
              :disabled="exploreCombinationCount === 0"
              @click="generateCombinations"
            >
              Generate combinations
            </button>
          </div>
        </div>
      </div>

      <div class="alert alert-info d-flex justify-content-between align-items-center">
        <div>
          <i class="bi bi-info-circle me-2"></i>
          <span v-if="!isPromoted"><strong>Click the expand button</strong> on the compressor node in the graph to view and configure pipeline modules.</span>
          <span v-else>This node is <strong>promoted</strong> to the Config Graph for bulk generation.</span>
        </div>
        <button 
          v-if="!isPromoted"
          type="button"
          class="btn btn-primary shadow-sm px-3"
          :disabled="!isReadyToRun || isRunning"
          @click="runCompressor"
        >
          <span v-if="isRunning" class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
          <i v-else class="bi bi-play-fill me-1"></i>
          {{ isRunning ? 'Running...' : 'Run' }}
        </button>
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

.explore-parcoords {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  background: #fff;
  padding: 8px;
  overflow: auto;
  max-width: 100%;
}
.explore-parcoords svg {
  display: block;
}
</style>
