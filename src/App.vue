<template>
  <InputDataset />
  <StatA />
  <DataVis />
  <!-- <DataSelection /> -->
  <CustomizeCompressor />
</template>

<script>

import StatA from './components/StatA.vue'
import DataVis from './components/DataVis.vue'
// import DataSelection from './components/DataSelection.vue'
import InputDataset from './components/InputDataset.vue'
import CustomizeCompressor from './components/CustomizeCompressor.vue'
export default {
  name: 'App',
  
  components: {
    InputDataset,
    StatA,
    DataVis,
    // DataSelection
    CustomizeCompressor
  },
  
}
</script>
<style>
body, html {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
}
</style>
