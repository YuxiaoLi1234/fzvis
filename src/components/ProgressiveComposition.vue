<script>
import axios from 'axios';
import TreeNode from './TreeNode.vue';
import ProgressivePipeline from './ProgressivePipeline.vue';

export default {
  name: 'ProgressiveComposition',
  components: {
    TreeNode,
    ProgressivePipeline,
  },

  props: {
    compressorId: {
      type: String,
      required: true,
    },
  },

  data() {
    return {
      configurations: {},
      documentation: {},
      highLevelOptions: {},
      childrenOptions: {},
      childrenDetails: {},
      optionLists: {},
      optionTypes: {},
      tokens: new Set(),
      treeRoot: null,
      isTreeExpanded: true,
      activeEditingNode: null,
      isTreeDisabled: false,
      isPipelineView: false,
    };
  },

  computed: {
  },

  watch: {
    compressorId: {
      immediate: true,
      handler(newVal) {
        this.tokens.clear();
        this.tokens.add(newVal);
        this.configurations = {
          "name": "pressio",
          "compressor_id": "pressio",
          "early_config": {
            "pressio": {
              "pressio:compressor": newVal,
            }
          }
        };
        this.getHighLevelOptions();
      },
    },
  },

  beforeUnmount() {
    this.tokens = null;
  },

  methods: {
    toggleAllNodes() {
      this.isTreeExpanded = !this.isTreeExpanded;
    },
    // Collect active tokens from current configuration so UI stays in sync
    collectActiveTokens(config) {
      const tokens = new Set();
      // Always include the top-level compressor id token
      if (this.compressorId) tokens.add(this.compressorId);

      const walk = (val, keyPath = []) => {
        if (Array.isArray(val)) {
          val.forEach(v => {
            if (typeof v === 'string') tokens.add(v);
          });
          return;
        }
        if (val && typeof val === 'object') {
          Object.entries(val).forEach(([k, v]) => walk(v, keyPath.concat(k)));
          return;
        }
        if (typeof val === 'string') {
          // Only add string values that look like selections (keys with colon or plugins array)
          const lastKey = keyPath[keyPath.length - 1] || '';
          if (lastKey.includes(':')) tokens.add(val);
        }
      };
      walk(config);
      return tokens;
    },
    async getHighLevelOptions() {
      try {
        const response = await axios.post(`/api/progressiveOptions`, this.configurations);
        if (response.data.error) {
          console.error('Error fetching high-level options:', response.data.error);
          return;
        }
        this.documentation = response.data.doc;
        this.highLevelOptions = response.data.highlevel;
        this.childrenOptions = response.data.children;
        this.optionLists = response.data.optionLists;
        this.optionTypes = response.data.optionTypes || {};
        
        this.updateChildrenDetails();
      } catch (error) {
        console.error('Error fetching high-level options:', error);
      }
    },

    updateChildrenDetails() {
      console.log("tokens:", this.tokens);
      const newDetails = {};
      
      for (const [path, details] of Object.entries(this.optionLists)) {
        const isRelevant = Array.from(this.tokens).some(token => path.includes(token + ':')) || path.includes('pressio:metric');
        if (isRelevant) {
          // Normalize path by replacing any segment like "x:y" with just "y"
          const normalizedPath = path
            .split('/')
            .map(seg => (seg.includes(':') ? seg.split(':').pop() : seg))
            .join('/');
          newDetails[normalizedPath] = details;
        }
      }
      this.childrenDetails = newDetails;
      console.log("Updated children details:", this.childrenDetails);
      
      // Rebuild tree
      this.treeRoot = this.buildTree(this.highLevelOptions, this.childrenOptions, this.childrenDetails);
    },

    // Build hierarchical tree from maps {path -> options}
    buildTree(highlevelMap, childrenMap, childDetailsMap) {
      const root = { name: 'pressio', path: 'pressio', highlevelOptions: [], highlevelTypes: {}, childDetails: null, children: {}, options: [] };

      const ensureNode = (path) => {
        if (path === root.path) return root;

        const rel = path.startsWith(root.path + '/')
          ? path.slice(root.path.length + 1)
          : path;

        const parts = rel.split('/').filter(Boolean);
        let cur = root; let curPath = root.path;
        for (const p of parts) {
          curPath = `${curPath}/${p}`;
          if (!cur.children[p]) {
            cur.children[p] = { name: p, path: curPath, highlevelOptions: [], highlevelTypes: {}, childDetails: null, children: {}, options: [] };
          }
          cur = cur.children[p];
        }
        return cur;
      };

      const attachDetails = (node, detail) => {
        if (detail) {
          node.childDetails = detail;
          node.options = detail.options || [];
        }
      };

      // Insert highlevel options with type information
      Object.entries(highlevelMap || {}).forEach(([path, opts]) => {
        const node = ensureNode(path);
        node.highlevelOptions = Array.isArray(opts) ? opts : [];
        // Map each option to its type
        node.highlevelTypes = {};
        node.highlevelOptions.forEach(optName => {
          node.highlevelTypes[optName] = this.optionTypes[optName] || 'unknown';
        });
      });

      // Insert children lists and their details
      Object.entries(childrenMap || {}).forEach(([path, children]) => {
        // Ensure the parent node exists in the tree
        ensureNode(path);
        const list = Array.isArray(children) ? children : [];
        list.forEach((childPath) => {
          const childNode = ensureNode(childPath);
          // attach detail if available
          attachDetails(childNode, childDetailsMap[childPath]);
        });
      });

      // Also attach details for any nodes present only in details
      Object.entries(childDetailsMap || {}).forEach(([path, detail]) => {
        const node = ensureNode(path);
        if (!node.childDetails) { // Avoid overwriting
          attachDetails(node, detail);
        }
      });

      return root;
    },

    handleNodeEdit(path) {
      this.activeEditingNode = path;
    },
    async handleNodeSave(path) {
      if (this.activeEditingNode === path) {
        this.activeEditingNode = null;
        this.isTreeDisabled = true;
        console.log('Current configuration:', JSON.stringify(this.configurations, null, 2));
        await this.getHighLevelOptions();
        this.isTreeDisabled = false;
      }
    },
    handleSelection({ path, option, slot, isMetric }) {
      if (!slot) return;
      
      const parts = path.split('/');
      let current = this.configurations.early_config;
      
      // Traverse path but only descend if the key exists in the config
      for (const part of parts) {
        if (current[part] && typeof current[part] === 'object') {
          current = current[part];
        } else {
          break;
        }
      }
      
      if (isMetric) {
        const ids = Array.isArray(option) ? option.map(o => o.id) : [];
        if (ids.length) {
          current[slot] = 'composite';
          current['composite:plugins'] = ids;
        } else {
          delete current[slot];
          delete current['composite:plugins'];
        }
      } else {
        // const prev = current[slot];
        if (option) {
          current[slot] = option.id;
        } else {
          delete current[slot];
        }
      }
      
      // Refresh tokens from current configuration
      this.tokens = this.collectActiveTokens(this.configurations);
      this.updateChildrenDetails();
    },

    handleHighlevelChange({ path, values }) {
      console.log('High-level options changed:', path, values);
      
      // Navigate to the correct location in the configuration
      const parts = path.split('/');
      let current = this.configurations.early_config;
      
      // Traverse path to find the right config object
      for (const part of parts) {
        if (current[part] && typeof current[part] === 'object') {
          current = current[part];
        } else {
          break;
        }
      }
      
      // Update the configuration with the new values
      Object.entries(values).forEach(([key, value]) => {
        // Convert to appropriate type based on optionTypes
        const type = this.optionTypes[key];
        
        // Handle boolean types
        if (type && type.toLowerCase() === 'bool') {
          current[key] = Boolean(value);
        } else if (value !== null && value !== undefined && value !== '') {
          // Handle other types
          let convertedValue = value;
          
          if (type && type.toLowerCase().includes('int')) {
            convertedValue = parseInt(value, 10);
          } else if (type && (type.toLowerCase() === 'float' || type.toLowerCase() === 'double')) {
            convertedValue = parseFloat(value);
          }
          
          current[key] = convertedValue;
        } else {
          // Remove the key if value is empty
          delete current[key];
        }
      });
      
      console.log('Updated configuration:', JSON.stringify(this.configurations, null, 2));
    },

    saveConfiguration() {
      // Emit the current progressive composition config as-is
      const config = JSON.parse(JSON.stringify(this.configurations));
      this.$emit('save-configuration', config);
    },

    reset() {
      // Reset to initial state for current compressorId
      this.tokens.clear();
      if (this.compressorId) this.tokens.add(this.compressorId);
      this.configurations = {
        name: 'pressio',
        compressor_id: 'pressio',
        early_config: {
          pressio: {
            'pressio:compressor': this.compressorId,
          },
        },
      };
      this.treeRoot = null;
      this.activeEditingNode = null;
      this.isTreeDisabled = false;
      this.getHighLevelOptions();
    },
  },
};
</script>

