<script>
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick, markRaw } from 'vue';
import { useStore } from 'vuex';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import vtkColorMaps from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction/ColorMaps';
import html2canvas from 'html2canvas';

export default {
  name: 'HelloThree',

  setup() {
    const store = useStore();
    const isMounted = ref(false);
    const fileData = computed(() => store.state.dataset?.content);
    const dimensions = computed(() => store.state.dataset?.dimensions);
    const precision = computed(() => store.state.dataset?.precision);
    const isTimeVarying = computed(() => store.state.isTimeVarying);
    
    const sliceId = ref(0);
    const rescaleMethod = ref("global");
    const customMin = ref(0);
    const customMax = ref(1);
    
    const containerOriginal = ref(null);
    const containerDecompressed = ref(null);
    const scalarBarCanvasOriginal = ref(null);
    const scalarBarCanvasDecompressed = ref(null);
    const manifoldBarCanvasOriginal = ref(null);
    const manifoldBarCanvasDecompressed = ref(null);

    const context = ref({
      original: null,
      decompressed: null,
    });
    const colormap = ref("jet");
    
    let sameCamera = ref(false);
    const currentRangeOriginal = ref([0, 1]);
    const currentRangeDecompressed = ref([0, 1]);
    const currentLabelRangeOriginal = ref([0, 1]);
    const currentLabelRangeDecompressed = ref([0, 1]);
    
    const comparisonData = computed(() => store.state.comparisonData);
    const criticalPoints = computed(() => store.state.criticalPoints);
    const segmentation = computed(() => store.state.segmentation);
    const criticalPointsDisplay = ref('all');
    const criticalPointsScale = ref(0.3);
    const minimaColor = ref('#666666');
    const maximaColor = ref('#ff0000');
    const saddleColor = ref('#ffcc00');
    const segmentationMode = ref('none');
    const segmentationModeOptions = [
      { value: 'none', label: 'Scalar Field' },
      { value: 'ascending', label: 'Ascending Manifold' },
      { value: 'descending', label: 'Descending Manifold' },
      { value: 'morse_smale', label: 'Morse-Smale Manifold' },
    ];
    
    // Movable Colorbar and Scaling
    const visualScale = ref(1.0);
    const scalarBarTop = ref(88); // Default for horizontal layout
    const scalarBarLeft = ref(50); // Centered for horizontal layout
    const isDragging = ref(false);
    let dragStart = { x: 0, y: 0, top: 0, left: 0, width: 1, height: 1 };
    
    const layoutMode = ref('horizontal'); // 'horizontal' or 'vertical'
    const leadContext = ref('original'); // 'original' or 'decompressed'

    function startDrag(e) {
      isDragging.value = true;
      const host = e.currentTarget?.parentElement;
      const rect = host?.getBoundingClientRect();
      dragStart = { 
        x: e.clientX, 
        y: e.clientY, 
        top: scalarBarTop.value, 
        left: scalarBarLeft.value,
        width: Math.max(1, rect?.width || 1),
        height: Math.max(1, rect?.height || 1),
      };
      window.addEventListener('mousemove', handleDrag);
      window.addEventListener('mouseup', stopDrag);
    }

    function handleDrag(e) {
      if (!isDragging.value) return;
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;

      // Update position in percentage
      scalarBarTop.value = Math.max(0, Math.min(100, dragStart.top + (dy / dragStart.height * 100))); 
      scalarBarLeft.value = Math.max(0, Math.min(100, dragStart.left + (dx / dragStart.width * 100)));
    }

    function stopDrag() {
      isDragging.value = false;
      window.removeEventListener('mousemove', handleDrag);
      window.removeEventListener('mouseup', stopDrag);
    }

    function normalizeSegmentationField(field) {
      if (field === null || field === undefined) return null;
      if (field instanceof ArrayBuffer) return new Float32Array(field);
      if (ArrayBuffer.isView(field)) return new Float32Array(field);
      if (Array.isArray(field)) {
        if (!field.length) return new Float32Array();
        if (field.every(item => typeof item !== 'object' || item === null)) {
          return new Float32Array(field.map(v => Number.isFinite(Number(v)) ? Number(v) : -1));
        }
        return new Float32Array(field.flat(Infinity).map(v => Number.isFinite(Number(v)) ? Number(v) : -1));
      }
      if (typeof field === 'object' && Array.isArray(field.data)) {
        return normalizeSegmentationField(field.data);
      }
      return null;
    }

    const selectedDecompressedIndex = ref(0);
    const decompressedKeys = computed(() => comparisonData.value ? Object.keys(comparisonData.value) : []);
    const hasDecompressedData = computed(() => decompressedKeys.value.length > 0);
    
    // Watch for decompressed data sources list changing (e.g. node removed)
    watch(decompressedKeys, (newKeys) => {
      // If the currently selected index is now invalid, reset to 0 or clamp
      if (selectedDecompressedIndex.value >= newKeys.length) {
        selectedDecompressedIndex.value = Math.max(0, newKeys.length - 1);
      }
    }, { deep: true });
    const selectedCompressor = computed(() => decompressedKeys.value[selectedDecompressedIndex.value] || null);
    const selectedDecompressedData = computed(() => {
      if (hasDecompressedData.value && selectedCompressor.value) {
        return comparisonData.value[selectedCompressor.value];
      }
      return null;
    });
    const hasAnySegmentation = computed(() => {
      const seg = segmentation.value;
      if (!seg) return false;
      const sources = [];
      if (seg.original) sources.push(seg.original);
      if (seg.decompressed) {
        Object.values(seg.decompressed).forEach((v) => {
          if (v) sources.push(v);
        });
      }
      return sources.some((src) => (
        normalizeSegmentationField(src.ascending)?.length ||
        normalizeSegmentationField(src.descending)?.length ||
        normalizeSegmentationField(src.morse_smale)?.length
      ));
    });
    const allPresets = vtkColorMaps.rgbPresetNames;

    // --- Shader Definitions ---
    const volumeVertexShader = `
      out vec3 vOrigin;
      out vec3 vDirection;
      void main() {
        vOrigin = cameraPosition;
        vDirection = position - cameraPosition;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `;

    const volumeFragmentShader = `
      precision highp float;
      precision highp sampler3D;
      
      uniform mat4 inverseModelMatrix;
      uniform sampler3D volume;
      uniform sampler2D transferFunction;
      uniform vec3 dimensions;
      uniform float stepSize;
      uniform float opacityMultiplier;
      uniform vec2 dataRange;
      
      // Random function for jittering
      float rand(vec2 co) {
        return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
      }
      
      in vec3 vOrigin;
      in vec3 vDirection;
      out vec4 outColor;

      vec2 intersectBox(vec3 orig, vec3 dir) {
        vec3 boxMin = vec3(-0.5);
        vec3 boxMax = vec3(0.5);
        vec3 invDir = 1.0 / dir;
        vec3 t0 = (boxMin - orig) * invDir;
        vec3 t1 = (boxMax - orig) * invDir;
        vec3 tmin = min(t0, t1);
        vec3 tmax = max(t0, t1);
        float t_start = max(tmin.x, max(tmin.y, tmin.z));
        float t_end = min(tmax.x, min(tmax.y, tmax.z));
        return vec2(t_start, t_end);
      }

      void main() {
        vec3 rayDir = normalize(vDirection);
        vec4 modelOrig = inverseModelMatrix * vec4(vOrigin, 1.0);
        vec4 modelDir = normalize(inverseModelMatrix * vec4(rayDir, 0.0));
        
        vec2 t = intersectBox(modelOrig.xyz, modelDir.xyz);
        if (t.x > t.y) discard;
        
        float t_enter = max(0.0, t.x);
        float t_exit = t.y;
        
        // Ray jittering to reduce banding
        float jitter = stepSize * rand(gl_FragCoord.xy);
        float t_start = t_enter + jitter;
        
        vec4 color = vec4(0.0);
        float actualStep = stepSize;
        
        for (float dist = t_start; dist < t_exit; dist += actualStep) {
          vec3 p = modelOrig.xyz + modelDir.xyz * dist + 0.5;
          float rawVal = texture(volume, p).r;
          
          float normalizedVal = (rawVal - dataRange.x) / (dataRange.y - dataRange.x + 1e-10);
          normalizedVal = clamp(normalizedVal, 0.0, 1.0);
          
          vec4 sampledColor = texture(transferFunction, vec2(normalizedVal, 0.5));
          
          sampledColor.a *= opacityMultiplier;
          
          // Opacity correction for step size
          float correctedAlpha = 1.0 - pow(1.0 - sampledColor.a, actualStep * 100.0);
          
          // Premultiplied alpha blending
          color.rgb += (1.0 - color.a) * sampledColor.rgb * correctedAlpha;
          color.a += (1.0 - color.a) * correctedAlpha;
          
          if (color.a > 0.95) break;
        }
        
        if (color.a < 0.01) discard;
        outColor = color;
      }
    `;

    function formatValue(val) {
      if (val === undefined || val === null) return "0";
      if (val === 0) return "0";
      const absVal = Math.abs(val);
      if (absVal < 0.00001) {
        return val.toExponential(2);
      }
      // Use up to 5 decimal places, but remove trailing zeros
      return parseFloat(val.toFixed(5)).toString();
    }

    function cleanupContext(ctx) {
      if (ctx) {
        const { renderer, resizeObserver, frameId } = ctx;
        if (frameId) cancelAnimationFrame(frameId);
        if (resizeObserver) resizeObserver.disconnect();
        if (renderer) {
          renderer.dispose();
          renderer.forceContextLoss();
          renderer.domElement.remove();
        }
      }
    }

    function createTransferFunctionTexture(name, { opaque = false } = {}) {
      const preset = vtkColorMaps.getPresetByName(name);
      const canvas = document.createElement('canvas');
      canvas.width = 256;
      canvas.height = 1;
      const ctx = canvas.getContext('2d');
      const gradient = ctx.createLinearGradient(0, 0, 256, 0);

      const rgbPoints = preset.RGBPoints;
      // vtk RGBPoints is [value, R, G, B, value, R, G, B, ...]
      let minT = Infinity;
      let maxT = -Infinity;
      for (let i = 0; i < rgbPoints.length; i += 4) {
        if (rgbPoints[i] < minT) minT = rgbPoints[i];
        if (rgbPoints[i] > maxT) maxT = rgbPoints[i];
      }

      for (let i = 0; i < rgbPoints.length; i += 4) {
        let t = (rgbPoints[i] - minT) / (maxT - minT || 1);
        const r = Math.round(rgbPoints[i + 1] * 255);
        const g = Math.round(rgbPoints[i + 2] * 255);
        const b = Math.round(rgbPoints[i + 3] * 255);
        // Add linear alpha ramp: 0 at min, 1 at max (or force opaque)
        const a = opaque ? 1 : t;
        gradient.addColorStop(t, `rgba(${r},${g},${b},${a})`);
      }

      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, 256, 1);

      const texture = new THREE.CanvasTexture(canvas);
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;
      return texture;
    }

    function updateScalarBar(canvasRef, name) {
      if (!canvasRef) return;
      const ctx = canvasRef.getContext('2d');
      const isHorizontal = layoutMode.value === 'horizontal';
      
      // Update canvas resolution based on orientation
      if (isHorizontal) {
        canvasRef.width = 220;
        canvasRef.height = 12;
      } else {
        canvasRef.width = 12;
        canvasRef.height = 180;
      }
      
      const w = canvasRef.width;
      const h = canvasRef.height;
      const preset = vtkColorMaps.getPresetByName(name);
      
      const gradient = isHorizontal 
        ? ctx.createLinearGradient(0, 0, w, 0) // Left to Right
        : ctx.createLinearGradient(0, h, 0, 0); // Bottom to Top

      const rgbPoints = preset.RGBPoints;
      let minT = Infinity, maxT = -Infinity;
      for (let i = 0; i < rgbPoints.length; i += 4) {
        if (rgbPoints[i] < minT) minT = rgbPoints[i];
        if (rgbPoints[i] > maxT) maxT = rgbPoints[i];
      }
      for (let i = 0; i < rgbPoints.length; i += 4) {
        let t = (rgbPoints[i] - minT) / (maxT - minT || 1);
        const r = Math.round(rgbPoints[i + 1] * 255);
        const g = Math.round(rgbPoints[i + 2] * 255);
        const b = Math.round(rgbPoints[i + 3] * 255);
        gradient.addColorStop(t, `rgb(${r},${g},${b})`);
      }
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, w, h);
    }

    function inferLabelRange(sourceSeg) {
      if (!sourceSeg || segmentationMode.value === 'none') return [0, 1];
      const modeField = normalizeSegmentationField(sourceSeg[segmentationMode.value]);
      if (!modeField || !modeField.length) return [0, 1];
      let min = Infinity;
      let max = -Infinity;
      for (let i = 0; i < modeField.length; i += 1) {
        const v = Number(modeField[i]);
        if (!Number.isFinite(v)) continue;
        if (v < min) min = v;
        if (v > max) max = v;
      }
      if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
      return [min, max];
    }

    function updateManifoldBar(canvasRef, range) {
      if (!canvasRef) return;
      const ctx = canvasRef.getContext('2d');
      const isHorizontal = layoutMode.value === 'horizontal';
      if (isHorizontal) {
        canvasRef.width = 220;
        canvasRef.height = 12;
      } else {
        canvasRef.width = 12;
        canvasRef.height = 180;
      }
      const w = canvasRef.width;
      const h = canvasRef.height;
      const minLabel = Number(range?.[0] ?? 0);
      const maxLabel = Number(range?.[1] ?? 1);
      const stops = getColormapStops(colormap.value);

      if (isHorizontal) {
        for (let x = 0; x < w; x += 1) {
          const t = x / Math.max(1, w - 1);
          const label = minLabel + t * (maxLabel - minLabel);
          const [r, g, b] = labelToColor(label, [minLabel, maxLabel], stops);
          ctx.fillStyle = `rgb(${r},${g},${b})`;
          ctx.fillRect(x, 0, 1, h);
        }
      } else {
        for (let y = 0; y < h; y += 1) {
          const t = 1 - (y / Math.max(1, h - 1));
          const label = minLabel + t * (maxLabel - minLabel);
          const [r, g, b] = labelToColor(label, [minLabel, maxLabel], stops);
          ctx.fillStyle = `rgb(${r},${g},${b})`;
          ctx.fillRect(0, y, w, 1);
        }
      }
    }

    function refreshColorBars() {
      if (segmentationMode.value === 'none') {
        updateScalarBar(scalarBarCanvasOriginal.value, colormap.value);
        updateScalarBar(scalarBarCanvasDecompressed.value, colormap.value);
        return;
      }
      const seg = segmentation.value || {};
      const originalRange = inferLabelRange(seg.original);
      const decompressedRange = inferLabelRange(selectedCompressor.value ? seg.decompressed?.[selectedCompressor.value] : null);
      currentLabelRangeOriginal.value = originalRange;
      currentLabelRangeDecompressed.value = decompressedRange;
      updateManifoldBar(manifoldBarCanvasOriginal.value, originalRange);
      updateManifoldBar(manifoldBarCanvasDecompressed.value, decompressedRange);
    }

    function segmentationLabel() {
      if (segmentationMode.value === 'ascending') return 'Ascending';
      if (segmentationMode.value === 'descending') return 'Descending';
      if (segmentationMode.value === 'morse_smale') return 'Morse-Smale';
      return 'Manifold';
    }

    function getLocalRange(data, dims, sliceIdx = 0) {
      if (!data) return [0, 1];
      const sliceSize = dims[0] * dims[1];
      const startIdx = sliceIdx * sliceSize;
      const endIdx = startIdx + sliceSize;
      let min = Infinity;
      let max = -Infinity;
      for (let i = startIdx; i < endIdx; i++) {
        const val = data[i];
        if (val < min) min = val;
        if (val > max) max = val;
      }
      if (min === Infinity) return [0, 1];
      return [min, max];
    }

    function setupThree(container) {
      const scene = new THREE.Scene();
      // We rely on the parent HTML element's background color (bg-dark) instead of WebGL background
      scene.background = null;

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.setPixelRatio(window.devicePixelRatio);
      const width = container.clientWidth || 1;
      const height = container.clientHeight || 1;
      renderer.setSize(width, height);
      container.appendChild(renderer.domElement);

      const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 100);
      camera.position.set(0, 0, 2.0);

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.1;

      // Track lead context for two-way sync
      const interactionHandler = () => {
        leadContext.value = container === containerOriginal.value ? 'original' : 'decompressed';
      };
      renderer.domElement.addEventListener('pointerdown', interactionHandler);
      renderer.domElement.addEventListener('wheel', interactionHandler, { passive: true });

      const resizeObserver = new ResizeObserver(() => {
        if (!isMounted.value) return;
        const width = container.clientWidth;
        const height = container.clientHeight;
        if (width === 0 || height === 0) return;
        renderer.setSize(width, height);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
      });
      resizeObserver.observe(container);

      const ctx = markRaw({
        scene: markRaw(scene),
        renderer: markRaw(renderer),
        camera: markRaw(camera),
        controls: markRaw(controls),
        resizeObserver,
        volumeMesh: null,
        sliceMesh: null,
        cpGroup: markRaw(new THREE.Group()),
        transferTexture: markRaw(createTransferFunctionTexture(colormap.value)),
        transferTextureOpaque: markRaw(createTransferFunctionTexture(colormap.value, { opaque: true })),
        cachedData: null,
        cachedRange: [0, 1],
      });
      scene.add(ctx.cpGroup);

      return ctx;
    }

    function fitCameraToView(ctx) {
      if (!ctx || !ctx.camera || !ctx.renderer) return;
      const container = ctx.renderer.domElement.parentElement;
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (width === 0 || height === 0) return;

      // Update renderer and aspect
      ctx.renderer.setSize(width, height);
      ctx.camera.aspect = width / height;
      ctx.camera.updateProjectionMatrix();

      // Fit logic: 
      // We want the object (roughly size 1.0) to fit comfortably.
      // Dist = (size/2) / tan(fov/2 * aspect_correction)
      const fovRad = (ctx.camera.fov * Math.PI) / 180;
      const size = 1.2 * visualScale.value; // Give some margin
      
      // For vertical containers, we need to account for the width being the limiting factor
      const distance = (size / 2) / Math.tan(fovRad / 2) / Math.min(1, ctx.camera.aspect);
      
      ctx.camera.position.set(0, 0, distance);
      ctx.camera.lookAt(0, 0, 0);
      ctx.controls.target.set(0, 0, 0);
      ctx.controls.update();
    }

    function toFloat32Data(content, precisionHint) {
      if (!content) return null;
      if (content instanceof Float32Array) return content;
      if (content instanceof Float64Array) return new Float32Array(content);
      if (ArrayBuffer.isView(content)) {
        const view = content;
        const ctorName = view.constructor?.name || '';
        if (ctorName === 'Float64Array') return new Float32Array(view);
        return new Float32Array(view.buffer.slice(view.byteOffset, view.byteOffset + view.byteLength));
      }
      if (!(content instanceof ArrayBuffer)) return null;
      const isDouble = precisionHint === 'd' || precisionHint === 'double' || precisionHint === 'float64';
      const rawArray = isDouble ? new Float64Array(content) : new Float32Array(content);
      return new Float32Array(rawArray);
    }

    function updateVisualization(ctx, content, dims, precision, isOriginal, options = {}) {
      if (!ctx || !content || !dims || dims[0] <= 0 || dims[1] <= 0) return;
      const { scene } = ctx;
      if (ctx.volumeMesh) scene.remove(ctx.volumeMesh);
      if (ctx.sliceMesh) scene.remove(ctx.sliceMesh);

      const data = toFloat32Data(content, precision);
      if (!data) return;
      ctx.cachedData = data;
      
      // Calculate global range, skipping NaNs and Infinites
      let min = Infinity, max = -Infinity;
      for (let i = 0; i < data.length; i++) {
        const v = data[i];
        if (isNaN(v) || !isFinite(v)) continue;
        if (v < min) min = v;
        if (v > max) max = v;
      }
      
      if (min === Infinity) { min = 0; max = 1; }
      console.log(`[Three] Data Range: [${min}, ${max}]`);
      ctx.cachedRange = [min, max];

      const is2D = !dims[2] || dims[2] <= 1 || isTimeVarying.value;
      
      // Determine actual range to use
      const forcedRange = options?.forcedRange;
      const transferOverride = options?.transferTexture || null;
      const opacityOverride = options?.opacityMultiplier;
      let displayRange = forcedRange ? [forcedRange[0], forcedRange[1]] : [...ctx.cachedRange];
      if (!forcedRange) {
        if (rescaleMethod.value === 'local' && is2D) {
          displayRange = getLocalRange(data, dims, sliceId.value);
        } else if (rescaleMethod.value === 'custom') {
          displayRange = [customMin.value, customMax.value];
        }
      }
      
      if (isOriginal) currentRangeOriginal.value = displayRange;
      else currentRangeDecompressed.value = displayRange;

      if (is2D) {
        const sliceSize = dims[0] * dims[1];
        const sliceData = data.slice(sliceId.value * sliceSize, (sliceId.value + 1) * sliceSize);
        const texture = new THREE.DataTexture(sliceData, dims[0], dims[1], THREE.RedFormat, THREE.FloatType);
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.unpackAlignment = 1;
        texture.needsUpdate = true;

        const maxDim = Math.max(dims[0], dims[1]);
        const aspectX = dims[0] / maxDim;
        const aspectY = dims[1] / maxDim;
        const geometry = new THREE.PlaneGeometry(aspectX, aspectY);
        const material = new THREE.ShaderMaterial({
          uniforms: {
            tex: { value: texture },
            transferFunction: { value: transferOverride || ctx.transferTexture },
            dataRange: { value: new THREE.Vector2(displayRange[0], displayRange[1]) }
          },
          vertexShader: `
            out vec2 vUv;
            void main() {
              vUv = uv;
              gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
          `,
          fragmentShader: `
            precision highp float;
            uniform sampler2D tex;
            uniform sampler2D transferFunction;
            uniform vec2 dataRange;
            in vec2 vUv;
            out vec4 outColor;
            void main() {
              float val = texture(tex, vUv).r;
              float norm = clamp((val - dataRange.x) / (dataRange.y - dataRange.x + 1e-10), 0.0, 1.0);
              outColor = texture(transferFunction, vec2(norm, 0.5));
            }
          `,
          side: THREE.DoubleSide,
          glslVersion: THREE.GLSL3
        });
        
        ctx.sliceMesh = markRaw(new THREE.Mesh(geometry, material));
        ctx.sliceMesh.scale.set(visualScale.value, visualScale.value, visualScale.value);
        scene.add(ctx.sliceMesh);
        
        // Reset camera for 2D
        ctx.controls.enableRotate = false;
        ctx.controls.mouseButtons = {
          LEFT: THREE.MOUSE.PAN,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.ROTATE
        };
        // Reset camera view to look straight down Z-axis
        ctx.camera.position.set(0, 0, 1.6);
        ctx.camera.up.set(0, 1, 0);
        ctx.camera.lookAt(0, 0, 0);
        ctx.controls.reset();
        
        // Ensure the 2D plane fits the view
        nextTick(() => {
          fitCameraToView(ctx);
        });
      } else {
        const texture = new THREE.Data3DTexture(data, dims[0], dims[1], dims[2]);
        texture.format = THREE.RedFormat;
        texture.type = THREE.FloatType;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.unpackAlignment = 1;
        texture.needsUpdate = true;

        const maxDim = Math.max(dims[0], dims[1], dims[2] || 0);
        const aspectX = dims[0] / maxDim;
        const aspectY = dims[1] / maxDim;
        const aspectZ = (dims[2] || 0) / maxDim;
        const geometry = new THREE.BoxGeometry(aspectX, aspectY, aspectZ);
        const material = new THREE.ShaderMaterial({
          uniforms: {
            volume: { value: texture },
            transferFunction: { value: transferOverride || ctx.transferTexture },
            inverseModelMatrix: { value: new THREE.Matrix4() }, // Will be updated
            dimensions: { value: new THREE.Vector3(dims[0], dims[1], dims[2]) },
            stepSize: { value: 1.5 / Math.max(dims[0], Math.max(dims[1], dims[2])) }, // Increased step size slightly (faster)
            opacityMultiplier: { value: typeof opacityOverride === 'number' ? opacityOverride : 1.0 },
            dataRange: { value: new THREE.Vector2(displayRange[0], displayRange[1]) }
          },
          vertexShader: volumeVertexShader,
          fragmentShader: volumeFragmentShader,
          transparent: true,
          side: THREE.BackSide,
          glslVersion: THREE.GLSL3
        });

        ctx.volumeMesh = markRaw(new THREE.Mesh(geometry, material));
        ctx.volumeMesh.scale.set(visualScale.value, visualScale.value, visualScale.value);
        scene.add(ctx.volumeMesh);
        ctx.controls.enableRotate = true;
        ctx.controls.mouseButtons = {
          LEFT: THREE.MOUSE.ROTATE,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.PAN
        };
      }
      
      renderCriticalPoints(ctx);
    }

    function updateSegmentationVisualization(ctx, sourceSeg, isOriginal) {
      if (!ctx || !sourceSeg || segmentationMode.value === 'none') return;
      const modeField = normalizeSegmentationField(sourceSeg[segmentationMode.value]);
      const dimsObj = sourceSeg.dimensions || {};
      const width = Number(dimsObj.width || dimensions.value?.[0] || 0);
      const height = Number(dimsObj.height || dimensions.value?.[1] || 0);
      const depth = Number(dimsObj.depth || dimensions.value?.[2] || 1);
      if (!modeField || !width || !height || !depth) return;
      const range = inferLabelRange(sourceSeg);
      updateVisualization(
        ctx,
        modeField,
        [width, height, depth],
        'float32',
        isOriginal,
        {
          forcedRange: range,
          transferTexture: ctx.transferTextureOpaque,
          opacityMultiplier: 1.0
        }
      );
    }

    function updateSegmentationThreePanels() {
      if (segmentationMode.value === 'none') return;
      const seg = segmentation.value;
      if (!seg) return;
      if (context.value.original && seg.original) {
        updateSegmentationVisualization(context.value.original, seg.original, true);
      }
      const decSeg = selectedCompressor.value ? seg.decompressed?.[selectedCompressor.value] : null;
      if (context.value.decompressed && decSeg) {
        updateSegmentationVisualization(context.value.decompressed, decSeg, false);
      }
      refreshColorBars();
    }

    function renderCriticalPoints(ctx) {
      if (!ctx || !criticalPoints.value) return;
      ctx.cpGroup.clear();

      const isOriginal = ctx === context.value.original;
      const cpData = isOriginal 
        ? (criticalPoints.value?.original)
        : (selectedCompressor.value ? criticalPoints.value?.decompressed?.[selectedCompressor.value] : null);

      console.log(`[Three] renderCriticalPoints for ${isOriginal ? 'original' : 'decompressed'}:`, {
        hasCpData: !!cpData,
        selectedCompressor: selectedCompressor.value,
        displayMode: criticalPointsDisplay.value,
        cpKeys: criticalPoints.value ? Object.keys(criticalPoints.value.decompressed || {}) : 'null'
      });

      if (!cpData || criticalPointsDisplay.value === 'none') {
        ctx.cpGroup.clear(); // Ensure it's cleared if no data or hidden (both original and decompressed)
        return;
      }

      const originalCP = criticalPoints.value.original;
      
      const filterFalse = (points, type) => {
        if (!points) return [];
        if (criticalPointsDisplay.value !== 'false_points' || isOriginal || !originalCP) return points;
        
        const origPoints = originalCP[type]?.points || [];
        const origSet = new Set(origPoints.map(p => `${p.x},${p.y},${p.z}`));
        
        return points.filter(p => !origSet.has(`${p.x},${p.y},${p.z}`));
      };

      const dims = dimensions.value || [1, 1, 1];
      const width = dims[0] || 1;
      const height = dims[1] || 1;
      const depth = dims[2] || 0; // Use 0 for missing depth
      const maxD = Math.max(width, height, depth);
      const aspectX = width / maxD;
      const aspectY = height / maxD;
      const is2D = depth <= 1 || isTimeVarying.value;
      const aspectZ = is2D ? 0 : (depth / maxD);
      
      // Ensure the group follows the visual scale of the mesh
      ctx.cpGroup.scale.set(visualScale.value, visualScale.value, visualScale.value);

      const radius = (1.0 / 80) * criticalPointsScale.value;

      // Shared geometry for all point types to save memory
      const sphereGeom = new THREE.SphereGeometry(radius, 10, 10);

      const addPoints = (points, colorHex) => {
        if (!points || points.length === 0) return;
        
        // MeshPhongMaterial is much lighter than MeshStandardMaterial
        const material = new THREE.MeshPhongMaterial({ 
          color: colorHex, 
          shininess: 100,
          specular: 0x444444
        });
        
        const mesh = new THREE.InstancedMesh(sphereGeom, material, points.length);
        mesh.renderOrder = 10; // Ensure spheres are drawn above the 2D plane regardless of tiny Z differences
        const matrix = new THREE.Matrix4();
        
        points.forEach((p, i) => {
          const pz = (p.z !== undefined) ? p.z : 0;
          const x = Math.max(-aspectX/2, Math.min(aspectX/2, (p.x / maxD) - aspectX/2));
          const y = Math.max(-aspectY/2, Math.min(aspectY/2, (p.y / maxD) - aspectY/2));
          
          if (is2D) {
            if (Math.abs(pz - Number(sliceId.value)) > 0.5) {
              matrix.makeScale(0, 0, 0);
            } else {
              matrix.makeTranslation(x, y, 0.01);
            }
          } else {
            const z = Math.max(-aspectZ/2, Math.min(aspectZ/2, (pz / maxD) - aspectZ/2));
            matrix.makeTranslation(x, y, z);
          }
          mesh.setMatrixAt(i, matrix);
        });
        mesh.instanceMatrix.needsUpdate = true;
        ctx.cpGroup.add(mesh);
      };

      // Simplified lighting: Directional + Ambient is usually enough for Phong
      const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
      dirLight.position.set(2, 2, 5);
      ctx.cpGroup.add(dirLight);
      
      ctx.cpGroup.add(new THREE.AmbientLight(0xaaaaaa));

      if (['minima', 'all', 'false_points'].includes(criticalPointsDisplay.value)) addPoints(filterFalse(cpData.minima?.points, 'minima'), minimaColor.value);
      if (['maxima', 'all', 'false_points'].includes(criticalPointsDisplay.value)) addPoints(filterFalse(cpData.maxima?.points, 'maxima'), maximaColor.value);
      if (['saddles', 'all', 'false_points'].includes(criticalPointsDisplay.value)) addPoints(filterFalse(cpData.saddles?.points, 'saddles'), saddleColor.value);
      
    }

    function updateColormap() {
      const tex = createTransferFunctionTexture(colormap.value);
      const opaqueTex = createTransferFunctionTexture(colormap.value, { opaque: true });
      [context.value.original, context.value.decompressed].forEach(ctx => {
        if (ctx) {
          ctx.transferTexture = tex;
          ctx.transferTextureOpaque = opaqueTex;
          if (ctx.volumeMesh) ctx.volumeMesh.material.uniforms.transferFunction.value = tex;
          if (ctx.sliceMesh) ctx.sliceMesh.material.uniforms.transferFunction.value = tex;
        }
      });
      if (segmentationMode.value !== 'none') {
        updateSegmentationThreePanels();
      }
      refreshColorBars();
    }

    function getColormapStops(name) {
      const preset = vtkColorMaps.getPresetByName(name) || vtkColorMaps.getPresetByName('jet');
      const rgbPoints = preset?.RGBPoints || [0, 0, 0, 0, 1, 1, 1, 1];
      let minT = Infinity;
      let maxT = -Infinity;
      for (let i = 0; i < rgbPoints.length; i += 4) {
        if (rgbPoints[i] < minT) minT = rgbPoints[i];
        if (rgbPoints[i] > maxT) maxT = rgbPoints[i];
      }
      const span = (maxT - minT) || 1;
      const stops = [];
      for (let i = 0; i < rgbPoints.length; i += 4) {
        stops.push({
          t: (rgbPoints[i] - minT) / span,
          r: rgbPoints[i + 1],
          g: rgbPoints[i + 2],
          b: rgbPoints[i + 3],
        });
      }
      return stops;
    }

    function sampleStops(stops, t) {
      if (!stops?.length) return [255, 255, 255];
      const tt = Math.max(0, Math.min(1, t));
      if (tt <= stops[0].t) {
        return [
          Math.round(stops[0].r * 255),
          Math.round(stops[0].g * 255),
          Math.round(stops[0].b * 255),
        ];
      }
      for (let i = 1; i < stops.length; i += 1) {
        const a = stops[i - 1];
        const b = stops[i];
        if (tt <= b.t) {
          const local = (tt - a.t) / Math.max(1e-8, b.t - a.t);
          const r = a.r + (b.r - a.r) * local;
          const g = a.g + (b.g - a.g) * local;
          const bl = a.b + (b.b - a.b) * local;
          return [
            Math.round(r * 255),
            Math.round(g * 255),
            Math.round(bl * 255),
          ];
        }
      }
      const last = stops[stops.length - 1];
      return [
        Math.round(last.r * 255),
        Math.round(last.g * 255),
        Math.round(last.b * 255),
      ];
    }

    function labelToColor(label, range = [0, 1], stops = null) {
      if (!Number.isFinite(label)) return [0, 0, 0, 0];
      const minLabel = Number(range?.[0] ?? 0);
      const maxLabel = Number(range?.[1] ?? 1);
      const denom = Math.max(1e-8, maxLabel - minLabel);
      const t = (label - minLabel) / denom;
      const [r, g, b] = sampleStops(stops || getColormapStops(colormap.value), t);
      return [
        r,
        g,
        b,
        255,
      ];
    }

    function updateVisuals() {
      if (segmentationMode.value !== 'none') {
        updateSegmentationThreePanels();
        return;
      }
      if (context.value.original && fileData.value) {
        updateVisualization(context.value.original, fileData.value, dimensions.value, precision.value, true);
      }
      if (context.value.decompressed && selectedDecompressedData.value) {
        updateVisualization(context.value.decompressed, selectedDecompressedData.value.decp_data, dimensions.value, precision.value, false);
      }
      refreshColorBars();
    }

    function syncCameras() {
      if (!sameCamera.value || !context.value.original || !context.value.decompressed) return;
      
      const source = leadContext.value === 'original' ? context.value.original : context.value.decompressed;
      const target = leadContext.value === 'original' ? context.value.decompressed : context.value.original;

      const sourceCam = source.camera;
      const sourceCtrl = source.controls;
      const targetCam = target.camera;
      const targetCtrl = target.controls;

      // Bidirectional Sync logic
      targetCam.position.copy(sourceCam.position);
      targetCam.quaternion.copy(sourceCam.quaternion);
      targetCam.zoom = sourceCam.zoom;
      targetCtrl.target.copy(sourceCtrl.target);
      targetCam.updateProjectionMatrix();
      targetCtrl.update();
    }

    onMounted(() => {
      isMounted.value = true;
      setTimeout(() => {
        if (containerOriginal.value) {
          context.value.original = setupThree(containerOriginal.value);
          if (fileData.value) {
            updateVisualization(context.value.original, fileData.value, dimensions.value, precision.value, true);
            nextTick(() => {
              refreshColorBars();
            });
          }
        }
        
        if (selectedDecompressedData.value && containerDecompressed.value) {
          context.value.decompressed = setupThree(containerDecompressed.value);
              updateVisualization(context.value.decompressed, selectedDecompressedData.value.decp_data, dimensions.value, precision.value, false);
              nextTick(() => {
                refreshColorBars();
              });
        }

        // Unified Animation Loop
        const mainAnimate = () => {
          if (!isMounted.value) return;
          requestAnimationFrame(mainAnimate);

          // 1. Update Controls
          if (sameCamera.value) {
            // Update the lead controls first
            if (leadContext.value === 'original' && context.value.original) {
              context.value.original.controls.update();
            } else if (leadContext.value === 'decompressed' && context.value.decompressed) {
              context.value.decompressed.controls.update();
            }
            // Then sync the other one
            syncCameras();
          } else {
            if (context.value.original) context.value.original.controls.update();
            if (context.value.decompressed) context.value.decompressed.controls.update();
          }

          // 3. Render Original
          if (context.value.original) {
            const ctx = context.value.original;
            if (ctx.renderer.domElement.width > 0 && ctx.renderer.domElement.height > 0) {
              if (ctx.volumeMesh) {
                ctx.volumeMesh.updateMatrixWorld();
                ctx.volumeMesh.material.uniforms.inverseModelMatrix.value.copy(ctx.volumeMesh.matrixWorld).invert();
              }
              ctx.renderer.render(ctx.scene, ctx.camera);
            }
          }

          // 4. Render Decompressed
          if (context.value.decompressed) {
            const ctx = context.value.decompressed;
            if (ctx.renderer.domElement.width > 0 && ctx.renderer.domElement.height > 0) {
              if (ctx.volumeMesh) {
                ctx.volumeMesh.updateMatrixWorld();
                ctx.volumeMesh.material.uniforms.inverseModelMatrix.value.copy(ctx.volumeMesh.matrixWorld).invert();
              }
              ctx.renderer.render(ctx.scene, ctx.camera);
            }
          }
        };
        mainAnimate();
      }, 200);
    });

    onBeforeUnmount(() => {
      isMounted.value = false;
      cleanupContext(context.value.original);
      cleanupContext(context.value.decompressed);
    });

    watch(fileData, (val) => {
      if (val) {
        if (context.value.original) {
          updateVisualization(context.value.original, val, dimensions.value, precision.value, true);
          nextTick(() => {
            refreshColorBars();
          });
        }
      } else {
        // Data removed, reset the original container
        if (context.value.original) {
          const { scene, cpGroup } = context.value.original;
          if (context.value.original.volumeMesh) scene.remove(context.value.original.volumeMesh);
          if (context.value.original.sliceMesh) scene.remove(context.value.original.sliceMesh);
          context.value.original.volumeMesh = null;
          context.value.original.sliceMesh = null;
          cpGroup.clear();
        }
      }
    });

    watch(selectedDecompressedData, (val) => {
      if (val) {
        if (segmentationMode.value !== 'none') {
          nextTick(() => {
            if (!context.value.decompressed && containerDecompressed.value) {
              context.value.decompressed = setupThree(containerDecompressed.value);
            }
            updateSegmentationThreePanels();
            if (context.value.original) fitCameraToView(context.value.original);
            if (context.value.decompressed) fitCameraToView(context.value.decompressed);
          });
          return;
        }
        if (!context.value.decompressed) {
          nextTick(() => {
            if (containerDecompressed.value) {
              context.value.decompressed = setupThree(containerDecompressed.value);
              updateVisualization(context.value.decompressed, val.decp_data, dimensions.value, precision.value, false);
              nextTick(() => {
                refreshColorBars();
              });
              
              // Rescale both to fit the new side-by-side layout
              fitCameraToView(context.value.original);
              fitCameraToView(context.value.decompressed);
            }
          });
        } else {
          updateVisualization(context.value.decompressed, val.decp_data, dimensions.value, precision.value, false);
          // If we are just switching data, still ensure it fits correctly
          nextTick(() => {
            fitCameraToView(context.value.original);
            fitCameraToView(context.value.decompressed);
          });
        }
      } else {
        cleanupContext(context.value.decompressed);
        context.value.decompressed = null;
        // Rescale original to fill the full container again
        nextTick(() => {
          if (context.value.original) fitCameraToView(context.value.original);
        });
      }
    });

    watch(colormap, updateColormap);
    watch([sliceId, rescaleMethod, customMin, customMax], updateVisuals);
    watch(segmentation, updateSegmentationThreePanels, { deep: true });
    watch(segmentationMode, (mode) => {
      if (mode !== 'none' && !hasAnySegmentation.value) {
        segmentationMode.value = 'none';
        return;
      }
      updateVisuals();
      nextTick(() => refreshColorBars());
    });
    watch(criticalPoints, () => {
      if (context.value.original) renderCriticalPoints(context.value.original);
      if (context.value.decompressed) renderCriticalPoints(context.value.decompressed);
    }, { deep: true });

    watch([criticalPointsDisplay, minimaColor, maximaColor, saddleColor, criticalPointsScale], () => {
      if (context.value.original) renderCriticalPoints(context.value.original);
      if (context.value.decompressed) renderCriticalPoints(context.value.decompressed);
    });

    watch(layoutMode, (newMode) => {
      if (newMode === 'horizontal') {
        scalarBarTop.value = 88;
        scalarBarLeft.value = 50; // 50% = centered
      } else {
        scalarBarTop.value = 18;
        scalarBarLeft.value = 88; // Keep near right edge
      }

      nextTick(() => {
        if (context.value.original) fitCameraToView(context.value.original);
        if (context.value.decompressed) fitCameraToView(context.value.decompressed);
        
        // Update scalar bars
        refreshColorBars();
      });
    });

    async function saveScreenshot(which) {
      const ctx = which === 'original' ? context.value.original : context.value.decompressed;
      if (!ctx || !ctx.renderer) return;

      const el = which === 'original' ? containerOriginal.value?.parentElement : containerDecompressed.value?.parentElement;
      if (!el) return;

      try {
        const canvas = await html2canvas(el, {
          backgroundColor: '#343a40', // Explicitly use the dark background color of the container
        });

        const dataURL = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        const label = which === 'original' ? 'original' : (selectedCompressor.value || 'decompressed');
        link.download = `screenshot_${label}.png`;
        link.href = dataURL;
        link.click();
      } catch (err) {
        console.error('Screenshot error:', err);
      }
    }

    function saveData(which) {
      let rawData, label;
      const prec = precision.value;
      if (which === 'original') {
        rawData = fileData.value;
        label = 'original';
      } else {
        rawData = selectedDecompressedData.value?.decp_data;
        label = selectedCompressor.value || 'decompressed';
      }
      if (!rawData) return;
      // rawData may be an ArrayBuffer or TypedArray
      let buffer;
      if (rawData instanceof ArrayBuffer) {
        buffer = rawData;
      } else if (ArrayBuffer.isView(rawData)) {
        buffer = rawData.buffer.slice(rawData.byteOffset, rawData.byteOffset + rawData.byteLength);
      } else {
        console.warn('saveData: unknown rawData type');
        return;
      }
      const ext = (prec === 'd' || prec === 'double' || prec === 'float64') ? 'f64' : 'f32';
      const blob = new Blob([buffer], { type: 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.download = `data_${label}.${ext}.bin`;
      link.href = url;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    }

    return {
      containerOriginal,
      containerDecompressed,
      scalarBarCanvasOriginal,
      scalarBarCanvasDecompressed,
      colormap,
      sliceId,
      rescaleMethod,
      customMin,
      customMax,
      sameCamera,
      dimensions,
      isTimeVarying,
      hasDecompressedData,
      selectedDecompressedIndex,
      decompressedKeys,
      selectedCompressor,
      selectedDecompressedData,
      segmentationMode,
      segmentationModeOptions,
      hasAnySegmentation,
      criticalPointsDisplay,
      criticalPointsScale,
      minimaColor,
      maximaColor,
      saddleColor,
      manifoldBarCanvasOriginal,
      manifoldBarCanvasDecompressed,
      currentRangeOriginal,
      currentRangeDecompressed,
      currentLabelRangeOriginal,
      currentLabelRangeDecompressed,
      hasAnyCriticalPoints: computed(() => {
        if (!criticalPoints.value) return false;
        const hasOriginal = criticalPoints.value.original && 
          (criticalPoints.value.original.minima?.points?.length > 0 || 
           criticalPoints.value.original.maxima?.points?.length > 0 || 
           criticalPoints.value.original.saddles?.points?.length > 0);
        const hasDecompressed = criticalPoints.value.decompressed && 
          Object.values(criticalPoints.value.decompressed).some(cp => 
            cp.minima?.points?.length > 0 || 
            cp.maxima?.points?.length > 0 || 
            cp.saddles?.points?.length > 0
          );
        return hasOriginal || hasDecompressed;
      }),
      allPresets,
      formatValue,
      visualScale,
      layoutMode,
      scalarBarTop,
      scalarBarLeft,
      startDrag,
      fileData,
      segmentationLabel,
      saveScreenshot,
      saveData,
    };
  }
};
</script>

