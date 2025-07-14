import { createStore } from 'vuex';

export default createStore({
  state: {
    comparisonData: null,
    dimensions: null,
    fileData: null,
    isTimeVarying: false,
    precision: null,
  },
  
  mutations: {
    setComparisonData(state, payload) {
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
  },
  
  actions: {},
  modules: {}
});
