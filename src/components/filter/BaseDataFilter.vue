<template>
  <div>
    <slot />
  </div>
</template>

<script>
export default {
  name: 'BaseDataFilter',
  props: {
    /**
     * Human readable label for the operation.
     */
    filterName: {
      type: String,
      default: 'Data Filter',
    },
    /**
     * History kind to record when the operation succeeds.
     */
    filterType: {
      type: String,
      default: 'filter',
    },
    /**
     * Automatically reset local state whenever the dataset changes.
     */
    autoResetOnDatasetChange: {
      type: Boolean,
      default: true,
    },
    /**
     * Whether the base component should create a history entry after success.
     */
    recordHistory: {
      type: Boolean,
      default: true,
    },
    /**
     * Push status updates to the global store when operations run.
     */
    updateGlobalStatus: {
      type: Boolean,
      default: true,
    },
  },
  emits: [
    'filter-start',
    'filter-success',
    'filter-error',
    'filter-invalid',
    'filter-finish',
    'dataset-change',
  ],
  data() {
    return {
      isApplying: false,
      errorMessage: '',
      lastRunResult: null,
      formDirty: false,
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
    datasetSummary() {
      if (!Array.isArray(this.datasetDimensions) || this.datasetDimensions.length < 3) {
        return null;
      }
      const [width, height, depth] = this.datasetDimensions;
      return {
        width,
        height,
        depth,
        precision: this.datasetPrecision,
      };
    },
  },
  created() {
    if (!this.$store) return;
    this.operationTeardowns = [
      this.$watch(
        () => this.$store.state.dataset?.content,
        (next, previous) => this.handleDatasetChange(next, previous)
      ),
      this.$watch(
        () => this.$store.state.dataset?.dimensions,
        (next, previous) => this.handleDatasetChange(next, previous)
      ),
      this.$watch(
        () => this.$store.state.dataset?.precision,
        (next, previous) => this.handleDatasetChange(next, previous)
      ),
    ];
  },
  beforeUnmount() {
    if (!Array.isArray(this.operationTeardowns)) return;
    this.operationTeardowns.forEach((stop) => {
      if (typeof stop === 'function') stop();
    });
    this.operationTeardowns = [];
  },
  methods: {
    /**
     * Mark the underlying form as changed.
     */
    markDirty() {
      if (!this.formDirty) {
        this.formDirty = true;
      }
    },

    /**
     * Reset the dirty state.
     */
    clearDirty() {
      this.formDirty = false;
    },

    /**
     * Reset error and cached result state.
     */
    resetOperationState() {
      this.errorMessage = '';
      this.lastRunResult = null;
      this.clearDirty();
    },

    handleDatasetChange(next, previous) {
      this.$emit('dataset-change', { next, previous });
      if (this.autoResetOnDatasetChange) {
        this.resetOperationState();
      }
    },

    /**
     * Hook that can be overridden to perform custom validation before running.
     * Return true when valid, or a string/object describing the error otherwise.
     */
    // eslint-disable-next-line no-unused-vars
    validateOperation(context) {
      return true;
    },

    /**
     * Method that derived components must implement to perform their logic.
     */
    // eslint-disable-next-line no-unused-vars
    async performOperation(context) {
      throw new Error('performOperation(context) must be implemented by components extending BaseDataFilter.');
    },

    buildHistoryEntry(result, context) {
      const text = `${this.filterName} applied`;
      return {
        kind: this.filterType,
        text,
        timestamp: Date.now(),
        context: context || null,
        result: result ?? null,
      };
    },

    buildSuccessStatusMessage() {
      return `${this.filterName} completed successfully.`;
    },

    buildFailureStatusMessage(error) {
      return error?.message || `${this.filterName} failed.`;
    },

    setStatus(type, message) {
      if (!this.updateGlobalStatus || !this.$store || !type || !message) return;
      this.$store.commit('setStatus', { type, message });
    },

    recordHistoryEntry(entry) {
      if (!this.recordHistory || !this.$store || !entry) return;
      this.$store.commit('addHistory', entry);
    },

    async applyOperation(context = {}) {
      if (this.isApplying) return null;

      if (!this.hasDataset) {
        const message = 'No dataset loaded. Please upload data before running this operation.';
        this.errorMessage = message;
        this.setStatus('warning', message);
        this.$emit('filter-invalid', { message, context, reason: 'missing-dataset' });
        return null;
      }

      let validationResult;
      try {
        validationResult = await this.validateOperation(context);
      } catch (validationError) {
        validationResult = validationError?.message || validationError || 'Validation failed.';
      }

      if (validationResult !== true) {
        const message = typeof validationResult === 'string'
          ? validationResult
          : validationResult?.message || 'Invalid parameters for this operation.';
        this.errorMessage = message;
        this.setStatus('warning', message);
        this.$emit('filter-invalid', { message, context, details: validationResult });
        return null;
      }

      this.isApplying = true;
      this.errorMessage = '';
      this.$emit('filter-start', { context });

      try {
        const result = await this.performOperation(context);
        this.lastRunResult = result ?? null;
        this.clearDirty();

        // Track this filter operation in the store for undo functionality
        if (this.$store && this.filterType === 'filter') {
          this.$store.commit('addFilterOperation', {
            nodeId: this.$attrs['data-node-id'] || `${this.filterType}-${Date.now()}`,
            filterType: this.filterType,
            filterName: this.filterName,
            context: context || null,
            result: result || null,
            timestamp: Date.now(),
          });
        }

        const historyEntry = this.buildHistoryEntry(result, context);
        this.recordHistoryEntry(historyEntry);

        const successMessage = this.buildSuccessStatusMessage(result, context);
        this.setStatus('success', successMessage);
        this.$emit('filter-success', { result, context });
        return result ?? null;
      } catch (error) {
        this.lastRunResult = null;
        const failureMessage = this.buildFailureStatusMessage(error, context);
        this.errorMessage = failureMessage;
        this.setStatus('danger', failureMessage);
        this.$emit('filter-error', { error, context });
        throw error;
      } finally {
        this.isApplying = false;
        this.$emit('filter-finish', { context });
      }
    },
  },
};
</script>