<template>
  <div class="three-wrapper">
    <div
      id="options-top"
      class="d-flex flex-column align-items-center justify-content-center mt-3 py-2 bg-light rounded shadow-sm border"
    >
      <!-- Top controls row -->
      <div class="d-flex flex-wrap align-items-center justify-content-center gap-3 w-100 px-3">
        <!-- Colormap -->
        <div class="d-flex align-items-center me-2">
          <label class="me-2 mb-0 fw-semibold text-secondary small">
            <i class="bi bi-palette me-1"></i>Colormap:
          </label>
          <select
            class="form-select form-select-sm"
            v-model="colormap"
            style="min-width: 120px; max-width: 180px;"
          >
            <option v-for="preset in allPresets" :value="preset" :key="preset">
              {{ preset }}
            </option>
          </select>
        </div>

        <button
          :class="['btn btn-sm d-flex align-items-center', sameCamera ? 'btn-primary' : 'btn-outline-primary']"
          @click="sameCamera = !sameCamera"
          title="Synchronize camera views"
        >
          <i class="bi bi-camera me-1"></i>Sync Camera
        </button>

        <!-- Layout Mode Toggle -->
        <div class="btn-group btn-group-sm">
          <button 
            class="btn" 
            :class="layoutMode === 'horizontal' ? 'btn-primary' : 'btn-outline-primary'"
            @click="layoutMode = 'horizontal'"
            title="Horizontal comparison"
          >
            <i class="bi bi-columns"></i>
          </button>
          <button 
            class="btn" 
            :class="layoutMode === 'vertical' ? 'btn-primary' : 'btn-outline-primary'"
            @click="layoutMode = 'vertical'"
            title="Vertical comparison"
          >
            <i class="bi bi-view-stacked"></i>
          </button>
        </div>


      </div>

      <!-- Decompressed Data Selector -->
      <div
        v-if="hasDecompressedData"
        class="d-flex align-items-center justify-content-center gap-2 w-100 mt-2 border-top pt-2 px-3"
      >
        <label class="me-2 mb-0 fw-semibold text-secondary small">
          <i class="bi bi-box me-1"></i>Decompressed:
        </label>
        <select
          v-model.number="selectedDecompressedIndex"
          class="form-select form-select-sm"
          style="width: 240px; min-width: 180px;"
        >
          <option v-for="(key, index) in decompressedKeys" :key="key" :value="index">
            {{ key }}
          </option>
        </select>
      </div>

      <!-- Critical Points Settings Row -->
      <div v-if="hasAnyCriticalPoints" class="d-flex flex-wrap align-items-center justify-content-center gap-3 w-100 mt-1 border-top pt-2 px-3">
        <!-- Mode -->
        <div class="d-flex align-items-center">
          <label class="me-2 mb-0 fw-semibold text-secondary small">
            <i class="bi bi-bullseye me-1"></i>Critical Points:
          </label>
          <select
            v-model="criticalPointsDisplay"
            class="form-select form-select-sm"
            style="width: 130px; font-size: 0.75rem;"
          >
            <option value="none">None</option>
            <option value="minima">Minima Only</option>
            <option value="maxima">Maxima Only</option>
            <option value="saddles">Saddles Only</option>
            <option value="all">Display All</option>
            <option value="false_points">False Points Only</option>
          </select>
        </div>

        <!-- Colors & Size -->
        <div v-if="criticalPointsDisplay !== 'none'" class="d-flex align-items-center gap-2">
          <div v-if="['minima', 'both', 'all', 'false_points'].includes(criticalPointsDisplay)" class="d-flex align-items-center">
            <label class="me-1 mb-0 text-secondary small">Min:</label>
            <input type="color" v-model="minimaColor" class="form-control form-control-sm form-control-color" style="width: 28px; height: 22px; padding: 1px;" />
          </div>
          <div v-if="['maxima', 'both', 'all', 'false_points'].includes(criticalPointsDisplay)" class="d-flex align-items-center">
            <label class="me-1 mb-0 text-secondary small">Max:</label>
            <input type="color" v-model="maximaColor" class="form-control form-control-sm form-control-color" style="width: 28px; height: 22px; padding: 1px;" />
          </div>
          <div v-if="['saddles', 'all', 'false_points'].includes(criticalPointsDisplay)" class="d-flex align-items-center">
            <label class="me-1 mb-0 text-secondary small">Sad:</label>
            <input type="color" v-model="saddleColor" class="form-control form-control-sm form-control-color" style="width: 28px; height: 22px; padding: 1px;" />
          </div>
          <div class="d-flex align-items-center ms-1">
            <label class="me-1 mb-0 text-secondary small">Size:</label>
            <div class="d-flex align-items-center gap-1">
              <input 
                type="range" 
                v-model.number="criticalPointsScale" 
                class="form-range" 
                min="0.1" 
                max="1.0" 
                step="0.05" 
                style="width: 120px;" 
              />
              <input 
                type="number" 
                v-model.number="criticalPointsScale" 
                class="form-control form-control-sm px-1 text-center" 
                min="0.05" 
                max="1.0" 
                step="0.05" 
                style="width: 60px; font-size: 0.75rem; height: 24px;" 
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Segmentation Selection -->
      <div class="d-flex flex-wrap align-items-center justify-content-center gap-2 w-100 mt-2 border-top pt-2 px-3">
        <label class="me-2 mb-0 fw-semibold text-secondary small">
          <i class="bi bi-grid-1x2 me-1"></i>Segmentation:
        </label>
        <select
          v-model="segmentationMode"
          class="form-select form-select-sm"
          style="width: 190px; font-size: 0.75rem;"
          :disabled="!hasAnySegmentation"
        >
          <option v-for="option in segmentationModeOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <span class="tiny text-muted" v-if="!hasAnySegmentation">
          Run Critical Points to compute Morse-Smale manifolds.
        </span>
      </div>
    </div>

    <!-- Visualization containers -->
    <div :class="['vis-grid mt-3', layoutMode]">
      <!-- Original Container -->
      <div class="card d-flex flex-column shadow-sm overflow-hidden" style="min-width:0;">
        <div class="card-header py-1 bg-white">
          <div class="d-flex align-items-center justify-content-between">
            <span class="fw-bold text-primary small">Original</span>
            <div class="d-flex align-items-center gap-2">
              <div v-if="isTimeVarying && dimensions" class="d-flex align-items-center gap-2">
                <select v-model="rescaleMethod" class="form-select form-select-sm w-auto" style="font-size: 0.75rem;">
                  <option value="global">Global</option>
                  <option value="local">Local</option>
                  <option value="custom">Custom</option>
                </select>
                <div v-if="rescaleMethod === 'custom'" class="d-flex gap-1">
                  <input type="number" v-model="customMin" class="form-control form-control-sm" style="width:60px; font-size: 0.75rem;">
                  <input type="number" v-model="customMax" class="form-control form-control-sm" style="width:60px; font-size: 0.75rem;">
                </div>
                <label class="small mb-0 text-secondary">Slice:</label>
                <input type="range" min="0" :max="(dimensions ? dimensions[2]-1 : 0)" v-model="sliceId" class="form-range" style="width:80px">
                <span class="badge bg-secondary" style="font-size: 0.7rem;">{{ sliceId }}</span>
              </div>
              <!-- Action buttons -->
              <button
                v-if="fileData"
                class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
                title="Save data as binary file"
                @click="saveData('original')"
                style="font-size: 0.72rem; padding: 1px 6px;"
              >
                <i class="bi bi-download"></i> Data
              </button>
              <button
                v-if="fileData"
                class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
                title="Save screenshot as PNG"
                @click="saveScreenshot('original')"
                style="font-size: 0.72rem; padding: 1px 6px;"
              >
                <i class="bi bi-camera"></i> PNG
              </button>
            </div>
          </div>
        </div>
        <div class="card-body p-0 position-relative bg-dark">
          <div ref="containerOriginal" class="three-host w-100 h-100"></div>
          <!-- Custom Scalar Bar Overlay -->
          <div 
             :class="['scalar-bar-overlay', layoutMode]" 
             v-if="segmentationMode === 'none' && colormap && fileData"
             :style="{ top: scalarBarTop + '%', left: scalarBarLeft + '%' }"
             @mousedown.stop="startDrag"
          >
             <div class="scalar-title">Intensity</div>
             <div :class="['scalar-content', layoutMode]">
               <span class="label-min">{{ formatValue(currentRangeOriginal[0]) }}</span>
               <canvas ref="scalarBarCanvasOriginal"></canvas>
               <span class="label-max">{{ formatValue(currentRangeOriginal[1]) }}</span>
             </div>
          </div>
          <div 
             :class="['scalar-bar-overlay', layoutMode]" 
             v-if="segmentationMode !== 'none' && hasAnySegmentation"
             :style="{ top: scalarBarTop + '%', left: scalarBarLeft + '%' }"
             @mousedown.stop="startDrag"
          >
             <div class="scalar-title">{{ segmentationLabel() }}</div>
             <div :class="['scalar-content', layoutMode]">
               <span class="label-min">{{ Math.floor(currentLabelRangeOriginal[0]) }}</span>
               <canvas ref="manifoldBarCanvasOriginal"></canvas>
               <span class="label-max">{{ Math.floor(currentLabelRangeOriginal[1]) }}</span>
             </div>
          </div>
        </div>
      </div>

      <!-- Decompressed Container -->
      <div
        v-if="selectedDecompressedData"
        class="card d-flex flex-column shadow-sm overflow-hidden"
        style="min-width:0;"
      >
        <div class="card-header py-1 bg-white">
          <div class="d-flex align-items-center justify-content-between">
            <span class="fw-bold text-success small">Decompressed ({{ selectedCompressor }})</span>
            <div class="d-flex align-items-center gap-2">
              <button
                class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
                title="Save decompressed data as binary file"
                @click="saveData('decompressed')"
                style="font-size: 0.72rem; padding: 1px 6px;"
              >
                <i class="bi bi-download"></i> Data
              </button>
              <button
                class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
                title="Save screenshot as PNG"
                @click="saveScreenshot('decompressed')"
                style="font-size: 0.72rem; padding: 1px 6px;"
              >
                <i class="bi bi-camera"></i> PNG
              </button>
            </div>
          </div>
        </div>
        <div class="card-body p-0 position-relative bg-dark">
          <div ref="containerDecompressed" class="three-host w-100 h-100"></div>
          <!-- Custom Scalar Bar Overlay -->
          <div 
             :class="['scalar-bar-overlay', layoutMode]" 
             v-if="segmentationMode === 'none' && colormap && selectedDecompressedData"
             :style="{ top: scalarBarTop + '%', left: scalarBarLeft + '%' }"
             @mousedown.stop="startDrag"
          >
             <div class="scalar-title">Intensity</div>
             <div :class="['scalar-content', layoutMode]">
               <span class="label-min">{{ formatValue(currentRangeDecompressed[0]) }}</span>
               <canvas ref="scalarBarCanvasDecompressed"></canvas>
               <span class="label-max">{{ formatValue(currentRangeDecompressed[1]) }}</span>
             </div>
          </div>
          <div 
             :class="['scalar-bar-overlay', layoutMode]" 
             v-if="segmentationMode !== 'none' && selectedDecompressedData"
             :style="{ top: scalarBarTop + '%', left: scalarBarLeft + '%' }"
             @mousedown.stop="startDrag"
          >
             <div class="scalar-title">{{ segmentationLabel() }}</div>
             <div :class="['scalar-content', layoutMode]">
               <span class="label-min">{{ Math.floor(currentLabelRangeDecompressed[0]) }}</span>
               <canvas ref="manifoldBarCanvasDecompressed"></canvas>
               <span class="label-max">{{ Math.floor(currentLabelRangeDecompressed[1]) }}</span>
             </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.three-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: hidden; /* Controlled by vis-grid */
}

