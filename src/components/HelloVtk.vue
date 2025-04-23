
<template>
  <div class="vtk-wrapper" style="height:460px; position:relative;">
    <!-- Control panel -->
    <div id="controls" class="d-flex flex-wrap align-items-center mt-3 gap-2">
      <button id="input-button" class="btn btn-outline-primary">Input Mode<i class="bi bi-box-arrow-in-left ms-1"></i></button>
        <button id="output-button" class="btn btn-outline-primary">Output Mode<i class="bi bi-box-arrow-in-right ms-1"></i></button>
        <button id="error-button" class="btn btn-outline-primary">Error Map<i class="bi bi-map ms-1"></i>
        </button>
        
    </div>

    <!-- VTK visualization panel -->
    <div ref="vtkContainer" class="h-100 position-relative mt-3 rounded">
      <!-- Options panel -->
      <div id="options-top" class="position-absolute w-100 d-flex justify-content-center flex-wrap gap-2 mt-3 z-3">
        <select class="form-select w-auto"
          :value="representation"
          @change="setRepresentation($event.target.value)">
          <option value="0">Points</option>
          <option value="1">Wireframe</option>
          <option value="2">Surface</option>
        </select>
          
        <select id="colormapSelect" class="form-select w-auto" aria-label="colormap">
          <option value="Rainbow">Rainbow</option>
          <option value="Viridis">Viridis</option>
          <option value="Plasma">Plasma</option>
          <option value="Inferno">Inferno</option>
        </select>
      
        <input type="number" id="slice_id" class="form-control" style="max-width: 120px" placeholder="Slice ID" />
        <button id="undo-button" class="btn btn-outline-light">Undo<i class="bi bi-arrow-counterclockwise"></i></button>
        <button id="reset-button" class="btn btn-outline-light">Reset<i class="bi bi-arrow-clockwise ms-1"></i></button>
      </div>

      <div id="options-bottom" class="position-absolute start-50 translate-middle-x w-50 bottom-0 d-flex justify-content-center flex-wrap mb-3 z-3">
        <input type="range" class="form-range" min="4" max="80" :value="coneResolution" @input="setConeResolution($event.target.value)" />
      </div>
    </div>

  </div>
</template>
  
<script>
import { ref, onMounted, onBeforeUnmount, watchEffect } from 'vue';
import '@kitware/vtk.js/Rendering/Profiles/Geometry';
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow';
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor';
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper';
import vtkConeSource from '@kitware/vtk.js/Filters/Sources/ConeSource';

export default {
  name: 'HelloVtk',
  setup() {
    const vtkContainer = ref(null);
    const context = ref(null);

    const coneResolution = ref(6);
    const representation = ref(2);

    function setConeResolution(res) {
      coneResolution.value = Number(res);
    }

    function setRepresentation(rep) {
      representation.value = Number(rep);
    }

    watchEffect(() => {
      if (context.value) {
        const { actor, coneSource, renderWindow } = context.value;
        coneSource.setResolution(coneResolution.value);
        actor.getProperty().setRepresentation(representation.value);
        renderWindow.render();
      }
    });

    function initVTK() {
      if (!context.value && vtkContainer.value?.offsetWidth > 0) {
        const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
          rootContainer: vtkContainer.value,
          containerStyle: {
            position: 'relative',
            width: '100%',
            height: '100%',
          },
        });

        const coneSource = vtkConeSource.newInstance({ height: 1.0 });
        const mapper = vtkMapper.newInstance();
        mapper.setInputConnection(coneSource.getOutputPort());

        const actor = vtkActor.newInstance();
        actor.setMapper(mapper);

        const renderer = fullScreenRenderer.getRenderer();
        const renderWindow = fullScreenRenderer.getRenderWindow();

        renderer.addActor(actor);
        renderer.resetCamera();
        renderWindow.render();

        context.value = {
          fullScreenRenderer,
          renderWindow,
          renderer,
          coneSource,
          actor,
          mapper,
        };
      }
    }

    onMounted(() => {
      // Delay init slightly to allow tab to become visible
      setTimeout(initVTK, 200);
    });

    onBeforeUnmount(() => {
      if (context.value) {
        const { fullScreenRenderer, coneSource, actor, mapper } = context.value;
        actor.delete();
        mapper.delete();
        coneSource.delete();
        fullScreenRenderer.delete();
        context.value = null;
      }
    });

    return {
      vtkContainer,
      setRepresentation,
      setConeResolution,
      coneResolution,
      representation,
    };
  },
};
</script>
