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
    isTimeVarying: false,
    status: { type: 'secondary', message: 'Idle' },
    history: [],
    progress: { active: false, percent: 0, message: '' },
    showConfigGraphInPane: false,
    baseConfigurations: {},
    derivedConfigurations: {},
    savedConfigurations: {},
    compressorOptions: {},
  },
  
  mutations: {
    setComparisonData(state, payload) {
      if (payload) {
        for (const key in payload) {
          if (payload[key].decp_data) {
            payload[key].decp_data = markRaw(payload[key].decp_data);
          }
        }
      }
      state.comparisonData = payload;
    },
    setFileData(state, payload) {
      if (!payload) return;
      let next = null;
      if (payload.dataset && typeof payload.dataset === 'object') {
        next = { ...payload.dataset };
      } else {
        next = {
          name: payload.name ?? state.dataset?.name ?? null,
          type: payload.type ?? state.dataset?.type ?? 'plain',
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
      // If the dataset is plain and no vars explicitly provided, clear vars
      if ((next?.type === 'plain' || next?.type === undefined) && payload?.vars === undefined) {
        next.vars = undefined;
      }
      state.dataset = next;
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
  },
  
  actions: {},
  modules: {}
});
