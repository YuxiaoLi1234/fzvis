<template>
  <StatA />
  <ParaMeter />
  <DataVis />
  <DataSelection />
</template>

<script>

import StatA from './components/StatA.vue'
import ParaMeter from './components/ParaMeter.vue'
import DataVis from './components/DataVis.vue'
import DataSelection from './components/DataSelection.vue'
// import VtkT from './components/VtkT.vue'
export default {
  name: 'App',
  
  components: {
    StatA,
    ParaMeter,
    DataVis,
    DataSelection,
    // VtkT
  },
  
}
</script>
<style>
html,body,#app{
  height: 100%;
  background-color: #FAFAFA;
}
</style>
