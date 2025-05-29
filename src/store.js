import { createStore } from 'vuex';

export default createStore({
  state: {
    fileData: null,
    compressedData: null,
    dimensions: null,
    precision: null,
    isTimeVarying: false,
    showDecompression: false,
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
    setCompressedData(state, compressedFile) {
      state.compressedData = compressedFile;
    },
    showDecompressionView(state, payload) {
      state.showDecompression = payload;
    },
  },
  actions: {},
  modules: {}
});
