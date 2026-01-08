<script>
export default {
  name: 'ProgressivePipeline',
  emits: ['child-option-selected', 'save-node'],
  props: {
    treeRoot: { type: Object, required: true },
    optionTypes: { type: Object, default: () => ({}) },
    disabled: { type: Boolean, default: false },
  },
  data() {
    return {
      selectedModulePath: null,
      draggingOption: null,
      moduleSelections: {}, // path -> { selected: string | string[] }
    };
  },
  computed: {
    modules() {
      // Flatten nodes with childDetails into a simple ordered list
      const list = [];
      const walk = (node) => {
        if (!node) return;
        if (node.childDetails && Array.isArray(node.childDetails.options) && node.childDetails.options.length) {
          list.push({
            name: node.name,
            path: node.path,
            slot: node.childDetails.slot,
            type: node.childDetails.type,
            options: node.childDetails.options,
          });
        }
        const children = node.children ? Object.values(node.children) : [];
        children.sort((a, b) => a.path.localeCompare(b.path));
        children.forEach(walk);
      };
      walk(this.treeRoot);
      return list;
    },
    selectedModule() {
      return this.modules.find(m => m.path === this.selectedModulePath) || null;
    },
  },
  watch: {
    selectedModulePath() {
      // Reset scroll position when module changes
      this.$nextTick(() => {
        if (this.$refs.optionsPanel) {
          this.$refs.optionsPanel.scrollTop = 0;
        }
      });
    },
  },
  methods: {
    selectModule(path) {
      this.selectedModulePath = (this.selectedModulePath === path) ? null : path;
    },
    getOptionsForModule(path) {
      const mod = this.modules.find(m => m.path === path);
      return mod ? mod.options : [];
    },
    onOptionDragStart(optionLabel, modulePath, event) {
      event.dataTransfer.setData('text/plain', optionLabel);
      event.dataTransfer.setData('module-path', modulePath);
      this.draggingOption = { label: optionLabel, modulePath };
    },
    onModuleDragOver(modulePath, event) {
      event.dataTransfer.dropEffect = 'copy';
      event.currentTarget.style.cursor = 'copy';
    },
    onModuleDragLeave(event) {
      event.currentTarget.style.cursor = 'pointer';
    },
    onDropOption(modulePath, event) {
      let label = this.draggingOption ? this.draggingOption.label : null;
      if (!label && event.dataTransfer) {
        label = event.dataTransfer.getData('text/plain');
      }
      this.draggingOption = null;
      if (!label) return;
      const mod = this.modules.find(m => m.path === modulePath);
      if (!mod) return;

      const isMetric = mod.type === 'metric';
      // Update local selection state
      if (!this.moduleSelections[modulePath]) {
        this.moduleSelections[modulePath] = { selected: isMetric ? [] : null };
      }
      if (isMetric) {
        const arr = this.moduleSelections[modulePath].selected;
        if (!arr.includes(label)) arr.push(label);
      } else {
        this.moduleSelections[modulePath].selected = label;
      }

      // Emit selection to parent to update configurations
      const payloadOption = isMetric
        ? (this.moduleSelections[modulePath].selected || []).map(v => ({ id: v, label: v }))
        : { id: label, label };
      this.$emit('child-option-selected', {
        path: modulePath,
        option: payloadOption,
        slot: mod.slot,
        isMetric,
      });
      // signal save on this node to trigger refresh upstream
      this.$emit('save-node', modulePath);
    },
    removeSelection(modulePath, label) {
      const mod = this.modules.find(m => m.path === modulePath);
      if (!mod) return;
      const isMetric = mod.type === 'metric';
      if (!this.moduleSelections[modulePath]) return;
      if (isMetric) {
        this.moduleSelections[modulePath].selected = (this.moduleSelections[modulePath].selected || []).filter(v => v !== label);
      } else {
        this.moduleSelections[modulePath].selected = null;
      }

      const payloadOption = isMetric
        ? (this.moduleSelections[modulePath].selected || []).map(v => ({ id: v, label: v }))
        : null;
      this.$emit('child-option-selected', {
        path: modulePath,
        option: payloadOption,
        slot: mod.slot,
        isMetric,
      });
      this.$emit('save-node', modulePath);
    },
  },
};
</script>

