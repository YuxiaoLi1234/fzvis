
<template>
  <div class="vtk-wrapper">
    <!-- Control panel -->
    <!-- <div id="controls" class="d-flex flex-wrap align-items-center mt-3 gap-2">
      <button id="input-button" class="btn btn-outline-primary">Input Mode<i class="bi bi-box-arrow-in-left ms-1"></i></button>
        <button id="output-button" class="btn btn-outline-primary">Output Mode<i class="bi bi-box-arrow-in-right ms-1"></i></button>
        <button id="error-button" class="btn btn-outline-primary">Error Map<i class="bi bi-map ms-1"></i>
        </button>
    </div> -->

    <div id="options-top" class="d-flex flex-wrap justify-content-center mt-3 gap-2">
      <select class="form-select w-auto" aria-label="colormap" v-model="colormap">
        <option value="rainbow">Rainbow</option>
        <option value="Viridis (matplotlib)">Viridis</option>
        <option value="Plasma (matplotlib)">Plasma</option>
        <option value="Inferno (matplotlib)">Inferno</option>
        <option value="Grayscale">Grayscale</option>
      </select>
      <!-- <select class="form-select w-auto" aria-label="colormap" v-model="colormap">
        <option v-for="preset in allPresets" :value="preset" :key="preset">{{ preset }}</option>
      </select> -->
      <input id="sliceID" type="number" min="0" class="form-control" style="max-width: 120px" placeholder="Slice ID" />
      <button :class="['btn', sameCamera ? 'btn-primary' : 'btn-outline-primary']" @click="syncCamera">Sync camera<i class="bi bi-camera ms-1"></i></button>
      <button id="undoBtn" class="btn btn-outline-info">Undo<i class="bi bi-arrow-counterclockwise ms-1"></i></button>
      <button id="resetBtn" class="btn btn-outline-info">Reset<i class="bi bi-arrow-clockwise ms-1"></i></button>
    </div>


    <!-- VTK visualization panel -->
    <div class="position-relative mt-3">
        <div class="card mb-3" style="height: 360px;">
          <div class="card-header">
            Original
          </div>
          <div class="card-body">
            <div ref="vtkContainerOriginal"></div>
          </div>
        </div>

        <div class="card mt-3" style="height: 360px;">
          <div class="card-header">
            Decompressed
          </div>
          <div class="card-body">
            <div ref="vtkContainerCompressed"></div>
          </div>
        </div>

      <!-- <div id="options-bottom" class="position-absolute start-50 translate-middle-x w-50 bottom-0 d-flex justify-content-center flex-wrap mb-3 z-3">
      </div> -->
    </div>

  </div>
</template>
  
<script>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { useStore } from 'vuex';
import * as d3 from 'd3-scale';
import { formatDefaultLocale } from 'd3-format';
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
import { SlicingMode } from '@kitware/vtk.js/Rendering/Core/ImageMapper/Constants';

