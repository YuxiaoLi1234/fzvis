import { createStore } from 'vuex';

export default createStore({
  state: {
    fileData: null,
    compressedData: null,
    dimensions: null,
    precision: null,
    isTimeVarying: false,
    showDecompression: false,
    comparisonData: null,
  },
  mutations: {
    setFileData(state, payload) {
      state.fileData = payload.content;
      state.dimensions = payload.dimensions;
      state.precision = payload.precision;
    },
    setTimeVarying(state, payload) {
      state.isTimeVarying = payload;
    },
    setCompressedData(state, payload) {
      state.compressedData = payload;
    },
    setComparisonData(state, payload) {
      state.comparisonData = payload;
    },
    showDecompressionView(state, payload) {
      state.showDecompression = payload;
    },
  },
  actions: {},
  modules: {}
});
