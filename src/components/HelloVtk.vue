<template>
  <div class="vtk-wrapper">

    <div
      id="options-top"
      class="d-flex flex-wrap align-items-center justify-content-center mt-3 gap-3 py-2 bg-light rounded shadow-sm"
    >
      <!-- Displays per row -->
      <div class="d-flex align-items-center me-3">
        <label class="me-2 mb-0 fw-semibold text-secondary">
          <i class="bi bi-grid-3x3-gap me-1"></i>Displays per row:
        </label>
        <select
          v-model="containersPerRow"
          class="form-select form-select-sm"
          style="width: 70px; min-width: 70px;"
        >
          <option v-for="n in 4" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>

      <!-- Colormap -->
      <div class="d-flex align-items-center me-3">
        <label class="me-2 mb-0 fw-semibold text-secondary">
          <i class="bi bi-palette me-1"></i>Colormap:
        </label>
        <select
          class="form-select form-select-sm"
          aria-label="colormap"
          v-model="colormap"
          style="min-width: 120px; max-width: 180px;"
        >
          <option v-for="preset in allPresets" :value="preset" :key="preset">
          {{ preset }}
          </option>
        </select>
      </div>

      <!-- Decompressed Data Selector -->
      <div v-if="hasDecompressedData" class="d-flex align-items-center me-3">
        <label class="me-2 mb-0 fw-semibold text-secondary">
          <i class="bi bi-box me-1"></i>Decompressed:
        </label>
        <template v-if="decompressedKeys.length <= 10">
          <input
          type="range"
          class="form-range"
          min="0"
          :max="decompressedKeys.length - 1"
          v-model="selectedDecompressedIndex"
          style="width: 120px;"
          />
          <span class="ms-2">{{ decompressedKeys[selectedDecompressedIndex] }}</span>
        </template>
        <template v-else>
          <button
          class="btn btn-sm btn-outline-secondary me-1"
          :disabled="selectedDecompressedIndex === 0"
          @click="selectedDecompressedIndex--"
          >
          &lt;
          </button>
          <span>{{ decompressedKeys[selectedDecompressedIndex] }}</span>
          <button
          class="btn btn-sm btn-outline-secondary ms-1"
          :disabled="selectedDecompressedIndex === decompressedKeys.length - 1"
          @click="selectedDecompressedIndex++"
          >
          &gt;
          </button>
        </template>
      </div>

      <!-- Camera Sync -->
      <button
        :class="['btn btn-sm d-flex align-items-center', sameCamera ? 'btn-primary' : 'btn-outline-primary']"
        @click="handleSyncCameraChange"
        title="Synchronize camera views"
      >
        <i class="bi bi-camera me-1"></i>Sync Camera
      </button>

      <!-- Undo -->
      <!-- <button
        id="undoBtn"
        class="btn btn-sm btn-outline-info d-flex align-items-center"
        title="Undo last action"
      >
        <i class="bi bi-arrow-counterclockwise me-1"></i>Undo
      </button> -->

      <!-- Reset -->
      <!-- <button
        id="resetBtn"
        class="btn btn-sm btn-outline-info d-flex align-items-center"
        title="Reset all settings"
      >
        <i class="bi bi-arrow-clockwise me-1"></i>Reset
      </button> -->
      
    </div>

    <!-- Modified container grid with dynamic columns -->
    <div
      class="position-relative mt-3"
      :style="{
        display: 'grid',
        gridTemplateColumns: `repeat(${containersPerRow}, 1fr)`,
        gap: '1rem'
      }"
    >
      <!-- Original Container -->
      <div class="card" style="height: 375px;">
        <div class="card-header">
          <div class="d-flex align-items-center justify-content-between">
            <span>
              Original
              <i
                type="button"
                class="bi bi-question-circle ms-1"
                title="Instructions"
                data-bs-toggle="popover"
                data-bs-placement="right"
                data-bs-html="true"
                data-bs-content="<ul><li>Use <b>scroll</b> to zoom.</li><li>Use <b>left click + drag</b> to move.</li><li>Use <b>ctrl + left click</b> to rotate. </li></ul>"
              ></i>
            </span>
            <div v-if="isTimeVarying && dimensions" class="d-flex align-items-center">
              <div class="d-flex align-items-center">
                <select
                  class="form-select w-auto"
                  aria-label="rescale"
                  v-model="rescaleMethod"
                >
                  <option value="global">Global range</option>
                  <option value="local">Local range</option>
                  <option value="custom">Custom range</option>
                </select>
                <div v-if="rescaleMethod === 'custom'" class="d-flex align-items-center">
                <input
                  type="number"
                  class="form-control form-control-sm w-auto mx-2"
                  v-model="customMin"
                  placeholder="Min"
                  style="max-width: 100px;"
                />
                <input
                  type="number"
                  class="form-control form-control-sm w-auto"
                  v-model="customMax"
                  placeholder="Max"
                  style="max-width: 100px;"
                />
              </div>
            </div>
            <label for="sliceId" class="form-label mx-2 pt-2">Slice:</label>
            <input
              type="range"
              min="0"
              :max="dimensions[2]-1"
              step="1"
              class="form-range align-self-center w-auto"
              v-model="sliceId"
              style="max-width: 160px;"
            />
          </div>
        </div>
      </div>
      <div class="card-body p-2">
        <div style="width: 100%; height: 100%; position: relative;">
        <div ref="vtkContainerOriginal"></div>
        </div>
      </div>
      </div>

      <!-- Decompressed Container -->
      <div
        v-show="selectedDecompressedData"
        class="card"
        style="height: 375px;"
      >
        <div class="card-header">
          <span
          class="ms-1 text-decoration-underline text-dark"
          style="cursor: pointer;"
          data-bs-toggle="tooltip"
          data-bs-placement="bottom"
          data-bs-html="true"
          :title="formatConfigHTML(selectedDecompressedData?.compressor_config)"
          >
          Decompressed ({{ selectedCompressor }})
          </span>
        </div>
        <div class="card-body p-2">
          <div style="width: 100%; height: 100%; position: relative;">
            <div ref="vtkContainerDecompressed"></div>
          </div>
        </div>
      </div>

    </div>

  </div>