<template>
  <div class="bg-light p-2 my-3 rounded shadow-sm w-100" :class="{ 'opacity-50 pe-none': disabled }">
    <div class="row">
      <div class="col-md-5">
        <div class="vertical-pipeline d-flex flex-column align-items-start">
          <template v-for="(module, idx) in modules" :key="module.path">
            <div :class="['pipeline-item d-flex align-items-center', idx < modules.length - 1 ? 'mb-4' : 'mb-1']" style="position: relative;">
              <div v-if="idx > 0" class="pipeline-vertical-connector"></div>
              <div
                class="pipeline-module card text-center border-2"
                :class="{'border-primary shadow': selectedModule && selectedModule.path === module.path, 'border-secondary': !selectedModule || selectedModule.path !== module.path}"
                style="min-width: 140px; cursor: pointer;"
                @click="selectModule(module.path)"
                @dragover.prevent="onModuleDragOver(module.path, $event)"
                @dragleave="onModuleDragLeave($event)"
                @drop="onDropOption(module.path, $event)"
              >
                <div class="card-body d-flex flex-column justify-content-center">
                  <span class="fw-bold" :title="module.path">{{ module.name }}</span>
                  <div v-if="moduleSelections[module.path] && (module.type === 'metric' ? (moduleSelections[module.path].selected || []).length : moduleSelections[module.path].selected)" class="mt-2 position-relative">
                    <div class="bg-light border rounded px-2 py-1 w-100 d-flex flex-column align-items-center justify-content-center">
                      <template v-if="module.type === 'metric'">
                        <div v-for="sel in (moduleSelections[module.path].selected || [])" :key="sel" class="d-flex align-items-center gap-1">
                          <span class="small text-success">{{ sel }}</span>
                          <button type="button" class="btn btn-link btn-sm text-danger p-0" title="Remove option" @click.stop="removeSelection(module.path, sel)">
                            <span aria-hidden="true">&times;</span>
                          </button>
                        </div>
                      </template>
                      <template v-else>
                        <div class="d-flex align-items-center gap-1">
                          <span class="small text-success">{{ moduleSelections[module.path].selected }}</span>
                          <button type="button" class="btn btn-link btn-sm text-danger p-0" title="Remove option" @click.stop="removeSelection(module.path)">
                            <span aria-hidden="true">&times;</span>
                          </button>
                        </div>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
      <div class="col-md-7 align-self-center">
        <div v-if="selectedModule" ref="optionsPanel" class="options-panel card p-3" style="max-height: 400px; overflow-y: auto;">
          <h6 class="fw-bold mb-3">Available Options</h6>
          <div v-for="opt in selectedModule.options" :key="opt" class="option-item mb-2">
            <span
              class="badge px-3 py-2 bg-info text-dark"
              draggable="true"
              style="cursor:pointer;"
              @dragstart="onOptionDragStart(opt, selectedModule.path, $event)"
            >{{ opt }}</span>
          </div>
        </div>
        <div v-else class="text-muted">Select a node to view options.</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vertical-pipeline { width: 100%; }
.pipeline-item { width: 100%; }
.pipeline-vertical-connector {
  position: absolute;
  left: 50px;
  top: -25px;
  width: 3px;
  height: 30px;
  background-color: #dee2e6;
  z-index: 0;
}
.pipeline-module .card-body span {
  white-space: normal;
  word-break: break-word;
  text-align: center;
}
.options-panel {
  background: #f8f9fa;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.option-item .badge {
  white-space: normal;
  word-break: break-word;
  text-align: left;
}
</style>