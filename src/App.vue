<script>

import Header from './components/AppHeader.vue'
import InputDataset from './components/InputDataset.vue'
import CustomizeCompressor from './components/CustomizeCompressor.vue'
import StatA from './components/StatA.vue'
import DataVis from './components/DataVis.vue'
// import DataSelection from './components/DataSelection.vue'
export default {
  name: 'App',
  
  components: {
    Header,
    InputDataset,
    CustomizeCompressor,
    StatA,
    DataVis,
    // DataSelection
  },
  
}
</script>

<template>
  <div class="container py-2 px-2 mx-auto">
    <Header />

    <div class="row">
      <div class="col-sm-4">
        <ul class="nav nav-tabs" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="dataset-tab" data-bs-toggle="tab" data-bs-target="#dataset" type="button" role="tab" aria-selected="true">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-file-earmark me-1" viewBox="0 0 16 16">
                <path d="M14 4.5V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2h5.5zm-3 0A1.5 1.5 0 0 1 9.5 3V1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V4.5z"/>
              </svg>Dataset</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="compressor-tab" data-bs-toggle="tab" data-bs-target="#compressor" type="button" role="tab" aria-selected="true">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-file-earmark-zip px-0 me-1" viewBox="0 0 16 16">
                <path d="M5 7.5a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v.938l.4 1.599a1 1 0 0 1-.416 1.074l-.93.62a1 1 0 0 1-1.11 0l-.929-.62a1 1 0 0 1-.415-1.074L5 8.438zm2 0H6v.938a1 1 0 0 1-.03.243l-.4 1.598.93.62.929-.62-.4-1.598A1 1 0 0 1 7 8.438z"/>
                <path d="M14 4.5V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2h5.5zm-3 0A1.5 1.5 0 0 1 9.5 3V1h-2v1h-1v1h1v1h-1v1h1v1H6V5H5V4h1V3H5V2h1V1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V4.5z"/>
              </svg>Compressor</button>
          </li>
        </ul>
        
        <div class="tab-content">
          <div id="dataset" class="tab-pane fade show active" role="tabpanel" aria-labelledby="dataset-tab">
            <InputDataset />
          </div>
          <div id="compressor" class="tab-pane fade" role="tabpanel" aria-labelledby="compressor-tab">
            <CustomizeCompressor />
          </div>
        </div>
      </div>

      <div class="col-sm-8">
        <ul class="nav nav-tabs" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="datavis-tab" data-bs-toggle="tab" data-bs-target="#datavis" type="button" role="tab" aria-selected="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-eye px-0 me-1" viewBox="0 0 16 16">
              <path d="M16 8s-3-5.5-8-5.5S0 8 0 8s3 5.5 8 5.5S16 8 16 8M1.173 8a13 13 0 0 1 1.66-2.043C4.12 4.668 5.88 3.5 8 3.5s3.879 1.168 5.168 2.457A13 13 0 0 1 14.828 8q-.086.13-.195.288c-.335.48-.83 1.12-1.465 1.755C11.879 11.332 10.119 12.5 8 12.5s-3.879-1.168-5.168-2.457A13 13 0 0 1 1.172 8z"/>
              <path d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5M4.5 8a3.5 3.5 0 1 1 7 0 3.5 3.5 0 0 1-7 0"/>
            </svg>Data Visualization</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="metrics-tab" data-bs-toggle="tab" data-bs-target="#metrics" type="button" role="tab" aria-selected="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-bar-chart-line px-0 me-1" viewBox="0 0 16 16">
              <path d="M11 2a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v12h.5a.5.5 0 0 1 0 1H.5a.5.5 0 0 1 0-1H1v-3a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v3h1V7a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v7h1zm1 12h2V2h-2zm-3 0V7H7v7zm-5 0v-3H2v3z"/>
            </svg>Metrics</button>
          </li>
        </ul>
        
        <div class="tab-content">
          <div id="datavis" class="tab-pane fade show active" role="tabpanel" aria-labelledby="datavis-tab">
            <DataVis />
          </div>
          <div id="metrics" class="tab-pane fade" role="tabpanel" aria-labelledby="metrics-tab">
            <StatA />
          </div>
        </div>
      </div>
    </div>

    <!-- <DataSelection /> -->
  </div>


  <!-- Offcanvas HTML -->
  <div class="offcanvas offcanvas-end m-2 py-0" tabindex="-1" id="showMore" aria-labelledby="showMoreLabel">
    <div class="offcanvas-header">
      <h4 class="offcanvas-title" id="showMoreLabel">About FZ-VIS</h4>
      <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
    </div>
    <div class="offcanvas-body">
      <div>
        FZ-VIS is a web-based visualization tool for the FZ project. The tool allows users to configure, apply, and compare the performance of multiple compression algorithms on the dataset.
      </div>
      <div class="mt-2">
        <h5>Tutorial</h5>
        <div class="mx-2">
          Please check out <a class="text-info" data-bs-toggle="tooltip" data-bs-placement="top" title="To be updated">this page</a> for text tutorial and <a class="text-info" data-bs-toggle="tooltip" data-bs-placement="right" title="To be updated">this video</a> for video tutorial.
        </div>
      </div>
      <div class="mt-2">
        <h5>Contributors</h5>
        <div class="mx-2">
          <p class="fw-bold my-1">The Ohio State University</p>
          <ul class="my-0">
            <li class="fw-bold fst-italic">PI: Hanqi Guo</li>
            <li>Yuxiao Li</li>
            <li>Guoxi Liu</li>
            <li>Hrithik Devaiah Bollachettira Ajithkumar</li>
          </ul>
          <p class="fw-bold my-1">Argonne National Laboratory</p>
          <ul class="my-0">
            <li>Robert Underwood</li>
          </ul>
        </div>
      </div>
    </div>
    <div class="offcanvas-footer px-2">
      <p class="text-muted">Powered by <a href="https://getbootstrap.com/" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-bootstrap me-1 mb-1" viewBox="0 0 16 16">
        <path d="M5.062 12h3.475c1.804 0 2.888-.908 2.888-2.396 0-1.102-.761-1.916-1.904-2.034v-.1c.832-.14 1.482-.93 1.482-1.816 0-1.3-.955-2.11-2.542-2.11H5.062zm1.313-4.875V4.658h1.78c.973 0 1.542.457 1.542 1.237 0 .802-.604 1.23-1.764 1.23zm0 3.762V8.162h1.822c1.236 0 1.887.463 1.887 1.348 0 .896-.627 1.377-1.811 1.377z"/>
        <path d="M0 4a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v8a4 4 0 0 1-4 4H4a4 4 0 0 1-4-4zm4-3a3 3 0 0 0-3 3v8a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3V4a3 3 0 0 0-3-3z"/>
      </svg>BootStrap</a> and <a href="https://vuejs.org/" target="_blank"><svg width="16" height="16" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" class="bi me-1 mb-1">
        <path d="M2 4L16 28L30 4H24.5L16 18.5L7.5 4H2Z" fill="#41B883"/>
        <path d="M7.5 4L16 18.5L24.5 4H19.5L16.0653 10.0126L12.5 4H7.5Z" fill="#35495E"/>
      </svg>Vue.js</a>. <br>Licensed MIT.</p>
    </div>
  </div>
  
</template>
