<script>
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick, markRaw } from 'vue';
import { useStore } from 'vuex';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls';
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
    const endianness = computed(() => store.state.dataset?.endianness || 'little');
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
    const colormap = ref("Viridis (matplotlib)");
    
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
    const showBoundaryLines = ref(false);
    
    const highlightRegionMode = ref('none'); // 'none', 'top5', 'top10', 'top20', 'most_diff'
    const showColorBarOverlay = ref(true);
    const rendererBgColor = ref('dark'); // Background color for renderer: 'transparent', 'white', 'dark', 'black'

    watch([highlightRegionMode], () => {
      if (segmentationMode.value !== 'none') {
        updateSegmentationThreePanels();
      }
    });

    // Watch background color changes and update renderers
    watch(rendererBgColor, (newColor) => {
      const colorMap = {
        'transparent': { color: 0x000000, alpha: 0 },
        'white': { color: 0xffffff, alpha: 1 },
        'dark': { color: 0x343a40, alpha: 1 },
        'black': { color: 0x000000, alpha: 1 }
      };
      const bgSetting = colorMap[newColor] || colorMap['dark'];

      if (context.value.original?.renderer) {
        context.value.original.renderer.setClearColor(bgSetting.color, bgSetting.alpha);
      }
      if (context.value.decompressed?.renderer) {
        context.value.decompressed.renderer.setClearColor(bgSetting.color, bgSetting.alpha);
      }
    });

    // Movable Colorbar and Scaling
    const visualScale = ref(1.0);
    const scalarBarTop = ref(88); // Default for horizontal layout
    const scalarBarLeft = ref(50); // Centered for horizontal layout
    const isDragging = ref(false);
    let dragStart = { x: 0, y: 0, top: 0, left: 0, width: 1, height: 1 };
    
    const layoutMode = ref('horizontal'); // 'horizontal' or 'vertical'
    const leadContext = ref('original'); // 'original' or 'decompressed'

    // ROI
    const roiEnabled = ref(false);
    const roiApplied = ref(false); // Whether ROI cropping is currently applied to visualization
    const roiMode = ref('scale'); // 'scale' | 'translate'
    const isTransformingROI = ref(false);
    const roiXStart = ref(20);
    const roiXEnd = ref(80);
    const roiYStart = ref(20);
    const roiYEnd = ref(80);
    const roiZStart = ref(20);
    const roiZEnd = ref(80);

    // Draw-ROI state
    const roiDrawMode = ref(false);   // user has activated draw mode
    const roiIsDrawing = ref(false);  // mouse is held down and dragging
    const roiDrawRect = ref(null);    // { x, y, w, h } in px for SVG overlay
    const roiZDepth = ref(100);       // Z span percentage (for 3D volumes)

    // We store mousedown start in plain vars (no reactivity overhead)
    let _drawStart = { x: 0, y: 0 };
    let _drawContainer = null; // which container element was targeted


    function onROIMouseDown(e, which) {
      if (!roiEnabled.value || !roiDrawMode.value) return;
      const container = which === 'original' ? containerOriginal.value : containerDecompressed.value;
      if (!container) return;
      e.preventDefault();
      e.stopPropagation();
      const rect = container.getBoundingClientRect();
      _drawStart = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      _drawContainer = container;
      roiIsDrawing.value = true;
      roiDrawRect.value = { x: _drawStart.x, y: _drawStart.y, w: 0, h: 0 };
    }

    function onROIMouseMove(e) {
      if (!roiIsDrawing.value || !_drawContainer) return;
      const rect = _drawContainer.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const x = Math.min(_drawStart.x, cx);
      const y = Math.min(_drawStart.y, cy);
      const w = Math.abs(cx - _drawStart.x);
      const h = Math.abs(cy - _drawStart.y);
      roiDrawRect.value = { x, y, w, h };
    }

    function onROIMouseUp(e) {
      if (!roiIsDrawing.value || !_drawContainer) return;
      roiIsDrawing.value = false;

      const rect = _drawContainer.getBoundingClientRect();
      const cw = rect.width;
      const ch = rect.height;
      if (cw <= 0 || ch <= 0) { roiDrawRect.value = null; return; }

      const x0px = Math.min(_drawStart.x, e.clientX - rect.left);
      const x1px = Math.max(_drawStart.x, e.clientX - rect.left);
      const y0px = Math.min(_drawStart.y, e.clientY - rect.top);
      const y1px = Math.max(_drawStart.y, e.clientY - rect.top);

      // Clamp to container bounds
      const x0 = Math.max(0, Math.min(cw, x0px));
      const x1 = Math.max(0, Math.min(cw, x1px));
      const y0 = Math.max(0, Math.min(ch, y0px));
      const y1 = Math.max(0, Math.min(ch, y1px));

      // Ignore tiny draws (< 5px)
      if (x1 - x0 < 5 || y1 - y0 < 5) { roiDrawRect.value = null; return; }

      const dims = dimensions.value;
      if (!dims) { roiDrawRect.value = null; return; }
      const dw = dims[0]; const dh = dims[1]; const dd = dims[2] || 1;
      const maxD = Math.max(dw, dh, dd);
      const aspectX = dw / maxD;
      const aspectY = dh / maxD;

      const ctx3d = _drawContainer === containerOriginal.value
        ? context.value.original
        : context.value.decompressed;

      if (ctx3d && ctx3d.camera) {
        const vs = visualScale.value;

        // Forward-project the data plane's world-space corners into screen pixels.
        // From updateROIVisual: worldX = (pct/100)*aspectX*vs - aspectX/2*vs
        // So data (0%,0%)→world(-aspectX/2*vs, -aspectY/2*vs, 0)
        //    data (100%,100%)→world(+aspectX/2*vs, +aspectY/2*vs, 0)
        const projectToScreen = (wx, wy, wz) => {
          const v = new THREE.Vector3(wx, wy, wz);
          v.project(ctx3d.camera);           // mutates to NDC [-1, 1]
          return { x: (v.x + 1) / 2 * cw, y: (-v.y + 1) / 2 * ch };
        };

        const sc00 = projectToScreen(-aspectX / 2 * vs, -aspectY / 2 * vs, 0);
        const sc11 = projectToScreen(+aspectX / 2 * vs, +aspectY / 2 * vs, 0);

        const spanSX = sc11.x - sc00.x;  // positive: left→right  = 0%→100% X
        const spanSY = sc11.y - sc00.y;  // negative: top→bottom  = 100%→0% Y

        if (Math.abs(spanSX) < 1 || Math.abs(spanSY) < 1) {
          roiDrawRect.value = null; return;
        }

        const toPercX = (sx) => (sx - sc00.x) / spanSX * 100;
        const toPercY = (sy) => (sy - sc00.y) / spanSY * 100;

        roiXStart.value = Math.round(Math.max(0, Math.min(100, Math.min(toPercX(x0), toPercX(x1)))));
        roiXEnd.value   = Math.round(Math.max(0, Math.min(100, Math.max(toPercX(x0), toPercX(x1)))));
        roiYStart.value = Math.round(Math.max(0, Math.min(100, Math.min(toPercY(y0), toPercY(y1)))));
        roiYEnd.value   = Math.round(Math.max(0, Math.min(100, Math.max(toPercY(y0), toPercY(y1)))));

        // Z: symmetric around midpoint, width from roiZDepth slider
        const zHalf = Math.round(roiZDepth.value / 2);
        roiZStart.value = Math.max(0, 50 - zHalf);
        roiZEnd.value   = Math.min(100, 50 + zHalf);
      }

      // Clear the rubber-band after a short delay so user can see it snap
      setTimeout(() => { roiDrawRect.value = null; }, 150);
      _drawContainer = null;

      // Exit draw mode after one draw so user can then use TransformControls
      roiDrawMode.value = false;
    }

    // Attach global mousemove/mouseup when drawing
    watch(roiIsDrawing, (active) => {
      if (active) {
        window.addEventListener('mousemove', onROIMouseMove);
        window.addEventListener('mouseup', onROIMouseUp);
      } else {
        window.removeEventListener('mousemove', onROIMouseMove);
        window.removeEventListener('mouseup', onROIMouseUp);
      }
    });

    // When draw mode is activated, disable OrbitControls temporarily
    watch(roiDrawMode, (active) => {
      [context.value.original, context.value.decompressed].forEach(ctx => {
        if (ctx && ctx.controls) ctx.controls.enabled = !active;
      });
    });

    watch(roiEnabled, (enabled) => {
      if (!enabled) {
        roiDrawMode.value = false;
        roiDrawRect.value = null;
        roiApplied.value = false; // Restore full volume when ROI is disabled
      }
    });

    function updateROIVisual() {
      if (isTransformingROI.value) return;

      const orig = context.value.original;
      const decp = context.value.decompressed;

      // Hide ROI box if:
      // - ROI is not enabled
      // - No dimensions available
      // - ROI is applied (entire visible volume IS the ROI, box would be misleading)
      if (!roiEnabled.value || !dimensions.value || roiApplied.value) {
        [orig, decp].forEach(ctx => {
          if (ctx && ctx.roiGroup) {
            ctx.roiGroup.visible = false;
            if (ctx.transformControls) ctx.transformControls.detach();
            if (ctx.roiInteractiveMesh) {
              ctx.roiGroup.remove(ctx.roiInteractiveMesh);
              ctx.roiInteractiveMesh = null;
            }
          }
        });
        return;
      }

      const w = dimensions.value[0];
      const h = dimensions.value[1];
      const d = dimensions.value[2] || 1;
      const maxD = Math.max(w, h, d);
      const aspectX = w / maxD;
      const aspectY = h / maxD;
      const aspectZ = d / maxD;

      // Calculate box position based on ROI percentages
      const x0 = (Math.min(roiXStart.value, roiXEnd.value) / 100) * aspectX - aspectX / 2;
      const x1 = (Math.max(roiXStart.value, roiXEnd.value) / 100) * aspectX - aspectX / 2;
      const y0 = (Math.min(roiYStart.value, roiYEnd.value) / 100) * aspectY - aspectY / 2;
      const y1 = (Math.max(roiYStart.value, roiYEnd.value) / 100) * aspectY - aspectY / 2;
      const z0 = (Math.min(roiZStart.value, roiZEnd.value) / 100) * aspectZ - aspectZ / 2;
      const z1 = (Math.max(roiZStart.value, roiZEnd.value) / 100) * aspectZ - aspectZ / 2;

      const vs = visualScale.value;
      const cx = (x0 + x1) / 2 * vs;
      const cy = (y0 + y1) / 2 * vs;
      const cz = (z0 + z1) / 2 * vs;
      const sx = Math.abs(x1 - x0) * vs;
      const sy = Math.abs(y1 - y0) * vs;
      const sz = Math.max(0.001, Math.abs(z1 - z0)) * vs;

      const fillMaterial = new THREE.MeshBasicMaterial({ color: 0xff0000, transparent: true, opacity: 0.1, side: THREE.DoubleSide, depthTest: false });
      const lineMaterial = new THREE.LineBasicMaterial({ color: 0xff0000, linewidth: 2, depthTest: false });
      
      [orig, decp].forEach(ctx => {
          if (!ctx) return;
          ctx.roiGroup.clear();
          
          const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), fillMaterial);
          const lines = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)), lineMaterial);
          mesh.add(lines);
          
          mesh.position.set(cx, cy, cz);
          mesh.scale.set(sx, sy, sz);
          
          ctx.roiGroup.add(mesh);
          ctx.roiGroup.visible = true;
          ctx.roiInteractiveMesh = mesh;
          
          if (ctx.transformControls) {
            if ((leadContext.value === 'original' && ctx === orig) || (leadContext.value === 'decompressed' && ctx === decp)) {
              ctx.transformControls.setMode(roiMode.value);
              ctx.transformControls.attach(mesh);
            } else {
              ctx.transformControls.detach();
            }
          }
      });
    }

    // Update ROI box visual when ROI parameters change (preview mode)
    watch([roiEnabled, roiXStart, roiXEnd, roiYStart, roiYEnd, roiZStart, roiZEnd, visualScale, leadContext], () => {
      updateROIVisual();
    });

    // Refresh visualization and ROI box when ROI is applied/unapplied
    watch(roiApplied, () => {
      updateROIVisual(); // Show/hide ROI box
      if (isMounted.value) {
        refreshFromDatasetMetadata();
      }
    });

    watch(roiMode, (m) => {
        if (context.value.original?.transformControls) context.value.original.transformControls.setMode(m);
        if (context.value.decompressed?.transformControls) context.value.decompressed.transformControls.setMode(m);
    });

    function computeROIMetrics() {
      if (!fileData.value || !dimensions.value || !comparisonData.value) return;

      // Apply ROI cropping to visualization
      const wasApplied = roiApplied.value;
      roiApplied.value = true;

      // Force refresh if ROI bounds changed while already applied
      if (wasApplied && isMounted.value) {
        refreshFromDatasetMetadata();
      }

      const w = dimensions.value[0];
      const h = dimensions.value[1];
      const d = dimensions.value[2] || 1;
      const origData = toFloat32Data(fileData.value, precision.value, endianness.value);
      
      const xMin = Math.floor((Math.min(roiXStart.value, roiXEnd.value) / 100) * w);
      const xMax = Math.max(xMin + 1, Math.ceil((Math.max(roiXStart.value, roiXEnd.value) / 100) * w));
      const yMin = Math.floor((Math.min(roiYStart.value, roiYEnd.value) / 100) * h);
      const yMax = Math.max(yMin + 1, Math.ceil((Math.max(roiYStart.value, roiYEnd.value) / 100) * h));
      const zMin = Math.floor((Math.min(roiZStart.value, roiZEnd.value) / 100) * d);
      const zMax = Math.max(zMin + 1, Math.ceil((Math.max(roiZStart.value, roiZEnd.value) / 100) * d));
      
      const totalCount = (xMax - xMin) * (yMax - yMin) * (zMax - zMin);

      const payload = {};

      for (const [key, compConfig] of Object.entries(comparisonData.value)) {
        if (!compConfig.decp_data) continue;
        const decpData = toFloat32Data(compConfig.decp_data, compConfig.precision || decompressedPrecision.value, compConfig.endianness || decompressedEndianness.value);
        
        let mseOuter = 0, maxErr = 0, minVal = Infinity, maxVal = -Infinity;
        
        for (let z = zMin; z < zMax; z++) {
          for (let y = yMin; y < yMax; y++) {
            for (let x = xMin; x < xMax; x++) {
               const idx = z * (w * h) + y * w + x;
               const o = origData[idx];
               const dc = decpData[idx];
               
               if (o < minVal) minVal = o;
               if (o > maxVal) maxVal = o;
               
               const err = Math.abs(o - dc);
               if (err > maxErr) maxErr = err;
               mseOuter += err * err;
            }
          }
        }
        const mse = mseOuter / totalCount;
        const rmse = Math.sqrt(mse);
        let psnr = 0;
        if (rmse > 0) {
            const range = (store.state.dataset?.min_max?.[1] || maxVal) - (store.state.dataset?.min_max?.[0] || minVal);
            psnr = 20 * Math.log10(Math.abs(range) / rmse);
        } else {
            psnr = 100;
        }
        
        const localMetrics = {
          "error:psnr": psnr,
          "error:mse": mse,
          "error:rmse": rmse,
          "error:max_error": maxErr,
        };
        
        payload[key] = { ...compConfig, local_metrics: localMetrics };
      }
      
      store.commit('setComparisonData', payload);
      store.commit('setStatus', { type: 'success', message: 'Local ROI metrics computed. Check the Metrics & Analysis tab.'});
    }

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
    const decompressedViewMode = ref('data');
    const decompressedKeys = computed(() => comparisonData.value ? Object.keys(comparisonData.value) : []);
    const hasDecompressedData = computed(() => decompressedKeys.value.length > 0);
    
    watch(decompressedViewMode, () => {
      updateVisuals();
    });

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
    const decompressedPrecision = computed(() => (
      selectedDecompressedData.value?.dataset_meta?.precision ||
      selectedDecompressedData.value?.precision ||
      precision.value
    ));
    const decompressedEndianness = computed(() => (
      selectedDecompressedData.value?.dataset_meta?.endianness ||
      selectedDecompressedData.value?.endianness ||
      endianness.value
    ));
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
      uniform bool showBoundaries;
      
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
          
          if (showBoundaries && sampledColor.a > 0.1) {
              vec3 dx = vec3(0.5 / dimensions.x, 0.0, 0.0);
              vec3 dy = vec3(0.0, 0.5 / dimensions.y, 0.0);
              vec3 dz = vec3(0.0, 0.0, 0.5 / dimensions.z);
              
              float vR = texture(volume, p + dx).r;
              float vU = texture(volume, p + dy).r;
              float vF = texture(volume, p + dz).r;
              
              if (abs(rawVal - vR) > 0.01 || abs(rawVal - vU) > 0.01 || abs(rawVal - vF) > 0.01) {
                  color.rgb = vec3(1.0); // White boundary
                  color.a = 1.0;
                  break; 
              }
          }
          
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

    function createCategoricalTransferFunctionTexture(modeField, range, highlightMode, otherModeField, explicitTopLabels) {
      let topLabels = new Set();
      const highlight = highlightMode !== 'none';

      if (explicitTopLabels) {
        // Caller pre-computed the highlight set (used for most_diff on the decompressed panel
        // so both panels show the same canonical original-segment IDs).
        topLabels = explicitTopLabels;
      } else if (highlightMode === 'top5' || highlightMode === 'top10' || highlightMode === 'top20') {
        const counts = new Map();
        for (let i = 0; i < modeField.length; i++) {
          const v = Math.round(modeField[i]);
          if (v < 0) continue; // skip sentinel / invalid values
          counts.set(v, (counts.get(v) || 0) + 1);
        }
        const sortedLabels = Array.from(counts.keys()).sort((a, b) => counts.get(b) - counts.get(a));
        const limit = highlightMode === 'top5' ? 5 : (highlightMode === 'top10' ? 10 : 20);
        topLabels = new Set(sortedLabels.slice(0, limit));
      } else if (highlightMode === 'most_diff' && otherModeField && otherModeField.length === modeField.length) {
        // Count how many voxels of each label in modeField were misclassified (label differs
        // from otherModeField). For the original panel modeField IS the original, so we get
        // "original segments with the most corrupted voxels". For the decompressed panel we
        // override via explicitTopLabels (pre-computed from the original) so both panels are
        // consistent — handled by the caller (updateSegmentationThreePanels).
        const diffCounts = new Map();
        for (let i = 0; i < modeField.length; i++) {
          const v = Math.round(modeField[i]);
          const other = Math.round(otherModeField[i]);
          if (v < 0) continue; // skip sentinel / invalid values
          if (v !== other) {
            diffCounts.set(v, (diffCounts.get(v) || 0) + 1);
          }
        }
        const sortedDiffs = Array.from(diffCounts.keys()).sort((a, b) => diffCounts.get(b) - diffCounts.get(a));
        topLabels = new Set(sortedDiffs.slice(0, 10));
      }

      // Give each integer label ID its own exact texel so NearestFilter sampling
      // on the GPU never aliases one segment ID to an adjacent label's color/highlight.
      // Cap at 16384 (max WebGL texture width on nearly all hardware).
      const labelRange = Math.ceil(range[1]) - Math.floor(range[0]);
      const width = Math.max(2, Math.min(16384, labelRange + 1));
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = 1;
      const ctx = canvas.getContext('2d');
      const imgData = ctx.createImageData(width, 1);

      function hslToRgb(h, s, l) {
        h /= 360; s /= 100; l /= 100;
        let r, g, b;
        if(s === 0){
            r = g = b = l; 
        } else {
            const hue2rgb = (p, q, t) => {
                if(t < 0) t += 1;
                if(t > 1) t -= 1;
                if(t < 1/6) return p + (q - p) * 6 * t;
                if(t < 1/2) return q;
                if(t < 2/3) return p + (q - p) * (2/3 - t) * 6;
                return p;
            }
            const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            const p = 2 * l - q;
            r = hue2rgb(p, q, h + 1/3);
            g = hue2rgb(p, q, h);
            b = hue2rgb(p, q, h - 1/3);
        }
        return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
      }

      const hashLabel = (label) => {
        let h = Math.imul(label ^ 0x1a3f5c, 0x5bd1e995);
        h ^= h >>> 13;
        h = Math.imul(h, 0x5bd1e995);
        h ^= h >>> 15;
        const hue = Math.abs(h % 360);
        const sat = 60 + (Math.abs(h >> 8) % 40);
        const light = 40 + (Math.abs(h >> 16) % 30);
        return hslToRgb(hue, sat, light);
      };

      for (let x = 0; x < width; x++) {
        const t = x / (width - 1);
        const label = Math.round(range[0] + t * (range[1] - range[0]));
        
        let r, g, b, a;
        if (highlight && topLabels.has(label)) {
          const rgb = hashLabel(label);
          r = Math.min(255, rgb[0] * 1.5);
          g = Math.min(255, rgb[1] * 1.5);
          b = Math.min(255, rgb[2] * 1.5);
          a = 255;
        } else if (highlight && !topLabels.has(label)) {
          const rgb = hashLabel(label);
          const gray = (rgb[0] + rgb[1] + rgb[2]) / 3;
          r = gray * 0.4;
          g = gray * 0.4;
          b = gray * 0.4;
          a = 60; // Semi transparent
        } else {
          const rgb = hashLabel(label);
          r = rgb[0];
          g = rgb[1];
          b = rgb[2];
          a = 255;
        }

        const idx = x * 4;
        imgData.data[idx] = r;
        imgData.data[idx + 1] = g;
        imgData.data[idx + 2] = b;
        imgData.data[idx + 3] = a;
      }

      ctx.putImageData(imgData, 0, 0);
      const texture = new THREE.CanvasTexture(canvas);
      texture.minFilter = THREE.NearestFilter; 
      texture.magFilter = THREE.NearestFilter;
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

      // Set initial background color
      const colorMap = {
        'transparent': { color: 0x000000, alpha: 0 },
        'white': { color: 0xffffff, alpha: 1 },
        'dark': { color: 0x343a40, alpha: 1 },
        'black': { color: 0x000000, alpha: 1 }
      };
      const bgSetting = colorMap[rendererBgColor.value] || colorMap['dark'];
      renderer.setClearColor(bgSetting.color, bgSetting.alpha);

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

      const transformControls = new TransformControls(camera, renderer.domElement);
      transformControls.addEventListener('dragging-changed', (event) => {
        controls.enabled = !event.value;
      });

      transformControls.addEventListener('change', () => {
        if (!roiEnabled.value || !dimensions.value) return;
        const attachedMesh = transformControls.object;
        if (!attachedMesh) return;
        
        isTransformingROI.value = true;
        
        const w = dimensions.value[0];
        const h = dimensions.value[1];
        const d = dimensions.value[2] || 1;
        const maxD = Math.max(w, h, d);
        const aspectX = w / maxD;
        const aspectY = h / maxD;
        const aspectZ = d / maxD;

        const vs = visualScale.value;
        const posX = attachedMesh.position.x / vs;
        const posY = attachedMesh.position.y / vs;
        const posZ = attachedMesh.position.z / vs;
        const scaleX = attachedMesh.scale.x / vs;
        const scaleY = attachedMesh.scale.y / vs;
        const scaleZ = attachedMesh.scale.z / vs;

        const x0 = posX - scaleX / 2;
        const x1 = posX + scaleX / 2;
        const y0 = posY - scaleY / 2;
        const y1 = posY + scaleY / 2;
        const z0 = posZ - scaleZ / 2;
        const z1 = posZ + scaleZ / 2;
        
        let nx0 = ((x0 + aspectX / 2) / aspectX) * 100;
        let nx1 = ((x1 + aspectX / 2) / aspectX) * 100;
        let ny0 = ((y0 + aspectY / 2) / aspectY) * 100;
        let ny1 = ((y1 + aspectY / 2) / aspectY) * 100;
        let nz0 = ((z0 + aspectZ / 2) / aspectZ) * 100;
        let nz1 = ((z1 + aspectZ / 2) / aspectZ) * 100;
        
        roiXStart.value = Math.round(Math.max(0, Math.min(100, Math.min(nx0, nx1))));
        roiXEnd.value = Math.round(Math.max(0, Math.min(100, Math.max(nx0, nx1))));
        roiYStart.value = Math.round(Math.max(0, Math.min(100, Math.min(ny0, ny1))));
        roiYEnd.value = Math.round(Math.max(0, Math.min(100, Math.max(ny0, ny1))));
        roiZStart.value = Math.round(Math.max(0, Math.min(100, Math.min(nz0, nz1))));
        roiZEnd.value = Math.round(Math.max(0, Math.min(100, Math.max(nz0, nz1))));
        
        setTimeout(() => { isTransformingROI.value = false; }, 10);
      });

      scene.add(transformControls);

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
        transformControls: markRaw(transformControls),
        resizeObserver,
        volumeMesh: null,
        sliceMesh: null,
        roiInteractiveMesh: null,
        cpGroup: markRaw(new THREE.Group()),
        roiGroup: markRaw(new THREE.Group()),
        transferTexture: markRaw(createTransferFunctionTexture(colormap.value)),
        transferTextureOpaque: markRaw(createTransferFunctionTexture(colormap.value, { opaque: true })),
        cachedData: null,
        cachedRange: [0, 1],
      });
      scene.add(ctx.cpGroup);
      scene.add(ctx.roiGroup);

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

    function toFloat32Data(content, precisionHint, endianness = 'little') {
      if (!content) return null;
      if (content instanceof Float32Array) return content;
      if (content instanceof Float64Array) return new Float32Array(content);
      if (ArrayBuffer.isView(content)) {
        const view = content;
        const ctorName = view.constructor?.name || '';
        if (ctorName === 'Float64Array') return new Float32Array(view);
        if (ctorName === 'Int8Array' || ctorName === 'Int16Array' || ctorName === 'Int32Array') {
          return new Float32Array(view);
        }
        if (ctorName === 'Uint8Array' || ctorName === 'Uint16Array' || ctorName === 'Uint32Array') {
          return new Float32Array(view);
        }
        return new Float32Array(view.buffer.slice(view.byteOffset, view.byteOffset + view.byteLength));
      }
      if (!(content instanceof ArrayBuffer)) return null;
      const swapIfNeeded = (buffer, bytesPerElement) => {
        if (!buffer || bytesPerElement === 1 || endianness !== 'big') return buffer;
        const src = new Uint8Array(buffer);
        const out = new Uint8Array(src.length);
        for (let i = 0; i < src.length; i += bytesPerElement) {
          for (let j = 0; j < bytesPerElement; j += 1) {
            out[i + j] = src[i + bytesPerElement - 1 - j];
          }
        }
        return out.buffer;
      };
      const prec = (precisionHint || '').toLowerCase();
      const isDouble = prec === 'd' || prec === 'double' || prec === 'float64' || prec === 'f64';
      const isInt8 = prec === 'i8' || prec === 'int8';
      const isUInt8 = prec === 'u8' || prec === 'uint8';
      const isInt16 = prec === 'i16' || prec === 'int16';
      const isUInt16 = prec === 'u16' || prec === 'uint16';
      const isInt32 = prec === 'i32' || prec === 'int32';
      const isUInt32 = prec === 'u32' || prec === 'uint32';
      let rawArray;
      if (isDouble) rawArray = new Float64Array(swapIfNeeded(content, 8));
      else if (isInt8) rawArray = new Int8Array(content);
      else if (isUInt8) rawArray = new Uint8Array(content);
      else if (isInt16) rawArray = new Int16Array(swapIfNeeded(content, 2));
      else if (isUInt16) rawArray = new Uint16Array(swapIfNeeded(content, 2));
      else if (isInt32) rawArray = new Int32Array(swapIfNeeded(content, 4));
      else if (isUInt32) rawArray = new Uint32Array(swapIfNeeded(content, 4));
      else rawArray = new Float32Array(swapIfNeeded(content, 4));
      return new Float32Array(rawArray);
    }

    function normalizeDimensionsForData(data, dims) {
      if (!data || !Array.isArray(dims) || dims.length < 2) return dims;
      const width = Number(dims[0]);
      const height = Number(dims[1]);
      const depth = Number(dims[2] ?? 1);
      if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return dims;

      const expected = width * height * Math.max(1, depth);
      if (data.length === expected) return [width, height, depth];

      // Try to recover from common dimension mismatches by inferring from data length.
      if (depth <= 1) {
        if (data.length % width === 0) {
          const inferredH = data.length / width;
          if (inferredH !== height) {
            console.warn(`[Three] Dimension mismatch: expected ${expected}, got ${data.length}. Inferred height=${inferredH}.`);
            return [width, inferredH, 1];
          }
        }
        if (data.length % height === 0) {
          const inferredW = data.length / height;
          if (inferredW !== width) {
            console.warn(`[Three] Dimension mismatch: expected ${expected}, got ${data.length}. Inferred width=${inferredW}.`);
            return [inferredW, height, 1];
          }
        }
      }
      console.warn(`[Three] Dimension mismatch: expected ${expected}, got ${data.length}. Using provided dims.`);
      return [width, height, depth];
    }

    // Extract ROI region from volume data
    function extractROIData(data, dims) {
      if (!dims) return { data, dims };

      const w = dims[0];
      const h = dims[1];
      const d = dims[2] || 1;

      const xMin = Math.floor((Math.min(roiXStart.value, roiXEnd.value) / 100) * w);
      const xMax = Math.max(xMin + 1, Math.ceil((Math.max(roiXStart.value, roiXEnd.value) / 100) * w));
      const yMin = Math.floor((Math.min(roiYStart.value, roiYEnd.value) / 100) * h);
      const yMax = Math.max(yMin + 1, Math.ceil((Math.max(roiYStart.value, roiYEnd.value) / 100) * h));
      const zMin = Math.floor((Math.min(roiZStart.value, roiZEnd.value) / 100) * d);
      const zMax = Math.max(zMin + 1, Math.ceil((Math.max(roiZStart.value, roiZEnd.value) / 100) * d));

      const roiW = xMax - xMin;
      const roiH = yMax - yMin;
      const roiD = zMax - zMin;
      const roiData = new Float32Array(roiW * roiH * roiD);

      let idx = 0;
      for (let z = zMin; z < zMax; z++) {
        for (let y = yMin; y < yMax; y++) {
          for (let x = xMin; x < xMax; x++) {
            const srcIdx = z * (w * h) + y * w + x;
            roiData[idx++] = data[srcIdx];
          }
        }
      }

      return { data: roiData, dims: [roiW, roiH, roiD] };
    }

    function updateVisualization(ctx, content, dims, precision, isOriginal, options = {}) {
      if (!ctx || !content || !dims || dims[0] <= 0 || dims[1] <= 0) return;
      const { scene } = ctx;
      if (ctx.volumeMesh) scene.remove(ctx.volumeMesh);
      if (ctx.sliceMesh) scene.remove(ctx.sliceMesh);

      let data = toFloat32Data(content, precision, options.endianness);
      if (!data) return;
      ctx.cachedData = data;
      let normalizedDims = normalizeDimensionsForData(data, dims);

      // Apply ROI cropping if applied (not just enabled for preview)
      if (roiApplied.value && !options.skipROI) {
        const roiResult = extractROIData(data, normalizedDims);
        data = roiResult.data;
        normalizedDims = roiResult.dims;
      }
      if (!normalizedDims || normalizedDims[0] <= 0 || normalizedDims[1] <= 0) return;
      
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

      const is2D = !normalizedDims[2] || normalizedDims[2] <= 1 || isTimeVarying.value;
      
      // Determine actual range to use
      const forcedRange = options?.forcedRange;
      const transferOverride = options?.transferTexture || null;
      const opacityOverride = options?.opacityMultiplier;
      let displayRange = forcedRange ? [forcedRange[0], forcedRange[1]] : [...ctx.cachedRange];
      if (!forcedRange) {
        if (rescaleMethod.value === 'local' && is2D) {
          displayRange = getLocalRange(data, normalizedDims, sliceId.value);
        } else if (rescaleMethod.value === 'custom') {
          displayRange = [customMin.value, customMax.value];
        }
      }
      
      if (isOriginal) currentRangeOriginal.value = displayRange;
      else currentRangeDecompressed.value = displayRange;

      if (is2D) {
        const sliceSize = normalizedDims[0] * normalizedDims[1];
        const sliceData = data.slice(sliceId.value * sliceSize, (sliceId.value + 1) * sliceSize);
        const texture = new THREE.DataTexture(sliceData, normalizedDims[0], normalizedDims[1], THREE.RedFormat, THREE.FloatType);
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.unpackAlignment = 1;
        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.generateMipmaps = false;
        texture.needsUpdate = true;

        const maxDim = Math.max(normalizedDims[0], normalizedDims[1]);
        const aspectX = normalizedDims[0] / maxDim;
        const aspectY = normalizedDims[1] / maxDim;
        const geometry = new THREE.PlaneGeometry(aspectX, aspectY);
        const material = new THREE.ShaderMaterial({
          uniforms: {
            tex: { value: texture },
            transferFunction: { value: transferOverride || ctx.transferTexture },
            dataRange: { value: new THREE.Vector2(displayRange[0], displayRange[1]) },
            texSize: { value: new THREE.Vector2(normalizedDims[0], normalizedDims[1]) },
            showBoundaries: { value: segmentationMode.value !== 'none' && showBoundaryLines.value }
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
            uniform vec2 texSize;
            uniform bool showBoundaries;
            in vec2 vUv;
            out vec4 outColor;
            void main() {
              vec2 uv = (vUv * (texSize - 1.0) + 0.5) / texSize;
              uv = clamp(uv, vec2(0.0), vec2(1.0));
              float val = texture(tex, uv).r;
              
              float edge = 0.0;
              if (showBoundaries) {
                vec2 pixel = 0.5 / texSize; // Reduced width check
                float vR = texture(tex, uv + vec2(pixel.x, 0.0)).r;
                float vU = texture(tex, uv + vec2(0.0, pixel.y)).r;
                if (abs(val - vR) > 0.01 || abs(val - vU) > 0.01) {
                  edge = 1.0;
                }
              }

              float norm = clamp((val - dataRange.x) / (dataRange.y - dataRange.x + 1e-10), 0.0, 1.0);
              vec4 sampledColor = texture(transferFunction, vec2(norm, 0.5));
              
              if (edge > 0.5) {
                outColor = vec4(1.0, 1.0, 1.0, 1.0); // White
              } else {
                outColor = sampledColor;
              }
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
        const texture = new THREE.Data3DTexture(data, normalizedDims[0], normalizedDims[1], normalizedDims[2]);
        texture.format = THREE.RedFormat;
        texture.type = THREE.FloatType;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.unpackAlignment = 1;
        texture.needsUpdate = true;

        const maxDim = Math.max(normalizedDims[0], normalizedDims[1], normalizedDims[2] || 0);
        const aspectX = normalizedDims[0] / maxDim;
        const aspectY = normalizedDims[1] / maxDim;
        const aspectZ = (normalizedDims[2] || 0) / maxDim;
        const geometry = new THREE.BoxGeometry(aspectX, aspectY, aspectZ);
        const material = new THREE.ShaderMaterial({
          uniforms: {
            volume: { value: texture },
            transferFunction: { value: transferOverride || ctx.transferTexture },
            inverseModelMatrix: { value: new THREE.Matrix4() }, // Will be updated
            dimensions: { value: new THREE.Vector3(normalizedDims[0], normalizedDims[1], normalizedDims[2]) },
            stepSize: { value: 1.5 / Math.max(normalizedDims[0], Math.max(normalizedDims[1], normalizedDims[2])) }, // Increased step size slightly (faster)
            opacityMultiplier: { value: typeof opacityOverride === 'number' ? opacityOverride : 1.0 },
            dataRange: { value: new THREE.Vector2(displayRange[0], displayRange[1]) },
            showBoundaries: { value: segmentationMode.value !== 'none' && showBoundaryLines.value }
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

    function updateSegmentationVisualization(ctx, sourceSeg, isOriginal, otherSeg, options = {}) {
      if (!ctx || !sourceSeg || segmentationMode.value === 'none') return;
      const modeField = normalizeSegmentationField(sourceSeg[segmentationMode.value]);
      const otherModeField = otherSeg ? normalizeSegmentationField(otherSeg[segmentationMode.value]) : null;

      const dimsObj = sourceSeg.dimensions || {};
      const width = Number(dimsObj.width || dimensions.value?.[0] || 0);
      const height = Number(dimsObj.height || dimensions.value?.[1] || 0);
      const depth = Number(dimsObj.depth || dimensions.value?.[2] || 1);
      if (!modeField || !width || !height || !depth) return;
      const range = inferLabelRange(sourceSeg);
      let transferTexture = createCategoricalTransferFunctionTexture(modeField, range, highlightRegionMode.value, otherModeField, options?.explicitTopLabels);

      updateVisualization(
        ctx,
        modeField,
        [width, height, depth],
        'float32',
        isOriginal,
        {
          forcedRange: range,
          transferTexture: transferTexture,
          opacityMultiplier: 1.0
        }
      );
    }

    function updateSegmentationThreePanels() {
      if (segmentationMode.value === 'none') return;
      const seg = segmentation.value;
      if (!seg) return;

      const origSeg = seg.original;
      const decSeg = selectedCompressor.value ? seg.decompressed?.[selectedCompressor.value] : null;

      // For 'most_diff', we compute two separate perspectives:
      // 1. Original view: Which original segment IDs had the most voxels misclassified? (regions destroyed)
      // 2. Decompressed view: Which decompressed segment IDs contain the most misclassified voxels? (corrupted/fake regions)
      let origDiffTopLabels = null;
      let decDiffTopLabels = null;
      
      if (highlightRegionMode.value === 'most_diff' && origSeg && decSeg) {
        const origField = normalizeSegmentationField(origSeg[segmentationMode.value]);
        const decField  = normalizeSegmentationField(decSeg[segmentationMode.value]);
        
        if (origField && decField && origField.length === decField.length) {
          const origCounts = new Map();
          const decCounts = new Map();
          
          for (let i = 0; i < origField.length; i++) {
            const o = Math.round(origField[i]);
            const d = Math.round(decField[i]);
            
            if (o < 0 || d < 0) continue; // Skip invalid
            
            if (o !== d) {
              origCounts.set(o, (origCounts.get(o) || 0) + 1);
              decCounts.set(d, (decCounts.get(d) || 0) + 1);
            }
          }
          
          const sortedOrig = Array.from(origCounts.keys()).sort((a, b) => origCounts.get(b) - origCounts.get(a));
          const sortedDec = Array.from(decCounts.keys()).sort((a, b) => decCounts.get(b) - decCounts.get(a));
          
          origDiffTopLabels = new Set(sortedOrig.slice(0, 10));
          decDiffTopLabels = new Set(sortedDec.slice(0, 10));
        }
      }

      if (context.value.original && origSeg) {
        updateSegmentationVisualization(context.value.original, origSeg, true, decSeg, { explicitTopLabels: origDiffTopLabels });
      }
      if (context.value.decompressed && decSeg) {
        updateSegmentationVisualization(context.value.decompressed, decSeg, false, origSeg, { explicitTopLabels: decDiffTopLabels });
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
      
      const filterFalse = (pointObj, type) => {
        if (!pointObj || !pointObj.points) return [];
        const isFlat = pointObj.format === 'flat';
        const points = pointObj.points;
        
        if (criticalPointsDisplay.value !== 'false_points' || isOriginal || !originalCP) {
           return pointObj; // Return the whole object
        }
        
        // Compute original set for filtering
        const origObj = originalCP[type];
        if (!origObj || !origObj.points) return pointObj;
        
        const origPts = origObj.points;
        const isOrigFlat = origObj.format === 'flat';
        const origSet = new Set();
        
        if (isOrigFlat) {
          for (let i = 0; i < origPts.length; i += 4) {
            origSet.add(`${origPts[i]},${origPts[i+1]},${origPts[i+2]}`);
          }
        } else {
          origPts.forEach(p => origSet.add(`${p.x},${p.y},${p.z}`));
        }
        
        if (isFlat) {
          const filtered = [];
          for (let i = 0; i < points.length; i += 4) {
             const key = `${points[i]},${points[i+1]},${points[i+2]}`;
             if (!origSet.has(key)) {
                filtered.push(points[i], points[i+1], points[i+2], points[i+3]);
             }
          }
          return { ...pointObj, points: filtered };
        } else {
          const filtered = points.filter(p => !origSet.has(`${p.x},${p.y},${p.z}`));
          return { ...pointObj, points: filtered };
        }
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

      const radius = (1.0 / 120) * criticalPointsScale.value;
      const sphereGeom = new THREE.SphereGeometry(radius, 8, 8);

      const addPoints = (pointObj, colorHex) => {
        if (!pointObj || !pointObj.points) return;
        const isFlat = pointObj.format === 'flat';
        const pts = pointObj.points;
        const count = isFlat ? pts.length / 4 : pts.length;
        if (count === 0) return;

        // Performance threshold for point cloud vs instanced spheres
        const usePoints = count > 20000;
        
        if (usePoints) {
           const geometry = new THREE.BufferGeometry();
           const positions = new Float32Array(count * 3);
           
           for (let i = 0; i < count; i++) {
             let px, py, pz;
             if (isFlat) {
               px = pts[i * 4];
               py = pts[i * 4 + 1];
               pz = pts[i * 4 + 2];
             } else {
               const p = pts[i];
               px = p.x; py = p.y; pz = p.z ?? 0;
             }
             
             const vx = Math.max(-aspectX/2, Math.min(aspectX/2, (px / maxD) - aspectX/2));
             const vy = Math.max(-aspectY/2, Math.min(aspectY/2, (py / maxD) - aspectY/2));
             
             if (is2D) {
               if (Math.abs(pz - Number(sliceId.value)) > 0.5) {
                 positions[i*3] = 0; positions[i*3+1] = 0; positions[i*3+2] = -100; // Hide
               } else {
                 positions[i*3] = vx; positions[i*3+1] = vy; positions[i*3+2] = 0.01;
               }
             } else {
               const vz = Math.max(-aspectZ/2, Math.min(aspectZ/2, (pz / maxD) - aspectZ/2));
               positions[i*3] = vx; positions[i*3+1] = vy; positions[i*3+2] = vz;
             }
           }
           
           geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
           const material = new THREE.PointsMaterial({ 
             color: colorHex, 
             size: criticalPointsScale.value * 3, // Point size in pixels
             sizeAttenuation: false 
           });
           const cloud = new THREE.Points(geometry, material);
           ctx.cpGroup.add(cloud);
        } else {
           const material = new THREE.MeshPhongMaterial({ 
             color: colorHex, 
             shininess: 80 
           });
           const mesh = new THREE.InstancedMesh(sphereGeom, material, count);
           mesh.renderOrder = 10;
           const matrix = new THREE.Matrix4();
           
           for (let i = 0; i < count; i++) {
             let px, py, pz;
             if (isFlat) {
               px = pts[i * 4]; py = pts[i * 4 + 1]; pz = pts[i * 4 + 2];
             } else {
               const p = pts[i];
               px = p.x; py = p.y; pz = p.z ?? 0;
             }
             
             const vx = Math.max(-aspectX/2, Math.min(aspectX/2, (px / maxD) - aspectX/2));
             const vy = Math.max(-aspectY/2, Math.min(aspectY/2, (py / maxD) - aspectY/2));
             
             if (is2D) {
               if (Math.abs(pz - Number(sliceId.value)) > 0.5) {
                 matrix.makeScale(0, 0, 0);
               } else {
                 matrix.makeTranslation(vx, vy, 0.01);
               }
             } else {
               const vz = Math.max(-aspectZ/2, Math.min(aspectZ/2, (pz / maxD) - aspectZ/2));
               matrix.makeTranslation(vx, vy, vz);
             }
             mesh.setMatrixAt(i, matrix);
           }
           mesh.instanceMatrix.needsUpdate = true;
           ctx.cpGroup.add(mesh);
        }
      };

      // Simplified lighting: Directional + Ambient is usually enough for Phong
      const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
      dirLight.position.set(2, 2, 5);
      ctx.cpGroup.add(dirLight);
      
      ctx.cpGroup.add(new THREE.AmbientLight(0xaaaaaa));

      if (['minima', 'all', 'false_points'].includes(criticalPointsDisplay.value)) addPoints(filterFalse(cpData.minima, 'minima'), minimaColor.value);
      if (['maxima', 'all', 'false_points'].includes(criticalPointsDisplay.value)) addPoints(filterFalse(cpData.maxima, 'maxima'), maximaColor.value);
      if (['saddles', 'all', 'false_points'].includes(criticalPointsDisplay.value)) addPoints(filterFalse(cpData.saddles, 'saddles'), saddleColor.value);
      
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
        updateVisualization(
          context.value.original,
          fileData.value,
          dimensions.value,
          precision.value,
          true,
          { endianness: endianness.value }
        );
      }
      if (context.value.decompressed && selectedDecompressedData.value) {
        let decpData = selectedDecompressedData.value.decp_data;
        let decpPrec = decompressedPrecision.value;
        let decpEnd = decompressedEndianness.value;
        
        if (decompressedViewMode.value === 'error') {
          const oData = toFloat32Data(fileData.value, precision.value, endianness.value);
          const dData = toFloat32Data(decpData, decpPrec, decpEnd);
          if (oData && dData && oData.length === dData.length) {
            const err = new Float32Array(oData.length);
            for(let i = 0; i < oData.length; i++) {
              err[i] = Math.abs(oData[i] - dData[i]);
            }
            decpData = err;
            decpPrec = 'float32';
          }
        }

        updateVisualization(
          context.value.decompressed,
          decpData,
          dimensions.value,
          decpPrec,
          false,
          { endianness: decpEnd }
        );
      }
      refreshColorBars();
    }

    function refreshFromDatasetMetadata() {
      if (!isMounted.value) return;
      if (segmentationMode.value !== 'none') {
        updateSegmentationThreePanels();
        return;
      }
      if (context.value.original && fileData.value) {
        updateVisualization(
          context.value.original,
          fileData.value,
          dimensions.value,
          precision.value,
          true,
          { endianness: endianness.value }
        );
      }
      if (context.value.decompressed && selectedDecompressedData.value) {
        let decpData = selectedDecompressedData.value.decp_data;
        let decpPrec = decompressedPrecision.value;
        let decpEnd = decompressedEndianness.value;
        
        if (decompressedViewMode.value === 'error') {
          const oData = toFloat32Data(fileData.value, precision.value, endianness.value);
          const dData = toFloat32Data(decpData, decpPrec, decpEnd);
          if (oData && dData && oData.length === dData.length) {
            const err = new Float32Array(oData.length);
            for(let i = 0; i < oData.length; i++) {
              err[i] = Math.abs(oData[i] - dData[i]);
            }
            decpData = err;
            decpPrec = 'float32';
          }
        }

        updateVisualization(
          context.value.decompressed,
          decpData,
          dimensions.value,
          decpPrec,
          false,
          { endianness: decpEnd }
        );
      }
      nextTick(() => {
        // Camera position is preserved - only refresh color bars
        refreshColorBars();
      });
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
            updateVisualization(
              context.value.original,
              fileData.value,
              dimensions.value,
              precision.value,
              true,
              { endianness: endianness.value }
            );
            nextTick(() => {
              refreshColorBars();
            });
          }
        }
        
        if (selectedDecompressedData.value && containerDecompressed.value) {
          context.value.decompressed = setupThree(containerDecompressed.value);
              updateVisualization(
                context.value.decompressed,
                selectedDecompressedData.value.decp_data,
                dimensions.value,
                decompressedPrecision.value,
                false,
                { endianness: decompressedEndianness.value }
              );
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
          updateVisualization(
            context.value.original,
            val,
            dimensions.value,
            precision.value,
            true,
            { endianness: endianness.value }
          );
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
              // Only fit camera for first-time setup
              if (context.value.original) fitCameraToView(context.value.original);
              if (context.value.decompressed) fitCameraToView(context.value.decompressed);
            }
            updateSegmentationThreePanels();
          });
          return;
        }

        // Prepare data based on view mode (data vs error)
        let decpData = val.decp_data;
        let decpPrec = decompressedPrecision.value;
        let decpEnd = decompressedEndianness.value;

        if (decompressedViewMode.value === 'error') {
          const oData = toFloat32Data(fileData.value, precision.value, endianness.value);
          const dData = toFloat32Data(decpData, decpPrec, decpEnd);
          if (oData && dData && oData.length === dData.length) {
            const err = new Float32Array(oData.length);
            for(let i = 0; i < oData.length; i++) {
              err[i] = Math.abs(oData[i] - dData[i]);
            }
            decpData = err;
            decpPrec = 'float32';
          }
        }

        if (!context.value.decompressed) {
          nextTick(() => {
            if (containerDecompressed.value) {
              context.value.decompressed = setupThree(containerDecompressed.value);
              updateVisualization(
                context.value.decompressed,
                decpData,
                dimensions.value,
                decpPrec,
                false,
                { endianness: decpEnd }
              );
              nextTick(() => {
                refreshColorBars();
              });

              // Rescale both to fit the new side-by-side layout (first-time setup only)
              fitCameraToView(context.value.original);
              fitCameraToView(context.value.decompressed);
            }
          });
        } else {
          updateVisualization(
            context.value.decompressed,
            decpData,
            dimensions.value,
            decpPrec,
            false,
            { endianness: decpEnd }
          );
          // Preserve camera position when switching data sources
          nextTick(() => {
            refreshColorBars();
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
    watch([dimensions, precision, endianness, isTimeVarying], refreshFromDatasetMetadata, { deep: true });
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

    watch([criticalPointsDisplay, minimaColor, maximaColor, saddleColor, criticalPointsScale, showBoundaryLines], () => {
      if (context.value.original) renderCriticalPoints(context.value.original);
      if (context.value.decompressed) renderCriticalPoints(context.value.decompressed);
      updateVisuals();
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
        // Preserve camera position when changing layout
        // Only update scalar bars
        refreshColorBars();
      });
    });

    // When the color bar overlay is toggled back ON, the v-if re-creates fresh
    // blank <canvas> elements. We must re-paint them after Vue has mounted them.
    watch(showColorBarOverlay, (visible) => {
      if (visible) {
        nextTick(() => refreshColorBars());
      }
    });

    async function saveScreenshot(which) {
      const el = which === 'original' ? containerOriginal.value?.parentElement : containerDecompressed.value?.parentElement;
      if (!el) return;

      try {
        const canvas = await html2canvas(el, {
          backgroundColor: '#343a40',
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

    function resetROI() {
      roiXStart.value = 20;
      roiXEnd.value = 80;
      roiYStart.value = 20;
      roiYEnd.value = 80;
      roiZStart.value = 20;
      roiZEnd.value = 80;
      roiApplied.value = false; // Clear applied ROI and show full volume
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
      decompressedViewMode,
      highlightRegionMode,
      showColorBarOverlay,
      rendererBgColor,
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
      roiEnabled,
      roiApplied,
      roiMode,
      roiXStart,
      roiXEnd,
      roiYStart,
      roiYEnd,
      roiZStart,
      roiZEnd,
      roiDrawMode,
      roiIsDrawing,
      roiDrawRect,
      roiZDepth,
      onROIMouseDown,
      computeROIMetrics,
      resetROI,
      startDrag,
      fileData,
      segmentationLabel,
      saveScreenshot,
      saveData,
      showBoundaryLines,
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

        <!-- Background Color -->
        <div class="d-flex align-items-center me-2">
          <label class="me-2 mb-0 fw-semibold text-secondary small">
            <i class="bi bi-image me-1"></i>Background:
          </label>
          <select
            class="form-select form-select-sm"
            v-model="rendererBgColor"
            style="min-width: 110px;"
            title="Background color for 3D visualization"
          >
            <option value="transparent">Transparent</option>
            <option value="white">White</option>
            <option value="dark">Dark</option>
            <option value="black">Black</option>
          </select>
        </div>

        <button
          :class="['btn btn-sm d-flex align-items-center', sameCamera ? 'btn-primary' : 'btn-outline-primary']"
          @click="sameCamera = !sameCamera"
          title="Synchronize camera views"
        >
          <i class="bi bi-camera me-1"></i>Sync Camera
        </button>

        <button
          class="btn btn-sm btn-outline-secondary d-flex align-items-center"
          @click="refreshFromDatasetMetadata"
          title="Refresh visualization"
        >
          <i class="bi bi-arrow-clockwise me-1"></i>Refresh
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
          <i class="bi bi-box me-1"></i>Decompressed View:
        </label>
        <select
          v-model="decompressedViewMode"
          class="form-select form-select-sm me-2"
          style="width: 130px;"
        >
          <option value="data">Data</option>
          <option value="error">Error Map</option>
        </select>
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

      <!-- ROI Selection -->
      <div v-if="hasDecompressedData" class="d-flex flex-wrap align-items-center justify-content-center gap-2 w-100 mt-2 border-top pt-2 px-3">
        <label class="me-2 mb-0 fw-semibold text-secondary small">
          <i class="bi bi-bounding-box me-1"></i>ROI:
        </label>
        <!-- Enable toggle -->
        <div class="form-check form-switch ms-1 mb-0 d-flex align-items-center">
          <input class="form-check-input" type="checkbox" id="roiToggle" v-model="roiEnabled">
          <label class="form-check-label small text-secondary ms-1 fw-semibold" for="roiToggle">Enable</label>
        </div>

        <template v-if="roiEnabled">
          <!-- TransformControls mode: Resize / Move -->
          <div class="btn-group btn-group-sm" title="You can interactively resize or move the ROI box in the 3D view">
            <button
              :class="['btn', roiMode === 'scale' ? 'btn-secondary' : 'btn-outline-secondary']"
              @click="roiMode = 'scale'"
              title="Resize ROI"
            ><i class="bi bi-arrows-angle-expand"></i></button>
            <button
              :class="['btn', roiMode === 'translate' ? 'btn-secondary' : 'btn-outline-secondary']"
              @click="roiMode = 'translate'"
              title="Move ROI"
            ><i class="bi bi-arrows-move"></i></button>
          </div>

          <!-- Reset ROI button -->
          <button
            class="btn btn-sm btn-outline-secondary"
            @click="resetROI"
            title="Reset ROI to default (20-80% on all axes) and restore full volume"
          >
            <i class="bi bi-arrow-counterclockwise"></i>
          </button>

          <!-- Coordinate inputs -->
          <div class="d-flex align-items-center gap-1 ms-1 roi-readout">
            <span class="roi-label">X</span>
            <input type="number" class="roi-num" min="0" max="100" v-model.number="roiXStart" title="X start %">
            <span class="roi-sep">–</span>
            <input type="number" class="roi-num" min="0" max="100" v-model.number="roiXEnd" title="X end %">
          </div>
          <div class="d-flex align-items-center gap-1 roi-readout">
            <span class="roi-label">Y</span>
            <input type="number" class="roi-num" min="0" max="100" v-model.number="roiYStart" title="Y start %">
            <span class="roi-sep">–</span>
            <input type="number" class="roi-num" min="0" max="100" v-model.number="roiYEnd" title="Y end %">
          </div>
          <div v-if="dimensions && dimensions[2] > 1" class="d-flex align-items-center gap-1 roi-readout">
            <span class="roi-label">Z</span>
            <input type="number" class="roi-num" min="0" max="100" v-model.number="roiZStart" title="Z start %">
            <span class="roi-sep">–</span>
            <input type="number" class="roi-num" min="0" max="100" v-model.number="roiZEnd" title="Z end %">
          </div>

          <!-- Apply ROI button -->
          <button
            :class="['btn btn-sm py-0 px-2 ms-1 d-flex align-items-center gap-1', roiApplied ? 'btn-success' : 'btn-primary']"
            style="font-size: 0.75rem"
            @click="computeROIMetrics"
            :title="roiApplied ? 'ROI applied - compute metrics for ROI region' : 'Apply ROI cropping and compute local metrics'"
          >
            <i :class="roiApplied ? 'bi bi-check-circle-fill' : 'bi bi-calculator'"></i>
            {{ roiApplied ? 'Applied' : 'Apply ROI' }}
          </button>
        </template>
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
        <div v-if="segmentationMode !== 'none'" class="form-check form-switch ms-2 mb-0 d-flex align-items-center">
          <input class="form-check-input" type="checkbox" id="showBoundariesToggle" v-model="showBoundaryLines">
          <label class="form-check-label small text-secondary ms-1 fw-semibold" for="showBoundariesToggle">Boundaries</label>
        </div>
        <div v-if="segmentationMode !== 'none'" class="d-flex align-items-center ms-2 mb-0">
          <label class="me-1 mb-0 fw-semibold text-secondary small">Highlights:</label>
          <select v-model="highlightRegionMode" class="form-select form-select-sm" style="width: 140px; font-size: 0.75rem;">
            <option value="none">None</option>
            <option value="top5">Top 5 Regions</option>
            <option value="top10">Top 10 Regions</option>
            <option value="top20">Top 20 Regions</option>
            <option value="most_diff">Most Different</option>
          </select>
        </div>
        <div class="form-check form-switch ms-2 mb-0 d-flex align-items-center">
          <input class="form-check-input" type="checkbox" id="colorbarToggle" v-model="showColorBarOverlay">
          <label class="form-check-label small text-secondary ms-1 fw-semibold" for="colorbarToggle">Color Bar</label>
        </div>
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
          <div
            ref="containerOriginal"
            :class="['three-host w-100 h-100', roiEnabled && roiDrawMode ? 'roi-draw-cursor' : '']"
            @mousedown="onROIMouseDown($event, 'original')"
          >
            <!-- Rubber-band SVG overlay -->
            <svg v-if="roiEnabled && roiIsDrawing && roiDrawRect" class="roi-svg-overlay" xmlns="http://www.w3.org/2000/svg">
              <rect
                :x="roiDrawRect.x" :y="roiDrawRect.y"
                :width="roiDrawRect.w" :height="roiDrawRect.h"
                class="roi-rubberband"
              />
            </svg>
          </div>
          <!-- Custom Scalar Bar Overlay -->
          <div 
             :class="['scalar-bar-overlay', layoutMode]" 
             v-if="showColorBarOverlay && segmentationMode === 'none' && colormap && fileData"
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
             v-if="showColorBarOverlay && segmentationMode !== 'none' && hasAnySegmentation"
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
            <span class="fw-bold text-success small">{{ decompressedViewMode === 'error' ? 'Error Map ' : 'Decompressed ' }}</span>
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
          <div
            ref="containerDecompressed"
            :class="['three-host w-100 h-100', roiEnabled && roiDrawMode ? 'roi-draw-cursor' : '']"
            @mousedown="onROIMouseDown($event, 'decompressed')"
          >
            <!-- Rubber-band SVG overlay -->
            <svg v-if="roiEnabled && roiIsDrawing && roiDrawRect" class="roi-svg-overlay" xmlns="http://www.w3.org/2000/svg">
              <rect
                :x="roiDrawRect.x" :y="roiDrawRect.y"
                :width="roiDrawRect.w" :height="roiDrawRect.h"
                class="roi-rubberband"
              />
            </svg>
          </div>
          <!-- Custom Scalar Bar Overlay -->
          <div 
             :class="['scalar-bar-overlay', layoutMode]" 
             v-if="showColorBarOverlay && segmentationMode === 'none' && colormap && selectedDecompressedData"
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
             v-if="showColorBarOverlay && segmentationMode !== 'none' && selectedDecompressedData"
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
  cursor: default;
}

.three-host.roi-draw-cursor {
  cursor: crosshair;
}

/* SVG rubber-band overlay */
.roi-svg-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 20;
}

.roi-rubberband {
  fill: rgba(0, 255, 100, 0.08);
  stroke: #00ff64;
  stroke-width: 1.5px;
  stroke-dasharray: 6 3;
  animation: roi-dash 0.5s linear infinite;
}

@keyframes roi-dash {
  to { stroke-dashoffset: -9; }
}

/* ROI readout fields */
.roi-readout {
  background: rgba(0,0,0,0.06);
  border-radius: 4px;
  padding: 1px 4px;
}
.roi-label {
  font-size: 0.7rem;
  font-weight: 700;
  color: #6c757d;
  min-width: 10px;
}
.roi-sep {
  font-size: 0.7rem;
  color: #adb5bd;
}
.roi-num {
  width: 40px;
  font-size: 0.7rem;
  border: 1px solid #dee2e6;
  border-radius: 3px;
  padding: 0 2px;
  text-align: center;
  height: 22px;
  background: white;
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
  display: flex;
  align-items: center;
  justify-content: center;
  transform: rotate(-90deg);
  white-space: nowrap;
  width: 12px;
  margin-right: 2px;
  height: 100%;
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
