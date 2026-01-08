<template>
  <div class="tree-node mb-2">
    <div @click="toggle" :class="['d-flex align-items-center gap-1', hasChildren ? 'pe-auto cursor-pointer' : '']" :title="node.path">
      <span v-if="hasChildren" class="me-1 text-secondary">{{ collapsed ? '▶' : '▼' }}</span>
      <span :class="['fw-semibold', ...headerClass]">{{ node.name }}</span>
    </div>

    <div v-show="!collapsed" class="ms-3 mt-1">
      <div v-if="node.highlevelOptions && node.highlevelOptions.length" class="my-2">
        <div class="d-flex align-items-center mb-1">
          <span class="me-2">⚙️</span>
          <span class="fw-semibold">High-level options</span>
          <button @click="toggleHighlevelEdit" class="btn btn-sm btn-info ms-2 d-flex align-items-center" :disabled="isEditingDisabled">
            <i :class="['bi', isEditingHighlevel ? 'bi-save' : 'bi-pencil-square']"></i>
            <span class="ms-1">{{ isEditingHighlevel ? 'Save' : 'Edit' }}</span>
          </button>
        </div>
        <div class="ms-2">
          <div v-for="opt in node.highlevelOptions" :key="opt" class="mb-2">
            <label :for="`${node.path}-${opt}`" class="form-label small mb-1">
              {{ opt }}
              <span v-if="node.highlevelTypes && node.highlevelTypes[opt]" class="badge bg-secondary ms-1" style="font-size: 0.65rem;">
                {{ node.highlevelTypes[opt] }}
              </span>
            </label>
            
            <!-- Boolean type: show switch -->
            <div v-if="isEditingHighlevel && node.highlevelTypes[opt] === 'bool'" class="form-check form-switch">
              <input
                :id="`${node.path}-${opt}`"
                v-model="highlevelValues[opt]"
                type="checkbox"
                class="form-check-input"
                role="switch"
              />
              <label class="form-check-label small text-muted" :for="`${node.path}-${opt}`">
                {{ highlevelValues[opt] ? 'Enabled' : 'Disabled' }}
              </label>
            </div>
            
            <!-- Non-boolean types: show regular input -->
            <input
              v-else-if="isEditingHighlevel"
              :id="`${node.path}-${opt}`"
              v-model="highlevelValues[opt]"
              :type="getInputType(node.highlevelTypes[opt])"
              :step="getInputStep(node.highlevelTypes[opt])"
              class="form-control form-control-sm"
              :placeholder="`Enter ${opt}`"
            />
            
            <!-- View mode -->
            <div v-else class="ps-2">
              <code v-if="highlevelValues[opt] !== null && highlevelValues[opt] !== undefined">
                {{ typeof highlevelValues[opt] === 'boolean' ? (highlevelValues[opt] ? 'true' : 'false') : highlevelValues[opt] }}
              </code>
              <small v-else class="text-muted">Not set</small>
            </div>
          </div>
        </div>
      </div>

      <div v-if="node.childDetails && childOptions.length" class="my-2">
        <div class="d-flex align-items-center gap-2 mb-1">
          <div class="fw-semibold small">Option</div>
          <button @click="toggleEdit" class="btn btn-sm btn-outline-info d-flex align-items-center" :disabled="isEditingDisabled">
            <i :class="['bi', isEditing ? 'bi-save' : 'bi-pencil-square']"></i>
            <span class="ms-1">{{ isEditing ? 'Save' : 'Edit' }}</span>
          </button>
        </div>

        <div v-if="isEditing" class="mt-2">
          <multiselect
            :id="selectId"
            v-model="selectedChildOption"
            :options="multiselectOptions"
            :searchable="true"
            :multiple="isMetric"
            :close-on-select="!isMetric"
            placeholder="Select an option"
            label="label"
            track-by="id"
          ></multiselect>
        </div>
        <div v-else class="ps-2">
          <template v-if="isMetric">
            <code v-if="Array.isArray(selectedChildOption) && selectedChildOption.length">
              {{ selectedChildOption.map(o => o.label).join(', ') }}
            </code>
            <small v-else class="text-muted">None selected</small>
          </template>
          <template v-else>
            <code v-if="selectedChildOption">{{ selectedChildOption.label }}</code>
            <small v-else class="text-muted">None selected</small>
          </template>
        </div>
      </div>

      <div class="border-start ps-2 ms-2">
        <TreeNode
          v-for="child in orderedChildren"
          :key="child.path"
          :node="child"
          :depth="depth + 1"
          :is-expanded="isExpanded"
          :active-editing-node="activeEditingNode"
          @edit-node="$emit('edit-node', $event)"
          @save-node="$emit('save-node', $event)"
          @child-option-selected="$emit('child-option-selected', $event)"
          @highlevel-option-changed="$emit('highlevel-option-changed', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script>