.vis-grid {
  display: flex;
  gap: 1rem;
  width: 100%;
  padding: 0 1rem 1rem 1rem;
  flex-grow: 1;
  min-height: 0;
}

.vis-grid.horizontal {
  flex-direction: row;
}

.vis-grid.vertical {
  flex-direction: column;
  overflow-y: auto;
}

.vis-grid .card {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: white;
}

.vis-grid.vertical .card {
  min-height: 400px;
  flex: 0 0 auto; /* Don't shrink cards in vertical mode */
}

.vis-grid.horizontal .card-body {
  flex-grow: 1;
  min-height: 0;
}

/* Responsive fallback for narrow views */
@media (max-width: 800px) {
  .vis-grid.horizontal {
    flex-direction: column;
    overflow-y: auto;
  }
  .vis-grid.horizontal .card {
    min-height: 400px;
    flex: 0 0 auto;
  }
}

.three-host {
  position: absolute;
  top: 0; bottom: 0; left: 0; right: 0;
  cursor: crosshair;
}

.card {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(0,0,0,0.1);
}

.btn-xs {
  padding: 0.1rem 0.3rem;
  font-size: 0.75rem;
}

.scalar-bar-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  background: rgba(0, 0, 0, 0.7);
  padding: 12px 10px;
  border-radius: 6px;
  pointer-events: auto;
  cursor: move;
  border: 1px solid rgba(255, 255, 255, 0.2);
  user-select: none;
  z-index: 10;
  box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}

