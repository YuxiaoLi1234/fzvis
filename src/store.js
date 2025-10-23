import { createStore } from 'vuex';
import { markRaw } from 'vue';

export default createStore({
  state: {
    comparisonData: null,
    dimensions: null,
    fileData: null,
    isTimeVarying: false,
    precision: null,
    status: { type: 'secondary', message: 'Idle' },
    history: [],
    progress: { active: false, percent: 0, message: '' },
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
      state.fileData = payload.content;
      state.dimensions = payload.dimensions;
      state.precision = payload.precision;
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
  },
  
  actions: {},
  modules: {}
});
