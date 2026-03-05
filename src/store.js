import { createStore } from 'vuex';
import { markRaw } from 'vue';

// Helper to format bytes into a human-readable string
function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return undefined;
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i += 1;
  }
  return `${val.toFixed(2)} ${units[i]}`;
}

export default createStore({
  state: {
    comparisonData: null,
    dataset: null,
    originalDataset: null, // Store the original unfiltered dataset
    filterOperations: [], // Stack of applied filter operations
    isTimeVarying: false,
    status: { type: 'secondary', message: 'Idle' },
    history: [],
    progress: { active: false, percent: 0, message: '' },
    showConfigGraphInPane: false,
    baseConfigurations: {},
    derivedConfigurations: {},
    savedConfigurations: {},
    compressorOptions: {},
    criticalPoints: {
      original: null,
      decompressed: {} // Map of compressorId -> cpData
    },
    bulkGenerationRequests: [],
  },

  mutations: {
    setOriginalDataset(state, payload) {
      // Store the original dataset when first loaded
      if (!payload) {
        state.originalDataset = null;
        return;
      }
      state.originalDataset = {
        name: payload.name ?? null,
        type: payload.type ?? 'raw',
        content: payload.content ?? null,
        dimensions: payload.dimensions ?? null,
        precision: payload.precision ?? null,
        size: payload.size,
        vars: payload.vars,
      };
      // Also clear filter operations
      state.filterOperations = [];
    },
    setComparisonData(state, payload) {
      if (!payload) {
        state.comparisonData = null;
        return;
      }

      const next = state.comparisonData ? { ...state.comparisonData } : {};
      for (const key in payload) {
        const item = { ...payload[key] };
        if (item.decp_data) {
          item.decp_data = markRaw(item.decp_data);
        }
        next[key] = item;
      }
      state.comparisonData = next;
    },
    removeComparisonData(state, nodeId) {
      if (state.comparisonData && nodeId in state.comparisonData) {
        const next = { ...state.comparisonData };
        delete next[nodeId];
        state.comparisonData = Object.keys(next).length > 0 ? next : null;
      }
      // Clean up associated critical points, regardless of comparisonData existence
      if (state.criticalPoints?.decompressed && nodeId in state.criticalPoints.decompressed) {
        delete state.criticalPoints.decompressed[nodeId];
      }
    },
    setFileData(state, payload) {
      if (!payload) return;
      let next = null;
      if (payload.dataset && typeof payload.dataset === 'object') {
        next = { ...payload.dataset };
      } else {
        next = {
          name: payload.name ?? state.dataset?.name ?? null,
          type: payload.type ?? state.dataset?.type ?? 'raw',
          content: payload.content ?? state.dataset?.content ?? null,
          dimensions: payload.dimensions ?? state.dataset?.dimensions ?? null,
          precision: payload.precision ?? state.dataset?.precision ?? null,
          size: payload.size ?? state.dataset?.size,
          vars: payload.vars ?? state.dataset?.vars,
        };
      }
      try {
        const byteLength = next?.content instanceof ArrayBuffer ? next.content.byteLength : undefined;
        if (Number.isFinite(byteLength)) {
          next.size = formatBytes(byteLength);
        }
      } catch (_) { /* no-op */ }
      // If the dataset is raw and no vars explicitly provided, clear vars
      if ((next?.type === 'raw' || next?.type === undefined) && payload?.vars === undefined) {
        next.vars = undefined;
      }

      // Check if this is a new dataset being loaded (not a filter operation result)
      // Set original dataset and clear filter operations when loading new data
      const isNewDataset = payload.content &&
        (!state.dataset ||
          payload.content !== state.dataset.content ||
          payload.name !== state.dataset.name);

      if (isNewDataset && !payload.isFilterResult) {
        // Store as original dataset
        state.originalDataset = {
          name: next.name,
          type: next.type,
          content: next.content,
          dimensions: next.dimensions,
          precision: next.precision,
          size: next.size,
          vars: next.vars,
        };
        state.filterOperations = [];
        state.criticalPoints = { original: null, decompressed: {} };
      }

      state.dataset = next;
    },
    clearFileData(state) {
      state.dataset = null;
      state.originalDataset = null;
      state.filterOperations = [];
      state.criticalPoints = { original: null, decompressed: {} };
    },
    addFilterOperation(state, operation) {
      // Add a filter operation to the stack
      // operation should contain: { nodeId, filterType, context, result }
      if (!operation) return;
      state.filterOperations.push(operation);
    },
    removeFilterOperation(state, nodeId) {
      // Remove a filter operation by nodeId
      const index = state.filterOperations.findIndex(op => op.nodeId === nodeId);
      if (index !== -1) {
        state.filterOperations.splice(index, 1);
      }
    },
    clearFilterOperations(state) {
      state.filterOperations = [];
    },
    setTimeVarying(state, payload) {
      state.isTimeVarying = payload;
    },
    setStatus(state, payload) {
      state.status = payload || { type: 'secondary', message: '' };
    },
    addHistory(state, item) {
      if (!item) return;
      // ensure timestamp exists
      if (!item.timestamp) item.timestamp = Date.now();
      state.history.push(item);
    },
    clearHistory(state) {
      state.history = [];
    },
    setProgress(state, payload) {
      if (!payload) {
        state.progress = { active: false, percent: 0, message: '' };
        return;
      }
      const next = { ...state.progress };
      if (payload.active !== undefined) next.active = payload.active;
      else next.active = true;
      if (payload.percent !== undefined) {
        const p = Math.max(0, Math.min(100, Math.round(payload.percent)));
        next.percent = p;
      }
      if (payload.message !== undefined) next.message = payload.message;
      state.progress = next;
    },
    clearProgress(state) {
      state.progress = { active: false, percent: 0, message: '' };
    },
    setShowConfigGraphInPane(state, payload) {
      state.showConfigGraphInPane = Boolean(payload);
    },
    addBaseConfiguration(state, { name, config }) {
      state.baseConfigurations = { ...state.baseConfigurations, [name]: config };
      // initialize derived map if doesn't exist
      if (!(name in state.derivedConfigurations)) {
        state.derivedConfigurations = { ...state.derivedConfigurations, [name]: {} };
      }
    },
    addDerivedConfiguration(state, { baseName, derivedName, config }) {
      if (!(baseName in state.derivedConfigurations)) {
        state.derivedConfigurations[baseName] = {};
      }
      state.derivedConfigurations[baseName] = {
        ...state.derivedConfigurations[baseName],
        [derivedName]: config
      };
      state.savedConfigurations = { ...state.savedConfigurations, [derivedName]: config };
    },
    setCriticalPoints(state, payload) {
      if (!payload) {
        state.criticalPoints = { original: null, decompressed: {} };
        return;
      }
      const { source, data } = payload;
      if (source === 'original') {
        state.criticalPoints.original = data;
      } else if (source) {
        state.criticalPoints.decompressed = {
          ...state.criticalPoints.decompressed,
          [source]: data
        };
      } else {
        // Fallback for backward compatibility if source is not provided
        state.criticalPoints.original = payload;
      }
    },
    requestBulkGeneration(state, payload) {
      state.bulkGenerationRequests.push({
        id: Date.now(),
        ...payload
      });
    },
    clearBulkGenerationRequest(state, requestId) {
      state.bulkGenerationRequests = state.bulkGenerationRequests.filter(r => r.id !== requestId);
    },
  },

  actions: {
    /**
     * Replay the entire filter pipeline from the original dataset.
     * This is called when a filter is removed or the pipeline needs to be rebuilt.
     * @param {Object} context - Vuex action context
     * @param {Object} options - { filterComponents: Map<filterType, ComponentClass> }
     */
    async replayFilterPipeline({ state, commit }, options = {}) {
      const { filterComponents = new Map() } = options;

      // Start from original dataset
      if (!state.originalDataset || !state.originalDataset.content) {
        console.warn('No original dataset available for replay');
        return;
      }

      // Reset to original
      commit('setFileData', {
        content: state.originalDataset.content,
        dimensions: state.originalDataset.dimensions,
        precision: state.originalDataset.precision,
        name: state.originalDataset.name,
        type: state.originalDataset.type,
        isFilterResult: true,
      });

      // Replay each filter operation in sequence
      for (const op of state.filterOperations) {
        const component = filterComponents.get(op.filterType);
        if (!component || typeof component.applyFilter !== 'function') {
          console.warn(`Cannot replay filter ${op.filterType}: no static applyFilter method`);
          continue;
        }

        try {
          // Call the static apply method with stored parameters
          const result = await component.applyFilter(state.dataset, op.params);

          // Update dataset with filtered result
          commit('setFileData', {
            content: result.content,
            dimensions: result.dimensions,
            precision: result.precision,
            name: result.name || state.dataset.name,
            type: result.type || state.dataset.type,
            isFilterResult: true,
          });
        } catch (error) {
          console.error(`Failed to replay filter ${op.filterType}:`, error);
          // Continue with remaining filters despite error
        }
      }
    },
  },
  modules: {}
});
