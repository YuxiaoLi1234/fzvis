
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
      <!-- Toggle Button -->
      <button @click="toggleLayout" :class="['btn', horizontalLayout ? 'btn-primary' : 'btn-outline-primary']">
        <i class="bi bi-layout-split"></i>
      </button>

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
      <button :class="['btn', sameCamera ? 'btn-primary' : 'btn-outline-primary']" @click="syncCamera" :disabled="!showDecompression">Sync camera<i class="bi bi-camera ms-1"></i></button>
      <button id="undoBtn" class="btn btn-outline-info">Undo<i class="bi bi-arrow-counterclockwise ms-1"></i></button>
      <button id="resetBtn" class="btn btn-outline-info">Reset<i class="bi bi-arrow-clockwise ms-1"></i></button>
    </div>


    <!-- VTK visualization panel -->
    <div class="position-relative mt-3" :class="horizontalLayout ? 'd-flex gap-3' : ''">
      <!-- Original Container -->
      <div class="card" :style="horizontalLayout ? 'height: 360px; flex: 1;' : 'height: 360px; margin-bottom: 1rem;'">
        <div class="card-header">
          Original
          <i type="button" class="bi bi-question-circle ms-1" title="Instructions" data-bs-toggle="popover" data-bs-placement="right" data-bs-html="true" data-bs-content="<ul><li>Use <b>scroll</b> to zoom.</li><li>Use <b>left click + drag</b> to move.</li><li>Use <b>ctrl + left click</b> to rotate. </li></ul>"></i>
        </div>
        <div class="card-body p-2">
          <div style="width: 100%; height: 100%; position: relative;">
            <div ref="vtkContainerOriginal"></div>
          </div>
        </div>
      </div>

      <!-- Decompressed Container -->
      <div class="card" v-show="showDecompression" :style="horizontalLayout ? 'height: 360px; flex: 1;' : 'height: 360px; margin-top: 1rem;'">
        <div class="card-header">Decompressed</div>
        <div class="card-body p-2">
          <div style="width: 100%; height: 100%; position: relative;">
            <div ref="vtkContainerCompressed"></div>
          </div>
        </div>
      </div>

      <!-- <div id="options-bottom" class="position-absolute start-50 translate-middle-x w-50 bottom-0 d-flex justify-content-center flex-wrap mb-3 z-3">
      </div> -->
    </div>
  </div>

</template>

<script>
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue';
import { useStore } from 'vuex';
import '@kitware/vtk.js/Rendering/Profiles/Volume';
import '@kitware/vtk.js/Rendering/Profiles/Geometry';
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
import vtkInteractorStyleManipulator from '@kitware/vtk.js/Interaction/Style/InteractorStyleManipulator';
import vtkMouseCameraTrackballZoomManipulator from '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballZoomManipulator';
import vtkGestureCameraManipulator from '@kitware/vtk.js/Interaction/Manipulators/GestureCameraManipulator';
import vtkMouseCameraTrackballPanManipulator from '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballPanManipulator';
import vtkMouseCameraTrackballRollManipulator from '@kitware/vtk.js/Interaction/Manipulators/MouseCameraTrackballRollManipulator';
import vtkInteractorStyleTrackballCamera from '@kitware/vtk.js/Interaction/Style/InteractorStyleTrackballCamera';
import vtkScalarBarActor from '@kitware/vtk.js/Rendering/Core/ScalarBarActor';