export default {
  name: 'HelloVtk',
  setup() {
    const store = useStore();
    const fileData = computed(() => store.state.fileData);
    const dimensions = computed(() => store.state.dimensions);
    const precision = computed(() => store.state.precision);
    const compressedData = computed(() => store.state.compressedData);

    const vtkContainerOriginal = ref(null);
    const vtkContainerCompressed = ref(null);
    const context = ref(null);
    const colormap = ref("rainbow");
    let sameCamera = ref(false);
    
    let oldCamera = null;
    let cachedImageData = null;
    let cachedCompressedData = null;

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

    // Change the number of ticks (TODO: add numberOfTicks to ScalarBarActor)
    function generateTicks(numberOfTicks, useLogScale = false) {
      return (helper) => {
        const lastTickBounds = helper.getLastTickBounds();
        // compute tick marks for axes
        const scale = useLogScale ? d3.scaleLog() : d3.scaleLinear();
        scale.domain([lastTickBounds[0], lastTickBounds[1]]).range([0, 1]);

        const ticks = scale.ticks(numberOfTicks);
        const tickPositions = ticks.map((tick) => scale(tick));

        // Replace minus "\u2212" with hyphen-minus "\u002D" so that parseFloat() works
        formatDefaultLocale({ minus: '\u002D' });
        const format = scale.tickFormat(ticks[0], ticks[ticks.length - 1]);
        const tickStrings = ticks.map(format).map((tick) => {
          if (tick === '') {
            return '';
          }
          return Number(parseFloat(tick).toPrecision(12)).toPrecision();
        }); // d3 sometimes adds unwanted whitespace

        helper.setTicks(ticks);
        helper.setTickStrings(tickStrings);
        helper.setTickPositions(tickPositions);
      };
    }

    // Create 2D visualizaiton for image data
    function create2DImageActor(imageData) {
      // Set color mapping function
      const dataRange = imageData.getPointData().getScalars().getRange();
      // console.log("data range:", dataRange[0], dataRange[1]);

      const ctfunc = vtkColorTransferFunction.newInstance();
      const preset = vtkColorMaps.getPresetByName(colormap.value);
      ctfunc.applyColorMap(preset);
      ctfunc.setRange(dataRange[0], dataRange[1]);
      ctfunc.setMappingRange(dataRange[0], dataRange[1]);
      ctfunc.updateRange();

      const otfunc = vtkPiecewiseFunction.newInstance();
      otfunc.addPoint(dataRange[0], 0.0);
      otfunc.addPoint(dataRange[1], 1.0);
      otfunc.updateRange();

      const mapper = vtkImageMapper.newInstance();
      mapper.setInputData(imageData);
      mapper.setSliceAtFocalPoint(true);
      mapper.setSlicingMode(SlicingMode.Z);

      // Update the existing scalar bar
      const scalarBarActor = context.value.original.barActor;
      if (scalarBarActor) {
        scalarBarActor.setAxisLabel("Intensity");
        scalarBarActor.setScalarsToColors(ctfunc);
        scalarBarActor.setGenerateTicks(generateTicks(10, false));
        scalarBarActor.modified(); // Force update
      }

      const imageActor = vtkImageSlice.newInstance();
      imageActor.setMapper(mapper);
      const window = dataRange[1] - dataRange[0];
      const level = (dataRange[0] + dataRange[1]) / 2;
      imageActor.getProperty().setColorWindow(window);
      imageActor.getProperty().setColorLevel(level);
      imageActor.getProperty().setRGBTransferFunction(0, ctfunc);
      imageActor.getProperty().setPiecewiseFunction(0, otfunc);
      imageActor.getProperty().setInterpolationTypeToLinear();

      return imageActor;
    }

    // Create 3D visualizaiton for volume data
    function createVolumeActor(imageData) {
      const mapper = vtkVolumeMapper.newInstance();
      mapper.setInputData(imageData);

      const volumeActor = vtkVolume.newInstance();
      volumeActor.setMapper(mapper);

      // Get the actual data range
      const dataRange = imageData.getPointData().getScalars().getRange();
      // console.log("data range:", dataRange[0], dataRange[1]);
      
      // Set color and opacity transfer functions
      const ctfunc = vtkColorTransferFunction.newInstance();
      const otfunc = vtkPiecewiseFunction.newInstance();

      const preset = vtkColorMaps.getPresetByName(colormap.value);
      ctfunc.applyColorMap(preset);
      ctfunc.setMappingRange(dataRange[0], dataRange[1]);
      ctfunc.updateRange();

      otfunc.addPoint(dataRange[0], 0.0);
      otfunc.addPoint(dataRange[1], 1.0);

      volumeActor.getProperty().setRGBTransferFunction(0, ctfunc);
      volumeActor.getProperty().setScalarOpacity(0, otfunc);
      volumeActor.getProperty().setScalarOpacityUnitDistance(1.0);
      volumeActor.getProperty().setInterpolationTypeToLinear();

      return volumeActor;
    }

    function initializeVTK() {
      // Only initialize the context once 
      if (!context.value) {
        const contextData = {};

        // Initialize the renderer for original dataset
        if (vtkContainerOriginal.value?.offsetWidth > 0) {
          const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
            rootContainer: vtkContainerOriginal.value,
            containerStyle: {
              position: "absolute", 
              width: "95%",
              height: "80%",
              overflow: "hidden",
            },
          });
  
          const renderer = fullScreenRenderer.getRenderer();
          renderer.setBackground(0.2, 0.3, 0.4);
          const renderWindow = fullScreenRenderer.getRenderWindow();
          contextData.original = {
            fullScreenRenderer,
            renderer,
            renderWindow,
          };
        }

        // Initialize the renderer for (de)compressed dataset
        if (vtkContainerCompressed.value?.offsetWidth > 0) {
          const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
            rootContainer: vtkContainerCompressed.value,
            containerStyle: {
              position: "absolute", 
              width: "95%",
              height: "80%",
              overflow: "hidden",
            },
          });
  
          const renderer = fullScreenRenderer.getRenderer();
          renderer.setBackground(0.2, 0.3, 0.4);
          const renderWindow = fullScreenRenderer.getRenderWindow();
          contextData.compressed = {
            fullScreenRenderer,
            renderer,
            renderWindow,
          };
        }

        context.value = contextData;
      }
    }

    function renderOriginal(content, dimensions, precision, forceUpdate = false) {
      if (!context.value.original) {
        console.error('VTK context for original dataset not initialized!');
        return;
      }

      if (!cachedImageData || forceUpdate) {
        cachedImageData = createImageData(content, dimensions, precision);
      }

      const { renderer, renderWindow } = context.value.original;
      renderer.removeAllViewProps();

      // const scalarBarActor = vtkScalarBarActor.newInstance();
      // scalarBarActor.setVisibility(true);
      // scalarBarActor.setPosition(0.9, 0.1, 0);  // Right side
      // scalarBarActor.setBoxSize(0.08, 0.5);
      // renderer.addActor(scalarBarActor);
      // context.value.original.barActor = scalarBarActor;  // Store for later updates

      let actor;
      const sliceInput = document.getElementById("sliceID");
      // Enable the 2D visualization if one of the dimension is 1
      if (dimensions[0] == 1 || dimensions[1] == 1 || dimensions[2] == 1) {
        if (sliceInput) {
          sliceInput.disabled = true;
        }
        actor = create2DImageActor(cachedImageData);
        renderer.addActor(actor);
        context.value.original.actor = actor;
      }
      // Otherwise, render 3D volume
      else {
        if (sliceInput) {
          sliceInput.disabled = false;
        }
        actor = createVolumeActor(cachedImageData);
        renderer.addVolume(actor);
        context.value.original.actor = actor;
      }

      renderer.resetCamera();
      renderWindow.render();
    }


    function renderCompressed(content, dimensions, precision, forceUpdate = false) {
      if (!context.value.compressed) {
        console.error('VTK context for decompressed dataset not initialized!');
        return;
      }

      if (!cachedCompressedData || forceUpdate) {
        cachedCompressedData = createImageData(content, dimensions, precision);
      }

      const { renderer, renderWindow } = context.value.compressed;
      renderer.removeAllViewProps();

      let actor;
      // Enable the 2D visualization if one of the dimension is 1
      if (dimensions[0] == 1 || dimensions[1] == 1 || dimensions[2] == 1) {
      // To disable the 2D visualization for now
      // if (dimensions[0] == -1) {
        actor = create2DImageActor(cachedCompressedData);
        renderer.addActor(actor);
        context.value.compressed.actor = actor;
      }
      // Otherwise, render 3D volume
      else {
        actor = createVolumeActor(cachedCompressedData);
        renderer.addVolume(actor);
        context.value.compressed.actor = actor;
      }

      renderer.resetCamera();
      renderWindow.render();
    }

    function syncCamera() {
      if (!context.value) {
        console.error("VTK context not initialized!");
        return;
      }

      if (sameCamera.value) {
        const { renderer, renderWindow } = context.value.compressed;
        renderer.setActiveCamera(oldCamera);
        renderWindow.render();
      }
      else {
        const sharedCamera = context.value.original.renderer.getActiveCamera();
        const { renderer, renderWindow } = context.value.compressed;
        oldCamera = renderer.getActiveCamera();
        renderer.setActiveCamera(sharedCamera);
        renderWindow.render();
        sharedCamera.onModified(() => {
          context.value.original.renderWindow.render();
          context.value.compressed.renderWindow.render();
        });
      }
      sameCamera.value = !sameCamera.value;
    }

    onMounted(() => {
      // Delay init slightly to allow tab to become visible
      setTimeout(() => {
        initializeVTK();
        if (fileData.value && dimensions.value && precision.value) {
          renderOriginal(fileData.value, dimensions.value, precision.value);
        }
      }, 200);
    });

    // Rerender the volume when the file info changes
    watch([fileData, dimensions, precision], ([newFileData, newDimensions, newPrecision]) => {
      if (newFileData && newDimensions && newPrecision) {
        renderOriginal(newFileData, newDimensions, newPrecision, true);
      }
    });

    watch([compressedData, dimensions, precision], ([newFileData, newDimensions, newPrecision]) => {
      if (newFileData && newDimensions && newPrecision) {
        renderCompressed(newFileData, newDimensions, newPrecision, true);
      }
    });

    // Rerender the volume when the colormap changes
    watch(colormap, (newColormap) => {
      console.log("Colormap is changed to:", newColormap)
      if (newColormap && cachedImageData) {
        // Create a new color transfer function
        const dataRange = cachedImageData.getPointData().getScalars().getRange();
        const ctfunc = vtkColorTransferFunction.newInstance();
        const preset = vtkColorMaps.getPresetByName(newColormap);
        ctfunc.applyColorMap(preset);
        ctfunc.setMappingRange(dataRange[0], dataRange[1]);
        ctfunc.updateRange();
        
        // Update to the new color transfer function
        var actor = context.value.original.actor;
        var renderWindow = context.value.original.renderWindow;
        actor.getProperty().setRGBTransferFunction(0, ctfunc);
        renderWindow.render();
        actor = context.value?.compressed?.actor;
        if (actor) {
          renderWindow = context.value.compressed.renderWindow;
          actor.getProperty().setRGBTransferFunction(0, ctfunc);
          renderWindow.render();
        }
      }
    });

    onBeforeUnmount(() => {
      if (context.value) {
        Object.keys(context.value).forEach(key => {
          const { fullScreenRenderer, actor } = context.value[key];
          if (actor) actor.delete();
          fullScreenRenderer.delete();
        });
        context.value = null;
      }
    });

    return {
      colormap,
      vtkContainerOriginal,
      vtkContainerCompressed,
      createImageData,
      create2DImageActor,
      renderOriginal,
      renderCompressed,
      sameCamera,
      syncCamera,
    };
  },

  computed: {
    allPresets() {
      return vtkColorMaps.rgbPresetNames;
    }
  },

};
</script>