<template>
  <div>
    <div class="d-flex justify-content-start align-items-center mb-2">
      <div class="form-check form-switch m-0">
        <input class="form-check-input" type="checkbox" id="viewSwitch" v-model="isPipelineView">
        <label class="form-check-label" for="viewSwitch">Use pipeline view</label>
      </div>
    </div>
    <div class="d-flex justify-content-between align-items-center">
      <h5>{{ isPipelineView ? 'Composition Pipeline' : 'Composition Tree' }}</h5>
      <button v-if="!isPipelineView" class="btn btn-sm btn-outline-secondary" @click="toggleAllNodes" :title="isTreeExpanded ? 'Collapse All' : 'Expand All'">
        <i :class="['bi', isTreeExpanded ? 'bi-arrows-collapse' : 'bi-arrows-expand']"></i>
      </button>
    </div>
    <div class="mt-2" :class="{ 'opacity-50 pe-none': isTreeDisabled }">
      <template v-if="!isPipelineView">
        <TreeNode
          v-if="treeRoot"
          :node="treeRoot"
          :is-expanded="isTreeExpanded"
          :active-editing-node="activeEditingNode"
          @edit-node="handleNodeEdit"
          @save-node="handleNodeSave"
          @child-option-selected="handleSelection"
          @highlevel-option-changed="handleHighlevelChange"
        />
        <div v-else class="text-muted">No options available.</div>
      </template>
      <template v-else>
        <ProgressivePipeline
          v-if="treeRoot"
          :tree-root="treeRoot"
          :option-types="optionTypes"
          :disabled="isTreeDisabled"
          @child-option-selected="handleSelection"
          @save-node="handleNodeSave"
        />
        <div v-else class="text-muted">No options available.</div>
      </template>
    </div>
    <div class="mt-3 d-flex gap-2">
        <button type="button" class="btn btn-primary" @click="saveConfiguration">Save</button>
        <button type="button" class="btn btn-secondary" @click="reset">Reset</button>
    </div>
  </div>
</template>