export default {
  name: 'HelloVtk',

  setup() {
    const store = useStore();
    const fileData = computed(() => store.state.fileData);
    const dimensions = computed(() => store.state.dimensions);
    const precision = computed(() => store.state.precision);
    const compressedData = computed(() => store.state.compressedData);
    const showDecompression = computed(() => store.state.showDecompression);

    const horizontalLayout = ref(false);
    const vtkContainerOriginal = ref(null);
    const vtkContainerCompressed = ref(null);
    const context = ref({
      original: null,
      compressed: null,
    });
    const colormap = ref("rainbow");
    
    let sameCamera = ref(false);
    let oldCamera = null;
    let cachedOriginalData = null;
    let cachedCompressedData = null;

    function toggleLayout() {
      horizontalLayout.value = !horizontalLayout.value;
    }

    function customize2DInteractorStyle() {
      const interactorStyle = vtkInteractorStyleManipulator.newInstance();
      interactorStyle.removeAllMouseManipulators();

      // Set scroll to zoom
      const zoomManipulator = vtkMouseCameraTrackballZoomManipulator.newInstance();
      zoomManipulator.setScrollEnabled(true);
      zoomManipulator.setDragEnabled(false);
      interactorStyle.addMouseManipulator(zoomManipulator);

      // Set drag to move around
      const panManipulator = vtkMouseCameraTrackballPanManipulator.newInstance();
      panManipulator.setButton(1);
      panManipulator.setDragEnabled(true);
      interactorStyle.addMouseManipulator(panManipulator);

      // Set ctrl+left to roll
      const rollManipulator = vtkMouseCameraTrackballRollManipulator.newInstance();
      rollManipulator.setButton(1);
      rollManipulator.setControl(true);
      interactorStyle.addMouseManipulator(rollManipulator);
      
      interactorStyle.addGestureManipulator(vtkGestureCameraManipulator.newInstance());
      return interactorStyle;
    }

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

    // Create 2D visualizaiton for image data
    function create2DImageActor(imageData) {
      const dataRange = imageData.getPointData().getScalars().getRange();
      
      const mapper = vtkImageMapper.newInstance();
      mapper.setInputData(imageData);
      mapper.setSliceAtFocalPoint(true);
      mapper.setSlicingMode(SlicingMode.Z);

      const imageActor = vtkImageSlice.newInstance();
      imageActor.setMapper(mapper);
      const window = dataRange[1] - dataRange[0];
      const level = (dataRange[0] + dataRange[1]) / 2;
      imageActor.getProperty().setColorWindow(window);
      imageActor.getProperty().setColorLevel(level);

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
      if (!context.value.original) {
        // Initialize the renderer for original dataset
        const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
          rootContainer: vtkContainerOriginal.value,
        });

        const renderer = fullScreenRenderer.getRenderer();
        renderer.setBackground(0.1, 0.2, 0.3);
        const renderWindow = fullScreenRenderer.getRenderWindow();
        const lookupTable = vtkColorTransferFunction.newInstance();

        const resizeObserver = new ResizeObserver(() => {
          fullScreenRenderer.resize();
          renderWindow.render();
        });
        resizeObserver.observe(vtkContainerOriginal.value);

        context.value.original = {
          fullScreenRenderer,
          renderer,
          renderWindow,
          resizeObserver,
          lookupTable,
        };
      }
    }

    function initializeVTKCompressed() {
      // Only initialize the context once 
      if (!context.value.compressed) {
        // Initialize the renderer for (de)compressed dataset
        const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
          rootContainer: vtkContainerCompressed.value,
        });
        
        const renderer = fullScreenRenderer.getRenderer();
        renderer.setBackground(0.1, 0.2, 0.3);
        const renderWindow = fullScreenRenderer.getRenderWindow();
        const lookupTable = vtkColorTransferFunction.newInstance();

        const resizeObserver = new ResizeObserver(() => {
          fullScreenRenderer.resize();
          renderWindow.render();
        });
        resizeObserver.observe(vtkContainerCompressed.value);

        context.value.compressed = {
          fullScreenRenderer,
          renderer,
          renderWindow,
          resizeObserver,
          lookupTable,
        };
      }
    }

    function renderView(content, dimensions, precision, contextInfo, forceUpdate = false) {
      if (!contextInfo) {
        console.error('VTK context is not initialized!');
        return;
      }

      if (!contextInfo?.cachedData || forceUpdate) {
        contextInfo.cachedData = createImageData(content, dimensions, precision);
      }

      const { renderer, renderWindow, lookupTable } = contextInfo;
      renderer.removeAllViewProps();

      // Set color mapping function
      const dataRange = contextInfo.cachedData.getPointData().getScalars().getRange();
      const preset = vtkColorMaps.getPresetByName(colormap.value);
      lookupTable.applyColorMap(preset);
      lookupTable.setMappingRange(...dataRange);
      lookupTable.updateRange();

      let actor;
      const sliceInput = document.getElementById("sliceID");
      // Enable the 2D visualization if one of the dimension is 1
      if (dimensions[0] == 1 || dimensions[1] == 1 || dimensions[2] == 1) {
        if (sliceInput) {
          sliceInput.disabled = true;
        }
        actor = create2DImageActor(contextInfo.cachedData);
        actor.getProperty().setRGBTransferFunction(0, lookupTable);
        actor.getProperty().setInterpolationTypeToLinear(true);
        renderer.addActor(actor);
        contextInfo.actor = actor;
        
        // Set camera properties for 2D visualization
        const camera = renderer.getActiveCamera();
        camera.setParallelProjection(true);
        camera.setPosition(0, 0, 1);
        camera.setFocalPoint(0, 0, 0);
        camera.setViewUp(0, 1, 0);

        // Set 2D image visualization interactor style
        const interactorStyle = customize2DInteractorStyle();
        renderWindow.getInteractor().setInteractorStyle(interactorStyle);
      }
      // Otherwise, render 3D volume
      else {
        if (sliceInput) {
          sliceInput.disabled = false;
        }
        const interactorStyle = vtkInteractorStyleTrackballCamera.newInstance();
        renderWindow.getInteractor().setInteractorStyle(interactorStyle);
        actor = createVolumeActor(contextInfo.cachedData);
        renderer.addVolume(actor);
        contextInfo.actor = actor;
      }

      const scalarBarActor = vtkScalarBarActor.newInstance();
      scalarBarActor.setAxisLabel("Intensity");
      scalarBarActor.setBoxSize(0.4, 0.8);
      scalarBarActor.setVisibility(true);
      renderer.addActor(scalarBarActor);
      scalarBarActor.setScalarsToColors(
        actor.getProperty().getRGBTransferFunction()
      );
      
      renderer.resetCamera();
      renderWindow.render();
    }

    function renderOriginal(content, dimensions, precision, forceUpdate = false) {
      if (!context.value.original) {
        console.error('VTK context for original dataset not initialized!');
        return;
      }

      if (!cachedOriginalData || forceUpdate) {
        cachedOriginalData = createImageData(content, dimensions, precision);
      }

      const { renderer, renderWindow, lookupTable } = context.value.original;
      renderer.removeAllViewProps();

      // Set color mapping function
      const dataRange = cachedOriginalData.getPointData().getScalars().getRange();
      const preset = vtkColorMaps.getPresetByName(colormap.value);
      lookupTable.applyColorMap(preset);
      lookupTable.setMappingRange(...dataRange);
      lookupTable.updateRange();

      let actor;
      const sliceInput = document.getElementById("sliceID");
      // Enable the 2D visualization if one of the dimension is 1
      if (dimensions[0] == 1 || dimensions[1] == 1 || dimensions[2] == 1) {
        if (sliceInput) {
          sliceInput.disabled = true;
        }
        actor = create2DImageActor(cachedOriginalData);
        actor.getProperty().setRGBTransferFunction(0, lookupTable);
        actor.getProperty().setInterpolationTypeToLinear(true);
        renderer.addActor(actor);
        context.value.original.actor = actor;
        
        // Set camera properties for 2D visualization
        const camera = renderer.getActiveCamera();
        camera.setParallelProjection(true);
        camera.setPosition(0, 0, 1);
        camera.setFocalPoint(0, 0, 0);
        camera.setViewUp(0, 1, 0);

        // Set 2D image visualization interactor style
        const interactorStyle = customize2DInteractorStyle();
        renderWindow.getInteractor().setInteractorStyle(interactorStyle);
      }
      // Otherwise, render 3D volume
      else {
        if (sliceInput) {
          sliceInput.disabled = false;
        }
        const interactorStyle = vtkInteractorStyleTrackballCamera.newInstance();
        renderWindow.getInteractor().setInteractorStyle(interactorStyle);
        actor = createVolumeActor(cachedOriginalData);
        renderer.addVolume(actor);
        context.value.original.actor = actor;
      }

      const scalarBarActor = vtkScalarBarActor.newInstance();
      scalarBarActor.setAxisLabel("Intensity");
      scalarBarActor.setBoxSize(0.4, 0.8);
      scalarBarActor.setVisibility(true);
      renderer.addActor(scalarBarActor);
      scalarBarActor.setScalarsToColors(
        actor.getProperty().getRGBTransferFunction()
      );
      
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
         // Set camera properties for 2D visualization
        const camera = renderer.getActiveCamera();
        camera.setParallelProjection(true);
        camera.setParallelProjection(true);
        camera.setPosition(0, 0, 1);
        camera.setFocalPoint(0, 0, 0);
        camera.setViewUp(0, 1, 0);

        // Set 2D image visualization interactor style
        const interactorStyle = customize2DInteractorStyle();
        renderWindow.getInteractor().setInteractorStyle(interactorStyle);
        
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
          renderView(fileData.value, dimensions.value, precision.value, context.value.original);
        }
      }, 200);
    });

    // Rerender the volume when the file info changes
    watch([fileData, dimensions, precision], ([newFileData, newDimensions, newPrecision]) => {
      if (newFileData && newDimensions && newPrecision) {
        setTimeout(() => {
          renderView(newFileData, newDimensions, newPrecision, context.value.original, true);
        }, 300);
      }
    });

    watch(showDecompression, newVal => {
      if (newVal) {
        nextTick(() => {
          initializeVTKCompressed();
        });
      }
    });

    watch([compressedData, dimensions, precision], ([newFileData, newDimensions, newPrecision]) => {
      if (newFileData && newDimensions && newPrecision) {
        setTimeout(() => {
          renderView(newFileData, newDimensions, newPrecision, context.value.compressed, true);
        }, 300);
      }
      else {
        if (context.value.compressed?.cachedData) {
          context.value.compressed.cachedData = null;
        }
      }
    });

    // // Rerender the volume when the colormap changes
    watch(colormap, (newColormap) => {
      console.log("Colormap is changed to:", newColormap)
      if (newColormap && cachedOriginalData) {
        const { renderWindow, lookupTable } = context.value.original;
        // const dataRange = cachedOriginalData.getPointData().getScalars().getRange();
        const preset = vtkColorMaps.getPresetByName(newColormap);
        lookupTable.applyColorMap(preset);
        // ctfunc.setMappingRange(dataRange[0], dataRange[1]);
        // ctfunc.updateRange();
        
        // Update to the new color transfer function
        renderWindow.render();
      }
    });

    onBeforeUnmount(() => {
      Object.keys(context.value).forEach(key => {
        if (context.value[key]) {
          const { fullScreenRenderer, actor } = context.value[key];
          if (actor) actor.delete();
          fullScreenRenderer.delete();
          if (context.value[key]?.resizeObserver) {
            context.value[key].resizeObserver.disconnect(); 
          }
          context.value[key] = null;
        }
      });
    });

    return {
      colormap,
      createImageData,
      create2DImageActor,
      horizontalLayout,
      renderOriginal,
      renderCompressed,
      sameCamera,
      showDecompression,
      syncCamera,
      toggleLayout,
      vtkContainerCompressed,
      vtkContainerOriginal,
    };
  },

  computed: {
    allPresets() {
      return vtkColorMaps.rgbPresetNames;
    }
  },

};
</script>