.scalar-bar-overlay.horizontal {
  flex-direction: column;
  padding: 8px 16px;
}

.scalar-bar-overlay.vertical {
  flex-direction: row;
}

.scalar-title {
  color: #adb5bd;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.scalar-bar-overlay.vertical .scalar-title {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  margin-right: 4px;
}

.scalar-bar-overlay.horizontal .scalar-title {
  margin-bottom: 4px;
}

.scalar-content {
  position: relative;
  display: flex;
  align-items: center;
}

.scalar-content.vertical {
  flex-direction: column;
  padding: 12px 0;
  min-width: 45px;
}

.scalar-content.horizontal {
  flex-direction: row;
  padding: 0 0 16px 0; /* Bottom padding for labels */
  min-height: 35px;
  min-width: 220px;
}

.label-min, .label-max {
  position: absolute;
  color: white;
  font-size: 0.7rem;
  font-family: 'JetBrains Mono', monospace;
  white-space: nowrap;
}

.vertical .label-max {
  top: -2px;
  left: 50%;
  transform: translateX(-50%);
}

.vertical .label-min {
  bottom: -2px;
  left: 50%;
  transform: translateX(-50%);
}

.horizontal .label-min {
  left: 0;
  bottom: -2px;
  top: auto;
  transform: none;
}

.horizontal .label-max {
  right: 0;
  bottom: -2px;
  top: auto;
  transform: none;
}

.form-control-color {
  cursor: pointer;
}

/* Adjust range thumb size for small UI */
.form-range::-webkit-slider-thumb {
  width: 0.8rem;
  height: 0.8rem;
}
</style>
