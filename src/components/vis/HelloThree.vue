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

    const context = ref({
      original: null,
      decompressed: null,
    });
    const colormap = ref("jet");
    
    let sameCamera = ref(false);
    const currentRangeOriginal = ref([0, 1]);
    const currentRangeDecompressed = ref([0, 1]);
    
    const comparisonData = computed(() => store.state.comparisonData);
    const criticalPoints = computed(() => store.state.criticalPoints);
    const criticalPointsDisplay = ref('all');
    const criticalPointsScale = ref(0.3);
    const minimaColor = ref('#666666');
    const maximaColor = ref('#ff0000');
    const saddleColor = ref('#ffcc00');
    
    // Movable Colorbar and Scaling
    const visualScale = ref(1.0);
    const scalarBarTop = ref(88); // Default for horizontal layout
    const scalarBarRight = ref(50); // Centered for horizontal layout
    const isDragging = ref(false);
    let dragStart = { x: 0, y: 0, top: 0, right: 0 };
    
    const layoutMode = ref('horizontal'); // 'horizontal' or 'vertical'
    const leadContext = ref('original'); // 'original' or 'decompressed'

    function startDrag(e) {
      isDragging.value = true;
      dragStart = { 
        x: e.clientX, 
        y: e.clientY, 
        top: scalarBarTop.value, 
        right: scalarBarRight.value 
      };
      window.addEventListener('mousemove', handleDrag);
      window.addEventListener('mouseup', stopDrag);
    }

    function handleDrag(e) {
      if (!isDragging.value || !containerOriginal.value) return;
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      
      const containerWidth = containerOriginal.value.clientWidth || 1;
      const containerHeight = containerOriginal.value.clientHeight || 1;
      
      // Update position in percentage
      scalarBarTop.value = Math.max(0, Math.min(100, dragStart.top + (dy / containerHeight * 100))); 
      scalarBarRight.value = Math.max(0, Math.min(100, dragStart.right - (dx / containerWidth * 100)));
    }

    function stopDrag() {
      isDragging.value = false;
      window.removeEventListener('mousemove', handleDrag);
      window.removeEventListener('mouseup', stopDrag);
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

    function createTransferFunctionTexture(name) {
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
        // Add linear alpha ramp: 0 at min, 1 at max
        const a = t; 
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

    function updateVisualization(ctx, content, dims, precision, isOriginal) {
      if (!ctx || !content || !dims || dims[0] <= 0 || dims[1] <= 0) return;
      const { scene } = ctx;
      if (ctx.volumeMesh) scene.remove(ctx.volumeMesh);
      if (ctx.sliceMesh) scene.remove(ctx.sliceMesh);

      const isDouble = precision === 'd' || precision === 'double' || precision === 'float64';
      // More robust conversion: handle ArrayBuffer or TypedArray inputs
      const rawArray = isDouble ? new Float64Array(content) : new Float32Array(content);
      const data = new Float32Array(rawArray);
      ctx.cachedData = data;
      
      console.log(`[Three] ${isOriginal ? 'Original' : 'Decompressed'} Data: ${data.length} pts, prec: ${precision}, dims: ${dims.join('x')}`);

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
      let displayRange = [...ctx.cachedRange];
      if (rescaleMethod.value === 'local' && is2D) {
        displayRange = getLocalRange(data, dims, sliceId.value);
      } else if (rescaleMethod.value === 'custom') {
        displayRange = [customMin.value, customMax.value];
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
            transferFunction: { value: ctx.transferTexture },
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
            transferFunction: { value: ctx.transferTexture },
            inverseModelMatrix: { value: new THREE.Matrix4() }, // Will be updated
            dimensions: { value: new THREE.Vector3(dims[0], dims[1], dims[2]) },
            stepSize: { value: 1.5 / Math.max(dims[0], Math.max(dims[1], dims[2])) }, // Increased step size slightly (faster)
            opacityMultiplier: { value: 1.0 },
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

      console.log(`[Three] cpData for ${isOriginal ? 'original' : 'decompressed'}:`, {
        minima: cpData.minima?.points?.length || 0,
        maxima: cpData.maxima?.points?.length || 0,
        saddles: cpData.saddles?.points?.length || 0,
        sampleMin: cpData.minima?.points?.[0] || 'none'
      });

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
      
      console.log(`[Three] Rendered ${ctx.cpGroup.children.filter(c => c.isInstancedMesh).length} CP types for ${isOriginal ? 'original' : 'decompressed'}`);
    }

    function updateColormap() {
      const tex = createTransferFunctionTexture(colormap.value);
      [context.value.original, context.value.decompressed].forEach(ctx => {
        if (ctx) {
          ctx.transferTexture = tex;
          if (ctx.volumeMesh) ctx.volumeMesh.material.uniforms.transferFunction.value = tex;
          if (ctx.sliceMesh) ctx.sliceMesh.material.uniforms.transferFunction.value = tex;
        }
      });
      updateScalarBar(scalarBarCanvasOriginal.value, colormap.value);
      updateScalarBar(scalarBarCanvasDecompressed.value, colormap.value);
    }

    function updateVisuals() {
      if (context.value.original && fileData.value) {
        updateVisualization(context.value.original, fileData.value, dimensions.value, precision.value, true);
      }
      if (context.value.decompressed && selectedDecompressedData.value) {
        updateVisualization(context.value.decompressed, selectedDecompressedData.value.decp_data, dimensions.value, precision.value, false);
      }
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
              updateScalarBar(scalarBarCanvasOriginal.value, colormap.value);
            });
          }
        }
        
        if (selectedDecompressedData.value && containerDecompressed.value) {
          context.value.decompressed = setupThree(containerDecompressed.value);
          updateVisualization(context.value.decompressed, selectedDecompressedData.value.decp_data, dimensions.value, precision.value, false);
          nextTick(() => {
            updateScalarBar(scalarBarCanvasDecompressed.value, colormap.value);
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
            updateScalarBar(scalarBarCanvasOriginal.value, colormap.value);
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
        if (!context.value.decompressed) {
          nextTick(() => {
            if (containerDecompressed.value) {
              context.value.decompressed = setupThree(containerDecompressed.value);
              updateVisualization(context.value.decompressed, val.decp_data, dimensions.value, precision.value, false);
              nextTick(() => {
                updateScalarBar(scalarBarCanvasDecompressed.value, colormap.value);
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
    watch(criticalPoints, (val) => {
      console.log('[Three] criticalPoints changed:', {
        hasOriginal: !!val?.original,
        decompressedKeys: Object.keys(val?.decompressed || {})
      });
      if (context.value.original) renderCriticalPoints(context.value.original);
      if (context.value.decompressed) renderCriticalPoints(context.value.decompressed);
    }, { deep: true });

    watch([criticalPointsDisplay, minimaColor, maximaColor, saddleColor, criticalPointsScale], () => {
      console.log('[Three] CP settings changed');
      if (context.value.original) renderCriticalPoints(context.value.original);
      if (context.value.decompressed) renderCriticalPoints(context.value.decompressed);
    });

    watch(layoutMode, (newMode) => {
      if (newMode === 'horizontal') {
        scalarBarTop.value = 88;
        scalarBarRight.value = 50; // 50% = Centered (with transform)
      } else {
        scalarBarTop.value = 50;
        scalarBarRight.value = 10; // Extra room from right
      }

      nextTick(() => {
        if (context.value.original) fitCameraToView(context.value.original);
        if (context.value.decompressed) fitCameraToView(context.value.decompressed);
        
        // Update scalar bars
        updateScalarBar(scalarBarCanvasOriginal.value, colormap.value);
        updateScalarBar(scalarBarCanvasDecompressed.value, colormap.value);
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
      criticalPointsDisplay,
      criticalPointsScale,
      minimaColor,
      maximaColor,
      saddleColor,
      currentRangeOriginal,
      currentRangeDecompressed,
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
      scalarBarRight,
      startDrag,
      fileData,
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
             v-if="colormap && fileData"
             :style="{ top: scalarBarTop + '%', right: scalarBarRight + '%' }"
             @mousedown.stop="startDrag"
          >
             <div class="scalar-title">Intensity</div>
             <div :class="['scalar-content', layoutMode]">
               <span class="label-min">{{ formatValue(currentRangeOriginal[0]) }}</span>
               <canvas ref="scalarBarCanvasOriginal"></canvas>
               <span class="label-max">{{ formatValue(currentRangeOriginal[1]) }}</span>
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
             v-if="colormap && selectedDecompressedData"
             :style="{ top: scalarBarTop + '%', right: scalarBarRight + '%' }"
             @mousedown.stop="startDrag"
          >
             <div class="scalar-title">Intensity</div>
             <div :class="['scalar-content', layoutMode]">
               <span class="label-min">{{ formatValue(currentRangeDecompressed[0]) }}</span>
               <canvas ref="scalarBarCanvasDecompressed"></canvas>
               <span class="label-max">{{ formatValue(currentRangeDecompressed[1]) }}</span>
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
  right: 5%;
  transform: translate(50%, -50%); /* Center based on right property */
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
