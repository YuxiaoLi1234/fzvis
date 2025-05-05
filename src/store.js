import { createStore } from 'vuex';

export default createStore({
  state: {
    fileData: null,
    compressedData: null,
    dimensions: null,
    precision: null,
  },
  mutations: {
    setFileData(state, payload) {
      state.fileData = payload.content;
      state.dimensions = payload.dimensions;
      state.precision = payload.precision;
    },
    setCompressedData(state, compressedFile) {
      state.compressedData = compressedFile;
    },
  },
  actions: {},
  modules: {}
});
