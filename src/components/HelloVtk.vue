
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
    <div ref="vtkContainer" class="h-100 position-relative mt-3">
      <!-- Options panel -->
      <div id="options-top" class="position-absolute w-100 d-flex justify-content-center flex-wrap gap-2 mt-3 z-3">
        <select id="colormapSelect" class="form-select w-auto" aria-label="colormap" ref="colormap">
          <option value="rainbow">Rainbow</option>
          <option value="Viridis (matplotlib)">Viridis</option>
          <option value="Plasma (matplotlib)">Plasma</option>
          <option value="Inferno (matplotlib)">Inferno</option>
          <option value="Grayscale">Grayscale</option>
        </select>
      
        <input type="number" min="0" id="slice_id" class="form-control" style="max-width: 120px" placeholder="Slice ID" />
        <button id="undo-button" class="btn btn-outline-light">Undo<i class="bi bi-arrow-counterclockwise"></i></button>
        <button id="reset-button" class="btn btn-outline-light">Reset<i class="bi bi-arrow-clockwise ms-1"></i></button>
      </div>

      <div id="options-bottom" class="position-absolute start-50 translate-middle-x w-50 bottom-0 d-flex justify-content-center flex-wrap mb-3 z-3">
      </div>
    </div>

  </div>
</template>
  
<script>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { useStore } from 'vuex';
import '@kitware/vtk.js/Rendering/Profiles/Volume';
import vtkColorMaps from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction/ColorMaps';
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow';
import vtkImageData from '@kitware/vtk.js/Common/DataModel/ImageData';
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray';
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume';
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction';
import vtkImageMapper from '@kitware/vtk.js/Rendering/Core/ImageMapper';
import vtkImageSlice from '@kitware/vtk.js/Rendering/Core/ImageSlice';

export default {
  name: 'HelloVtk',
  setup() {
    const store = useStore();
    const fileData = computed(() => store.state.fileData);
    const dimensions = computed(() => store.state.dimensions);
    const precision = computed(() => store.state.precision);
    // const compressedData = computed(() => store.state.compressedData);

    const vtkContainer = ref(null);
    const context = ref(null);
    const colormap = ref("rainbow");

    let cachedImageData = null;

    function createImageData(content, dimensions, precision) {
      const imageData = vtkImageData.newInstance();
      imageData.setDimensions(...dimensions);
      
      const scalars = (precision === 'f' ? new Float32Array(content) : new Float64Array(content));

      const dataArray = vtkDataArray.newInstance({
        numberOfComponents: 1,
        values: scalars,
        dataType: (precision === 'f' ? "Float32Array" : "Float64Array"),
      })

      imageData.getPointData().setScalars(dataArray);
      return imageData;
    }

    function createVolumeActor(imageData) {
      const mapper = vtkVolumeMapper.newInstance();
      mapper.setInputData(imageData);

      // Optimizing sampling settings
      const dims = imageData.getDimensions();
      const maxDim = Math.max(...dims);
      if (maxDim > 2000) {
        mapper.setSampleDistance(1.0);
        mapper.setImageSampleDistance(2.0);
        mapper.setAutoAdjustSampleDistances(true);
      }
      mapper.update();

      const actor = vtkVolume.newInstance();
      actor.setMapper(mapper);

      // Get the actual data range
      const dataRange = imageData.getPointData().getScalars().getRange();
      
      // Set color and opacity transfer functions
      const ctfun = vtkColorTransferFunction.newInstance();
      const ofun = vtkPiecewiseFunction.newInstance();

      const preset = vtkColorMaps.getPresetByName(colormap.value);
      ctfun.applyColorMap(preset);
      ctfun.setMappingRange(dataRange[0], dataRange[1]);

      ofun.addPoint(dataRange[0], 0.0);
      ofun.addPoint(dataRange[1], 0.8);

      actor.getProperty().setRGBTransferFunction(0, ctfun);
      actor.getProperty().setScalarOpacity(0, ofun);
      actor.getProperty().setScalarOpacityUnitDistance(1.0);
      actor.getProperty().setInterpolationTypeToLinear();

      return actor;
    }

    // Create 2D texture for image data
    function create2DTextureActor(imageData) {
      // Set color mapping function
      const dataRange = imageData.getPointData().getScalars().getRange();
      const ctfun = vtkColorTransferFunction.newInstance();
      const preset = vtkColorMaps.getPresetByName(colormap.value);
      ctfun.applyColorMap(preset);
      ctfun.setMappingRange(dataRange[0], dataRange[1]);

      const mapper = vtkImageMapper.newInstance();
      mapper.setInputData(imageData);
      mapper.setSlicingMode(vtkImageMapper.SlicingMode.K);
      mapper.setSlice(0);

      const actor = vtkImageSlice.newInstance();
      actor.setMapper(mapper);
      actor.getProperty().setRGBTransferFunction(0, ctfun);
      actor.getProperty().setInterpolationTypeToLinear();

      return actor;
    }

    function initializeVTK() {
      if (!context.value && vtkContainer.value?.offsetWidth > 0) {
        const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
          rootContainer: vtkContainer.value,
          containerStyle: {
            position: 'relative',
            width: '100%',
            height: '100%',
          },
        });

        const renderer = fullScreenRenderer.getRenderer();
        renderer.setBackground(0.2, 0.3, 0.4);
        const renderWindow = fullScreenRenderer.getRenderWindow();

        context.value = {
          fullScreenRenderer,
          renderer,
          renderWindow,
        };
      }
    }

    function renderData(content, dimensions, precision, forceUpdate = false) {
      if (!context.value) {
        console.error('VTK context not initialized!');
        return;
      }

      if (!cachedImageData || forceUpdate) {
        cachedImageData = createImageData(content, dimensions, precision);
      }

      const { renderer, renderWindow } = context.value;
      renderer.removeAllViewProps();

      // Disable the 2D visualization for now
      if (dimensions[0] == -1 || dimensions[1] == -1 || dimensions[2] == -1) {
        console.log('Creating 2D texture...');
        const actor = create2DTextureActor(cachedImageData);
        renderer.addActor(actor);
        context.value.actor = actor;
      } else {
        console.log('Creating volume...');
        const actor = createVolumeActor(cachedImageData);
        renderer.addVolume(actor);
        context.value.actor = actor;
      }

      renderer.resetCamera();
      renderWindow.render();
    }

    onMounted(() => {
      // Delay init slightly to allow tab to become visible
      setTimeout(() => {
        initializeVTK();

        if (fileData.value && dimensions.value && precision.value) {
          renderData(fileData.value, dimensions.value, precision.value);
        }
      }, 200);
    });

    // Rerender the volume when the file content changes
    watch(fileData, (newVal) => {
      if (newVal && dimensions.value && precision.value) {
        renderData(newVal, dimensions.value, precision.value, true);
      }
    });

    // Rerender the volume when the colormap changes
    watch(colormap, (newVal) => {
      console.log("colormap changes to", newVal);
      renderData(fileData, dimensions.value, precision.value);
    });

    onBeforeUnmount(() => {
      if (context.value) {
        const { fullScreenRenderer, actor } = context.value;
        if (actor) actor.delete();
        fullScreenRenderer.delete();
        context.value = null;
      }
    });

    return {
      vtkContainer,
      createImageData,
      create2DTextureActor,
    };
  },
};
</script>
