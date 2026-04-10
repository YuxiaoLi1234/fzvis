<template>
  <div>
    <slot />
  </div>
</template>

<script>
export default {
  name: 'BaseCompressorConfig',
  props: {
    compressorName: {
      type: String,
      default: 'Compressor',
    },
    compressorType: {
      type: String,
      default: 'compressor',
    },
    autoResetOnDatasetChange: {
      type: Boolean,
      default: true,
    },
    recordHistory: {
      type: Boolean,
      default: true,
    },
    updateGlobalStatus: {
      type: Boolean,
      default: true,
    },
    nodeId: {
      type: String,
      default: null,
    },
  },
  emits: [
    'config-start',
    'config-change',
    'config-invalid',
    'config-error',
    'config-finish',
    'pipeline-modules-updated',
    'moduleSelected',
  ],
  data() {
    return {
      isConfiguring: false,
      errorMessage: '',
      formDirty: false,
      lastConfig: null,
      operationTeardowns: [],
    };
  },
  computed: {
    datasetBuffer() {
      return this.$store?.state?.dataset?.content ?? null;
    },
    datasetDimensions() {
      return this.$store?.state?.dataset?.dimensions ?? null;
    },
    datasetPrecision() {
      return this.$store?.state?.dataset?.precision ?? null;
    },
    hasDataset() {
      return Boolean(this.datasetBuffer);
    },
  },
  created() {
    if (!this.$store) return;
    this.operationTeardowns = [
      this.$watch(
        () => this.$store.state.dataset?.content,
        () => this.handleDatasetChange()
      ),
      this.$watch(
        () => this.$store.state.dataset?.dimensions,
        () => this.handleDatasetChange()
      ),
      this.$watch(
        () => this.$store.state.dataset?.precision,
        () => this.handleDatasetChange()
      ),
    ];
  },
  beforeUnmount() {
    if (!Array.isArray(this.operationTeardowns)) return;
    this.operationTeardowns.forEach((stop) => typeof stop === 'function' && stop());
    this.operationTeardowns = [];
  },
  methods: {
    markDirty() {
      if (!this.formDirty) this.formDirty = true;
    },
    clearDirty() {
      this.formDirty = false;
    },
    resetOperationState() {
      this.errorMessage = '';
      this.clearDirty();
    },
    handleDatasetChange() {
      // Config may become invalid when dataset changes
      if (this.autoResetOnDatasetChange) {
        this.resetOperationState();
        try {
          const mods = this.getCurrentModules?.();
          if (mods) this.onModulesUpdated(mods);
        } catch (_) { /* no-op */ }
      }
    },
    setStatus(type, message) {
      if (!this.updateGlobalStatus || !this.$store || !type || !message) return;
      this.$store.commit('setStatus', { type, message });
    },
    recordHistoryEntry(entry) {
      if (!this.recordHistory || !this.$store || !entry) return;
      this.$store.commit('addHistory', entry);
    },
    buildHistoryEntry(modules) {
      const summary = Array.isArray(modules)
        ? modules.map(m => `${m.label || m.id}:${m && m.value ? Object.keys(m.value)[0] || '-' : '-'}`).join(', ')
        : 'Updated';
      return {
        kind: `${this.compressorType}.config`,
        text: `${this.compressorName} modules updated (${summary})`,
        timestamp: Date.now(),
        context: { modules },
      };
    },
    onModulesUpdated(modules) {
      // Unified hook for derived components to call when module selections change
      this.markDirty();
      this.$emit('config-change', { modules });
      this.$emit('pipeline-modules-updated', modules);
      const ready = Array.isArray(modules) && modules.length && modules.every(m => m && m.value && Object.keys(m.value).length);
      const message = ready ? `${this.compressorName} configuration complete.` : `${this.compressorName} configuration updated.`;
      this.setStatus(ready ? 'success' : 'info', message);
      this.recordHistoryEntry(this.buildHistoryEntry(modules));
    },
  },
};
</script>