</template>

<script>
import { Popover, Tooltip } from 'bootstrap';
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue';
import { useStore } from 'vuex';
import '@kitware/vtk.js/Rendering/Profiles/Geometry';
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
    const isTimeVarying = computed(() => store.state.isTimeVarying);
    
    const sliceId = ref(0);
    const rescaleMethod = ref("global");
    const customMin = ref(0);
    const customMax = ref(1);
    
    const vtkContainerOriginal = ref(null);
    const vtkContainerDecompressed = ref(null);
    const context = ref({
      original: null,
      decompressed: null,
    });
    const colormap = ref("rainbow");
    
    let sameCamera = ref(false);
    let oldCamera = null;
    
    const comparisonData = computed(() => store.state.comparisonData);
    const selectedDecompressedIndex = ref(0);
    const decompressedKeys = computed(() => comparisonData.value ? Object.keys(comparisonData.value) : []);
    const hasDecompressedData = computed(() => decompressedKeys.value.length > 0);
    const selectedCompressor = computed(() => decompressedKeys.value[selectedDecompressedIndex.value] || null);
    const selectedDecompressedData = computed(() => {
      if (hasDecompressedData.value && selectedCompressor.value) {
        return comparisonData.value[selectedCompressor.value];
      }
      return null;
    });

    function cleanupContext(ctx) {
      if (ctx) {
        const { fullScreenRenderer, resizeObserver } = ctx;
        if (resizeObserver) {
          resizeObserver.disconnect();
        }
        if (fullScreenRenderer) {
          fullScreenRenderer.getRenderWindow().delete();
          fullScreenRenderer.delete();
        }
      }
    }

    // Create 2D visualizaiton for image data
    function createImageActor(imageData) {
      const dataRange = imageData.getPointData().getScalars().getRange();
      
      const mapper = vtkImageMapper.newInstance();
      mapper.setInputData(imageData);
      // mapper.setSliceAtFocalPoint(true);
      mapper.setSlicingMode(SlicingMode.Z);
      mapper.setKSlice(0);

      const imageActor = vtkImageSlice.newInstance();
      imageActor.setMapper(mapper);
      const window = dataRange[1] - dataRange[0];
      const level = (dataRange[0] + dataRange[1]) / 2;
      imageActor.getProperty().setColorWindow(window);
      imageActor.getProperty().setColorLevel(level);

      return imageActor;
    }

    function createImageData(content, dimensions, precision) {
      const imageData = vtkImageData.newInstance();
      imageData.setDimensions(...dimensions);
      const inputArray = (precision === 'f' ? new Float32Array(content) : new Float64Array(content));

      const scalars = vtkDataArray.newInstance({
        size: inputArray.length,
        values: inputArray,
        dataType: (precision === 'f' ? `Float32Array` : `Float64Array`),
      });

      // let totalNaNs = 0;
      // for (let i = 0; i < inputArray.length; ++i) {
      //   if (isNaN(inputArray[i])) {
      //     totalNaNs++;
      //   }
      // }
      // console.log("TotalNaNs:", totalNaNs);

      imageData.getPointData().setScalars(scalars);
      return imageData;
    }

    // Create 3D visualizaiton for volume data
    function createVolumeActor(imageData) {
      const mapper = vtkVolumeMapper.newInstance();
      mapper.setInputData(imageData);

      const volumeActor = vtkVolume.newInstance();
      volumeActor.setMapper(mapper);

      // Get the actual data range
      const dataRange = imageData.getPointData().getScalars().getRange();
      
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

    function formatConfigHTML(config) {
      if (!config) return '';
      return Object.entries(config)
        .map(([key, value]) => `<b>${key}:</b> ${typeof value === 'object' && value !== null ? JSON.stringify(value) : value}<br>`)
        .join('');
    }

    function getLocalRange(imageData, sliceIdx=0) {
      const scalars = imageData.getPointData().getScalars();
      
      // Get the current slice data
      const sliceSize = dimensions.value[0] * dimensions.value[1];
      const startIdx = sliceIdx * sliceSize;
      
      // Calculate min and max for current slice
      const dataRange = scalars.getRange(startIdx, startIdx + sliceSize);
      return dataRange;
    }

    function handleSyncCameraChange() {
      if (!context.value?.original || !context.value?.decompressed) {
        console.error("VTK contexts not fully initialized!");
        return;
      }
      const decompressedCtx = context.value.decompressed;

      if (sameCamera.value) {
        if (decompressedCtx && oldCamera) {
          decompressedCtx.renderer.setActiveCamera(oldCamera);
          decompressedCtx.renderWindow.render();
          oldCamera = null;
        }
      } else {
        const sharedCamera = context.value.original.renderer.getActiveCamera();
        oldCamera = decompressedCtx.renderer.getActiveCamera();
        
        const originalContext = context.value.original;
        const colorWindow = originalContext.actor.getProperty().getColorWindow();
        const colorLevel = originalContext.actor.getProperty().getColorLevel();
        const dataRange = [colorLevel - colorWindow / 2, colorLevel + colorWindow / 2];

        decompressedCtx.renderer.setActiveCamera(sharedCamera);
        
        // Sync colormap range
        decompressedCtx.lookupTable.setMappingRange(dataRange[0], dataRange[1]);
        decompressedCtx.lookupTable.updateRange();
        decompressedCtx.actor.getProperty().setColorWindow(colorWindow);
        decompressedCtx.actor.getProperty().setColorLevel(colorLevel);

        decompressedCtx.renderWindow.render();
        sharedCamera.onModified(() => {
          if (sameCamera.value) {
            context.value.original.renderWindow.render();
            if (context.value.decompressed) context.value.decompressed.renderWindow.render();
          }
        });
      }
      sameCamera.value = !sameCamera.value;
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

    function initializeVTKDecompressed() {
      if (!context.value.decompressed) {
        if (vtkContainerDecompressed.value) {
          const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
            rootContainer: vtkContainerDecompressed.value,
          });
          
          const renderer = fullScreenRenderer.getRenderer();
          renderer.setBackground(0.1, 0.2, 0.3);
          const renderWindow = fullScreenRenderer.getRenderWindow();
          const lookupTable = vtkColorTransferFunction.newInstance();

          const resizeObserver = new ResizeObserver(() => {
            fullScreenRenderer.resize();
            renderWindow.render();
          });
          resizeObserver.observe(vtkContainerDecompressed.value);

          context.value.decompressed = {
            fullScreenRenderer,
            renderer,
            renderWindow,
            resizeObserver,
            lookupTable,
          };
        }
      }
    }

    function renderSlice(contextInfo, sliceIdx=sliceId.value) {
      const contexts = Array.isArray(contextInfo) ? contextInfo : [contextInfo];
      contexts.forEach(ctx => {
        if (!ctx?.cachedData) return;
        const { cachedData, lookupTable, actor, renderWindow } = ctx;
        let dataRange = cachedData.getPointData().getScalars().getRange();
        if (rescaleMethod.value === "global") {
          dataRange = cachedData.getPointData().getScalars().getRange();
        } else if (rescaleMethod.value === "local") {
          dataRange = getLocalRange(cachedData, sliceIdx);
        } else if (rescaleMethod.value === "custom") {
          dataRange = [customMin.value, customMax.value];
        }
        lookupTable.setMappingRange(dataRange[0], dataRange[1]);
        lookupTable.updateRange();
        actor.getMapper().setKSlice(sliceIdx);
        actor.getProperty().setColorWindow(dataRange[1] - dataRange[0]);
        actor.getProperty().setColorLevel((dataRange[1] + dataRange[0]) / 2);
        renderWindow.render();
      });
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
      let dataRange = contextInfo.cachedData.getPointData().getScalars().getRange();
      const preset = vtkColorMaps.getPresetByName(colormap.value);
      lookupTable.applyColorMap(preset);
      lookupTable.setNanColor([1, 1, 1, 1]);

      let actor;
      // Enable the 2D visualization if one of the dimension is 1 or the data is time-varying
      // Only check the last dimension (`depth`) as we assume the dimension of the data is like [x, y, t]
      if (dimensions[2] == 1 || isTimeVarying.value) {
        
        actor = createImageActor(contextInfo.cachedData);
        
        if (sameCamera.value) {
          const originalContext = context.value.original;
          const colorWindow = originalContext.actor.getProperty().getColorWindow();
          const colorLevel = originalContext.actor.getProperty().getColorLevel();
          dataRange = [colorLevel - colorWindow / 2, colorLevel + colorWindow / 2];
          // Sync colormap range
          lookupTable.setMappingRange(dataRange[0], dataRange[1]);
          lookupTable.updateRange();
          actor.getProperty().setColorWindow(colorWindow);
          actor.getProperty().setColorLevel(colorLevel);
        }
        else {
          // Set camera properties for 2D visualization
          const camera = renderer.getActiveCamera();
          camera.setParallelProjection(true);
          camera.setPosition(0, 0, 1);
          camera.setFocalPoint(0, 0, 0);
          camera.setViewUp(0, 1, 0);
        }
        
        actor.getProperty().setRGBTransferFunction(lookupTable);
        actor.getProperty().setInterpolationTypeToLinear(true);
        renderer.addActor(actor);
        contextInfo.actor = actor;
        customMin.value = dataRange[0], customMax.value = dataRange[1];

        // Set 2D image visualization interactor style
        const interactorStyle = customize2DInteractorStyle();
        renderWindow.getInteractor().setInteractorStyle(interactorStyle);
      }
      // Otherwise, render 3D volume
      else {
          const interactorStyle = vtkInteractorStyleTrackballCamera.newInstance();
          renderWindow.getInteractor().setInteractorStyle(interactorStyle);
          actor = createVolumeActor(contextInfo.cachedData);
          renderer.addVolume(actor);
          contextInfo.actor = actor;
      }

      const scalarBarActor = vtkScalarBarActor.newInstance();
      scalarBarActor.setAxisLabel("Intensity");
      // scalarBarActor.setBoxSize(0.4, 0.8);
      scalarBarActor.setVisibility(true);
      renderer.addActor(scalarBarActor);
      scalarBarActor.setScalarsToColors(
        actor.getProperty().getRGBTransferFunction()
      );
      
      if (sameCamera.value) {
        const sharedCamera = context.value.original.renderer.getActiveCamera();
        renderer.setActiveCamera(sharedCamera);
      }
      else {
        renderer.resetCamera();
      }
      renderWindow.render();
    }

    onMounted(() => {
      // Delay init slightly to allow tab to become visible
      setTimeout(() => {
        initializeVTK();
        if (fileData.value && dimensions.value && precision.value) {
          renderView(fileData.value, dimensions.value, precision.value, context.value.original);
        }
        if (hasDecompressedData.value) {
          selectedDecompressedIndex.value = 0;
        }
        
        nextTick(() => {
          document.querySelectorAll('[data-bs-toggle="popover"]').forEach(el => {
            new Popover(el);
          });
        });
      }, 200);
    });

    // Rerender when the colormap changes
    watch(colormap, newColormap => {
      // console.log("Colormap is changed to:", newColormap)
      if (newColormap) {
        if (context.value.original?.cachedData) {
          const { renderWindow, lookupTable } = context.value.original;
          const preset = vtkColorMaps.getPresetByName(newColormap);
          lookupTable.applyColorMap(preset);
          renderWindow.render();
        }
        if (context.value.decompressed?.cachedData) {
          const { renderWindow, lookupTable } = context.value.decompressed;
          const preset = vtkColorMaps.getPresetByName(newColormap);
          lookupTable.applyColorMap(preset);
          renderWindow.render();
        }
      }
    });

    // Rerender when the decompressed data changes
    watch(comparisonData, () => {
      cleanupContext(context.value.decompressed);
      context.value.decompressed = null;
      selectedDecompressedIndex.value = 0;
    });

    // Watch for decompressedKeys changes to reset index
    watch(decompressedKeys, (keys) => {
      if (keys.length > 0) selectedDecompressedIndex.value = 0;
    });

    watch([dimensions, precision], ([newDimensions, newPrecision]) => {
      if (newDimensions && newPrecision) {
        // Re-render original data if it exists and container is initialized
        if (fileData.value && context.value.original) {
          setTimeout(() => {
            renderView(fileData.value, newDimensions, newPrecision, context.value.original, false);
          }, 100);
        }
        // Re-render decompressed data if it exists
        if (selectedDecompressedData.value && context.value.decompressed) {
          renderView(
            selectedDecompressedData.value.decp_data,
            newDimensions,
            newPrecision,
            context.value.decompressed,
            true
          );
        }
      }
    });

    // Rerender when the file info changes
    watch(fileData, newFileData => {
      if (newFileData && dimensions.value && precision.value) {
        // Reset variables when file data changes
        rescaleMethod.value = "global";
        sameCamera.value = false;
        setTimeout(() => {
          renderView(newFileData, dimensions.value, precision.value, context.value.original, true);
        }, 300);
      }
    });

    // Watch both rescaleMethod and sliceId changes
    watch([rescaleMethod, sliceId, customMin, customMax], ([newMethod, newSliceId, newMin, newMax]) => {
      // Only proceed if we have valid inputs
      if (newMethod && newSliceId !== undefined && newMin !== undefined && newMax !== undefined) {
        // Update original view
        if (context.value.original?.cachedData) {
          renderSlice(context.value.original, newSliceId);
        }
        // Update decompressed view if it exists
        if (context.value.decompressed?.cachedData) {
          renderSlice(context.value.decompressed, newSliceId);
        }
      }
    });

    watch(selectedCompressor, (newCompressor) => {
      if (newCompressor && selectedDecompressedData.value && dimensions.value && precision.value) {
        nextTick(() => {
          document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
            let tooltip = Tooltip.getInstance(el);
            if (!tooltip) {
              new Tooltip(el);
            } else {
              // Update the title if the tooltip already exists
              const newTitle = formatConfigHTML(selectedDecompressedData.value.compressor_config);
              el.setAttribute('data-bs-original-title', newTitle);
              tooltip?.update();
            }
          });
          initializeVTKDecompressed();
          setTimeout(() => {
            renderView(
              selectedDecompressedData.value.decp_data,
              dimensions.value,
              precision.value,
              context.value.decompressed,
              true,
            );
          }, 200);
        });
      }
    });

    onBeforeUnmount(() => {
      cleanupContext(context.value.original);
      cleanupContext(context.value.decompressed);
      context.value = {
        original: null,
        decompressed: null,
      };
    });

    return {
      cleanupContext,
      createImageData,
      createImageActor,
      colormap,
      comparisonData,
      customMax,
      customMin,
      decompressedKeys,
      dimensions,
      formatConfigHTML,
      handleSyncCameraChange,
      hasDecompressedData,
      isTimeVarying,
      rescaleMethod,
      renderView,
      sameCamera,
      selectedCompressor,
      selectedDecompressedData,
      selectedDecompressedIndex,
      sliceId,
      vtkContainerDecompressed,
      vtkContainerOriginal,
    };
  },

  data() {
    return {
      allPresets: vtkColorMaps.rgbPresetNames,
      containersPerRow: 2,
    }
  },

};
</script>