import Multiselect from 'vue-multiselect';

export default {
  name: 'TreeNode',
  components: {
    Multiselect,
  },
  props: {
    node: { type: Object, required: true },
    depth: { type: Number, default: 0 },
    isExpanded: { type: Boolean, default: false },
    activeEditingNode: { type: String, default: null },
  },
  data() {
    return {
      collapsed: !this.isExpanded,
      selectedChildOption: null,
      isEditing: false,
      highlevelValues: {},
      isEditingHighlevel: false,
    };
  },
  watch: {
    isExpanded(newVal) {
      this.collapsed = !newVal;
    },
  },
  computed: {
    hasChildren() {
      return this.node && this.node.children && Object.keys(this.node.children).length > 0;
    },
    orderedChildren() {
      const vals = Object.values(this.node.children || {});
      return vals.filter(child => child.name !== 'composite').sort((a, b) => a.name.localeCompare(b.name));
    },
    // Bootstrap font-size utility classes based on depth
    headerClass() {
      if (this.depth <= 0) return ['fs-5'];
      if (this.depth === 1) return ['fs-6'];
      return ['small'];
    },
    itemClass() {
      if (this.depth <= 0) return [];
      if (this.depth === 1) return ['small'];
      return ['small'];
    },
    levelTextClass() {
      if (this.depth <= 0) return ['fs-6'];
      if (this.depth === 1) return ['small'];
      return ['small'];
    },
    childOptions() {
      if (this.node && Array.isArray(this.node.options)) {
        return this.node.options;
      }
      const opts = (this.node && this.node.childDetails && Array.isArray(this.node.childDetails.options))
        ? this.node.childDetails.options
        : [];
      return opts;
    },
    selectId() {
      return `select-${btoa(this.node.path).replace(/=/g, '')}`;
    },
    multiselectOptions() {
      const base = Array.isArray(this.childOptions) ? this.childOptions : [];
      return base.map(opt => ({ id: opt, label: opt }));
    },
    isEditingDisabled() {
      return this.activeEditingNode && this.activeEditingNode !== this.node.path;
    },
    isMetric() {
      return !!(this.node && this.node.childDetails && this.node.childDetails.type === 'metric');
    },
  },
  methods: {
    toggle() { if (this.hasChildren) this.collapsed = !this.collapsed; },
    emitSelection() {
      const slot = this.node.childDetails ? this.node.childDetails.slot : null;
      let optionPayload = this.selectedChildOption;
      if (this.isMetric) {
        // Ensure an array payload of selected options
        if (!Array.isArray(optionPayload)) optionPayload = optionPayload ? [optionPayload] : [];
      }
      this.$emit('child-option-selected', { path: this.node.path, option: optionPayload, slot, isMetric: this.isMetric });
    },
    toggleEdit() {
      if (this.isEditing) {
        this.emitSelection();
        this.$emit('save-node', this.node.path);
      } else {
        this.$emit('edit-node', this.node.path);
      }
      this.isEditing = !this.isEditing;
    },
    toggleHighlevelEdit() {
      if (this.isEditingHighlevel) {
        // Save the highlevel values
        this.$emit('highlevel-option-changed', { path: this.node.path, values: this.highlevelValues });
        this.$emit('save-node', this.node.path);
      } else {
        this.$emit('edit-node', this.node.path);
      }
      this.isEditingHighlevel = !this.isEditingHighlevel;
    },
    getInputType(type) {
      // Map libpressio types to HTML input types
      if (!type) return 'text';
      const lowerType = type.toLowerCase();
      if (lowerType.includes('int') || lowerType.includes('uint')) {
        return 'number';
      }
      if (lowerType === 'float' || lowerType === 'double') {
        return 'number';
      }
      return 'text';
    },
    getInputStep(type) {
      // Return appropriate step for number inputs
      if (!type) return 'any';
      const lowerType = type.toLowerCase();
      if (lowerType.includes('int') || lowerType.includes('uint')) {
        return '1';
      }
      if (lowerType === 'float' || lowerType === 'double') {
        return 'any';
      }
      return 'any';
    },
  },
};
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
</style>
