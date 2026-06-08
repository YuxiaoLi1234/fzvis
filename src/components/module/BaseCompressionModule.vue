<script>
export default {
  name: 'BaseCompressionModule',
  props: {
    nodeId: {
      type: String,
      default: null,
    },
    moduleDefinition: {
      type: Object,
      default: () => ({}),
    },
    nodeConfig: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['config-change'],
  data() {
    return {
      notes: '',
      mode: 'preview',
    };
  },
  mounted() {
    this.notes = this.nodeConfig?.notes || '';
    this.mode = this.nodeConfig?.mode || 'preview';
    this.emitChange();
  },
  methods: {
    emitChange() {
      this.$emit('config-change', {
        module_config: {
          notes: this.notes,
          mode: this.mode,
          module_id: this.moduleDefinition?.id || null,
        },
      });
    },
  },
};
</script>

<template>
  <div class="module-editor">
    <div class="module-hero rounded-3 p-3 mb-3">
      <div class="d-flex align-items-start justify-content-between gap-3">
        <div>
          <div class="text-uppercase small fw-semibold module-kicker">Compression Module</div>
          <h5 class="mb-1">{{ moduleDefinition.label || 'Module' }}</h5>
          <p class="mb-0 text-muted small">
            {{ moduleDefinition.description || 'Reusable pipeline building block.' }}
          </p>
        </div>
        <div class="d-flex flex-column gap-2 align-items-end">
          <span class="badge text-bg-light border">ID {{ moduleDefinition.id || 'unknown' }}</span>
          <span class="badge module-badge">
            {{ moduleDefinition.inputCount || 1 }} in / {{ moduleDefinition.outputCount || 1 }} out
          </span>
        </div>
      </div>
    </div>

    <div class="card border-0 shadow-sm">
      <div class="card-body">
        <div class="row g-3">
          <div class="col-md-5">
            <label class="form-label fw-semibold small text-muted">Module Mode</label>
            <select v-model="mode" class="form-select" @change="emitChange">
              <option value="preview">Preview</option>
              <option value="active">Active</option>
              <option value="bypass">Bypass</option>
            </select>
          </div>
          <div class="col-md-7">
            <label class="form-label fw-semibold small text-muted">Designer Notes</label>
            <input
              v-model="notes"
              type="text"
              class="form-control"
              placeholder="Add notes about how this module should be used"
              @input="emitChange"
            >
          </div>
        </div>

        <div class="module-spec mt-3 p-3 rounded-3">
          <div class="fw-semibold mb-2">Current wiring shape</div>
          <div class="small text-muted">
            This module expects <strong>{{ moduleDefinition.inputCount || 1 }}</strong> incoming edge<span v-if="(moduleDefinition.inputCount || 1) > 1">s</span>
            and produces <strong>{{ moduleDefinition.outputCount || 1 }}</strong> outgoing edge<span v-if="(moduleDefinition.outputCount || 1) > 1">s</span>.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.module-hero {
  background:
    radial-gradient(circle at top left, rgba(255, 193, 7, 0.25), transparent 45%),
    linear-gradient(135deg, rgba(13, 110, 253, 0.06), rgba(25, 135, 84, 0.08));
  border: 1px solid rgba(13, 110, 253, 0.14);
}

.module-kicker {
  letter-spacing: 0.08em;
  color: #0d6efd;
}

.module-badge {
  background: #0d6efd;
  color: #fff;
}

.module-spec {
  background: #f8f9fa;
  border: 1px dashed rgba(13, 110, 253, 0.25);
}
</style>
