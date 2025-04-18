<template>
    <div id="threed-vis">
      <div ref="vtkContainer" class="vtk-viewport"></div>
      <div class="threed-controls">
        <div class="button-group">
        <t-button @click="resetCamera">Reset View</t-button>
        <t-button @click="showRawData">Raw3DVis</t-button>
        <t-button @click="showCompressedData">C3DVis</t-button>
        <t-button @click="updateColormap">Update Colormap</t-button>
      </div>
      <div class="slider-group">
        <t-slider 
          v-model="opacity" 
          :min="0" 
          :max="1" 
          :step="0.1" 
          :label="sliderLabel"
          @change="updateOpacity"
        />
      </div>
      </div>
    </div>
  </template>
  
  <script>
    import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue';
    import { useStore } from 'vuex';
    import 'vtk.js/Sources/Rendering/Profiles/Volume';
    import vtkFullScreenRenderWindow from 'vtk.js/Sources/Rendering/Misc/FullScreenRenderWindow';
    import vtkVolume from 'vtk.js/Sources/Rendering/Core/Volume';
    import vtkVolumeMapper from 'vtk.js/Sources/Rendering/Core/VolumeMapper';
    import vtkDataArray from 'vtk.js/Sources/Common/Core/DataArray';
    import vtkImageData from 'vtk.js/Sources/Common/DataModel/ImageData';
    import vtkPiecewiseFunction from 'vtk.js/Sources/Common/DataModel/PiecewiseFunction';
    import vtkColorTransferFunction from 'vtk.js/Sources/Rendering/Core/ColorTransferFunction';
    import emitter from './eventBus';
  
  export default {
    name: 'ThreeDVis',
    setup() {
      const store = useStore();
      const fileData = computed(() => store.state.fileData);
      const compressedData = computed(() => store.state.compressedData);
      const selectedColormap = computed(() => store.state.selectedColormap || "Rainbow");

      const vtkContainer = ref(null);
      const opacity = ref(0.5);
      let fullScreenRenderer = null;
      let renderWindow = null;
      let renderer = null;
      let volumeMapper = null;
      let volume = null;
      let colorTransferFunction = null;
      let opacityTransferFunction = null;
      const rawPayload = ref(null);
  
      const initializeVTK = () => {
        if (fullScreenRenderer) {
          fullScreenRenderer.delete();
        }
        fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
          rootContainer: vtkContainer.value,
          background: [0.9, 0.9, 0.9],
        });
        renderWindow = fullScreenRenderer.getRenderWindow();
        renderer = fullScreenRenderer.getRenderer();
  
        volumeMapper = vtkVolumeMapper.newInstance();
        volume = vtkVolume.newInstance();
        volume.setMapper(volumeMapper);
  
        colorTransferFunction = vtkColorTransferFunction.newInstance();
        opacityTransferFunction = vtkPiecewiseFunction.newInstance();
        volume.getProperty().setRGBTransferFunction(0, colorTransferFunction);
        volume.getProperty().setScalarOpacity(0, opacityTransferFunction);
  
        renderer.addVolume(volume);
        renderWindow.render();
      };

      const applyColorMap = (dataRange, colormap) => {

        const epsilon = 1e-6;
        const effectiveRange =
          Math.abs(dataRange[1] - dataRange[0]) < epsilon
            ? [dataRange[0], dataRange[0] + 1]
            : dataRange;
        console.log(`Applying colormap ${colormap} with effective range:`, effectiveRange);

        colorTransferFunction.removeAllPoints();
        if(colormap === "Viridis") {
          // Viridis
          colorTransferFunction.addRGBPoint(dataRange[0], 0.267, 0.004, 0.329);
          colorTransferFunction.addRGBPoint((dataRange[0] + dataRange[1]) / 2, 0.229, 0.322, 0.545);
          colorTransferFunction.addRGBPoint(dataRange[1], 0.993, 0.906, 0.144);
        } else if(colormap === "Rainbow") {
          // Rainbow
          colorTransferFunction.addRGBPoint(dataRange[0], 0.0, 0.0, 1.0);
          colorTransferFunction.addRGBPoint((dataRange[0] + dataRange[1]) / 2, 0.0, 1.0, 0.0);
          colorTransferFunction.addRGBPoint(dataRange[1], 1.0, 0.0, 0.0);
        } else if(colormap === "Plasma") {
          // Plasma
          colorTransferFunction.addRGBPoint(dataRange[0], 0.050, 0.029, 0.527);
          colorTransferFunction.addRGBPoint((dataRange[0] + dataRange[1]) / 2, 0.859, 0.370, 0.007);
          colorTransferFunction.addRGBPoint(dataRange[1], 0.976, 0.983, 0.080);
        } else if(colormap === "Inferno") {
          // Inferno
          colorTransferFunction.addRGBPoint(dataRange[0], 0.001, 0.000, 0.013);
          colorTransferFunction.addRGBPoint((dataRange[0] + dataRange[1]) / 2, 0.803, 0.428, 0.083);
          colorTransferFunction.addRGBPoint(dataRange[1], 0.988, 0.998, 0.644);
        } else {
          // Default to Rainbow
          colorTransferFunction.addRGBPoint(dataRange[0], 0.0, 0.0, 1.0);
          colorTransferFunction.addRGBPoint((dataRange[0] + dataRange[1]) / 2, 0.0, 1.0, 0.0);
          colorTransferFunction.addRGBPoint(dataRange[1], 1.0, 0.0, 0.0);
        }
      };
  
      const parseVolumeData = (buffer, options = { hasHeader: true, dimensions: [128,128,128], precision: 'f' }) => {
        const { hasHeader, dimensions, precision } = options;
        let width, height, depth;
        let offset = 0;
        let minVal, maxVal;
        if (hasHeader) {
          const view = new DataView(buffer);
          width = view.getUint32(offset, true); offset += 4;
          height = view.getUint32(offset, true); offset += 4;
          depth = view.getUint32(offset, true); offset += 4;
          if (precision === 'f') {
            minVal = view.getFloat32(offset, true); offset += 4;
            maxVal = view.getFloat32(offset, true); offset += 4;
          } else if (precision === 'd') {
            minVal = view.getFloat64(offset, true); offset += 8;
            maxVal = view.getFloat64(offset, true); offset += 8;
          }
        } else {
          [width, height, depth] = dimensions;
        }
        const numVoxels = width * height * depth;
        console.log("Parsed dimensions:", width, height, depth, "Num voxels:", numVoxels);
        console.log("Buffer byteLength:", buffer.byteLength, "Current offset:", offset);
        let data;
        if (precision === 'f') {
          data = new Float32Array(buffer, offset, numVoxels);
        } else if (precision === 'd') {
          data = new Float64Array(buffer, offset, numVoxels);
        }
        if (!hasHeader) {
          if (data.length === 0) {
            console.error("No voxel data found in buffer.");
            return { dimensions: [width, height, depth], range: [0, 0], data: undefined };
          }
          minVal = data[0];
          maxVal = data[0];
          for (let i = 1; i < data.length; i++) {
            if (data[i] < minVal) minVal = data[i];
            if (data[i] > maxVal) maxVal = data[i];
          }
        }
        return { dimensions: [width, height, depth], range: [minVal, maxVal], data };
      };
  
      const handle3DData = (payload) => {
        console.log("Received 3D payload:", payload);
        if (!payload || !payload.dimensions || !payload.data || !payload.range) {
          console.error('Invalid 3D data payload:', payload);
          return;
        }
        const dims = payload.dimensions;
        const dataRange = payload.range;
        console.log("Data range before applying colormap:", dataRange);
        // Ensure payload.data is a typed array
        const dataArray = (payload.data instanceof Float32Array || payload.data instanceof Float64Array)
                          ? payload.data 
                          : new Float32Array(payload.data);
        const imageData = vtkImageData.newInstance();
        imageData.setDimensions(dims);
        const scalars = vtkDataArray.newInstance({
          name: 'values',
          numberOfComponents: 1,
          values: dataArray,
        });
        imageData.getPointData().setScalars(scalars);

        applyColorMap(dataRange, selectedColormap.value);
  
        opacityTransferFunction.removeAllPoints();
        opacityTransferFunction.addPoint(dataRange[0], 0.0);
        opacityTransferFunction.addPoint((dataRange[0] + dataRange[1]) / 2, opacity.value * 0.5);
        opacityTransferFunction.addPoint(dataRange[1], opacity.value);
  
        volumeMapper.setInputData(imageData);
        volumeMapper.update();
  
        resetCamera();
      };
  
      const resetCamera = () => {
        if (renderer && renderWindow) {
          renderer.resetCamera();
          renderWindow.render();
        }
      };
  
      const updateOpacity = () => {
        if (opacityTransferFunction && volumeMapper) {
          const range = volumeMapper.getInputData().getPointData().getScalars().getRange();
          opacityTransferFunction.removeAllPoints();
          opacityTransferFunction.addPoint(range[0], 0.0);
          opacityTransferFunction.addPoint(range[1], opacity.value);
          renderWindow.render();
        }
      };


      const updateColormap = () => {
        if (volumeMapper && volumeMapper.getInputData()) {
          const dataRange = volumeMapper.getInputData().getPointData().getScalars().getRange();
          // Read the current value from the select element directly.
          const colormapSelect = document.getElementById("colormapSelect");
          const currentColormap = colormapSelect ? colormapSelect.value : selectedColormap.value;
          console.log("Updating colormap with data range:", dataRange, "and colormap:", currentColormap);
          applyColorMap(dataRange, currentColormap);
          renderWindow.render();
        } else {
          console.warn("No volume data available to update colormap.");
        }
      };
    
      // Watch for changes to the shared file data from Vuex.
      watch(fileData, (newVal) => {
        if (newVal) {
          const reader = new FileReader();
          reader.onload = () => {
            const buffer = reader.result;
            // Get user-provided dimensions and precision from the store
            const dims = store.state.dimensions || [128, 128, 128];
            const prec = store.state.precision || 'f';
            const bytesPerVoxel = (prec === 'f') ? 4 : 8;
            const expectedRawSize = dims[0] * dims[1] * dims[2] * bytesPerVoxel;
            // Determine if the file contains a header: if the buffer is larger than expected for raw data.
            const hasHeader = buffer.byteLength > expectedRawSize;
            console.log("Buffer size:", buffer.byteLength, "Expected raw size:", expectedRawSize, "Has header:", hasHeader);
            const payload = parseVolumeData(buffer, { 
              hasHeader, 
              dimensions: dims, 
              precision: prec 
            });
            console.log("Parsed payload:", payload);
            console.log("Store dimensions:", store.state.dimensions, "Precision:", store.state.precision);
            if (payload.data) {
              rawPayload.value = payload;
              handle3DData(payload);
            } else {
              console.error("Parsed data is undefined.");
            }
          };
          reader.readAsArrayBuffer(newVal);
        }
      }, { immediate: true });

      // Method to load and display compressed data
      const showCompressedData = () => {
            if (compressedData.value) {
              handle3DData(compressedData.value);
        } else {
          console.error("No compressed data available.");
        }
      };

      // New method: show the raw data stored in rawPayload.
      const showRawData = () => {
        if (rawPayload.value) {
          handle3DData(rawPayload.value);
        } else {
          console.error("No raw data available.");
        }
      };

      // Watch for changes to the selected colormap so that the color mapping updates.
      watch(selectedColormap, (newColormap) => {
        console.log("Selected colormap changed to:", newColormap);
        if (volumeMapper && volumeMapper.getInputData()) {
          const dataRange = volumeMapper.getInputData().getPointData().getScalars().getRange();
          applyColorMap(dataRange, newColormap);
          renderWindow.render();
        }
      });
  
      onMounted(() => {
        initializeVTK();
        emitter.on('3d-data-loaded', handle3DData);
      });
  
      onBeforeUnmount(() => {
        if (fullScreenRenderer) {
          fullScreenRenderer.delete();
        }
        emitter.off('3d-data-loaded', handle3DData);
      });
  
      return {
        vtkContainer,
        opacity,
        resetCamera,
        updateOpacity,
        showCompressedData,
        showRawData,
        updateColormap,
      };
    },
  };
  </script>
  
  <style scoped src="@/assets/ThreeDVis.css"></style>
  