<script>
import Header from './components/AppHeader.vue'
import InputDataset from './components/InputDataset.vue'
import CustomizeCompressor from './components/CustomizeCompressor.vue'
import StatA from './components/StatA.vue'
import HelloVtk from './components/HelloVtk.vue'

export default {
  name: 'App',
  
  components: {
    Header,
    InputDataset,
    CustomizeCompressor,
    StatA,
    HelloVtk,
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
              <i class="bi bi-file-arrow-up me-1"></i>Dataset</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="compressor-tab" data-bs-toggle="tab" data-bs-target="#compressor" type="button" role="tab" aria-selected="true">
              <i class="bi bi-file-zip me-1"></i>Compressor</button>
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
            <button class="nav-link active" id="datavis-tab" data-bs-toggle="tab" data-bs-target="#datavis" type="button" role="tab" aria-selected="true"><i class="bi bi-eye me-1"></i>Data Visualization</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="metrics-tab" data-bs-toggle="tab" data-bs-target="#metrics" type="button" role="tab" aria-selected="true"><i class="bi bi-bar-chart-line me-1"></i>Metrics</button>
          </li>
        </ul>
        
        <div class="tab-content">
          <div id="datavis" class="tab-pane fade show active" role="tabpanel" aria-labelledby="datavis-tab">
            <!-- <DataVis /> -->
            <HelloVtk />
          </div>
          <div id="metrics" class="tab-pane fade" role="tabpanel" aria-labelledby="metrics-tab">
            <StatA />
          </div>
        </div>
      </div>
    </div>

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
