/**
 * Represents a connection point on a node.
 */
export class Port {
  constructor(id, label, type) {
    this.id = id;
    this.label = label;
    this.type = type; // 'input' or 'output'
  }
}

/**
 * Base class for all nodes in the DataFlow graph.
 * Implements the core logic for node validation and connections.
 */
export class BaseNode {
  constructor(id, label, icon, inputCount = 1, outputCount = 1) {
    this.id = id;
    this.label = label;
    this.icon = icon;
    this.type = 'base';
    this.status = 'pending';
    this.x = 0;
    this.y = 0;
    this.inputCount = inputCount;
    this.outputCount = outputCount;
    this.inputs = [];
    this.outputs = [];
    this.config = {}; // Stores node-specific configuration
    this.editorComponent = null; // Vue component to render in properties pane
  }

  /**
   * Helper method to initialize ports based on inputCount and outputCount.
   * @param {string} inputLabel - Label pattern for input ports (use {i} for index)
   * @param {string} outputLabel - Label pattern for output ports (use {i} for index)
   */
  initializePorts(inputLabel = 'Data In', outputLabel = 'Data Out') {
    this.inputs = [];
    for (let i = 0; i < this.inputCount; i++) {
      const label = this.inputCount > 1
        ? inputLabel.replace('{i}', String(i + 1))
        : inputLabel.replace('{i}', '').trim();
      this.inputs.push(new Port(`in-${i}`, label, 'input'));
    }

    this.outputs = [];
    for (let i = 0; i < this.outputCount; i++) {
      const label = this.outputCount > 1
        ? outputLabel.replace('{i}', String(i + 1))
        : outputLabel.replace('{i}', '').trim();
      this.outputs.push(new Port(`out-${i}`, label, 'output'));
    }
  }

  /**
   * Determines if this node type can be added to the graph given the current state.
   * @param {Array} existingNodes - The current nodes in the graph.
   * @returns {boolean}
   */
  // eslint-disable-next-line no-unused-vars
  static canAdd(existingNodes) {
    return true;
  }

  /**
   * Checks if this node can accept an incoming connection from the sourceNode.
   * Each input port can only accept ONE connection at a time.
   * The existing connection will be replaced when a new connection is made.
   * @param {BaseNode} sourceNode - The node attempting to connect to this node.
   * @returns {boolean}
   */
  // eslint-disable-next-line no-unused-vars
  canAcceptInput(sourceNode) {
    return this.inputs.length > 0;
  }

  /**
   * Checks if this node can connect to a targetNode.
   * @param {BaseNode} targetNode - The node this node is attempting to connect to.
   * @returns {boolean}
   */
  canConnectTo(targetNode) {
    if (this.outputs.length === 0) return false;
    return targetNode.canAcceptInput(this);
  }

  /**
   * Called when the node is being removed from the graph.
   * Override this to perform necessary reverse operations or cleanup.
   * @param {Object} context - Context object containing store, etc.
   */
  // eslint-disable-next-line no-unused-vars
  onDestroy(context) {
    // Default: no-op
  }
}

/**
 * Data Source Node: The entry point of the pipeline.
 */
export class DataSourceNode extends BaseNode {
  constructor(id, label = 'Data Source', icon = 'bi-database') {
    super(id, label, icon, 0, 1);
    this.type = 'source';
    this.status = 'empty';
    this.initializePorts('', 'Data Out');
    this.editorComponent = 'InputDataset';
  }

  static canAdd(existingNodes) {
    return existingNodes.length === 0;
  }

  // eslint-disable-next-line no-unused-vars
  canAcceptInput(sourceNode) {
    return false;
  }

  onDestroy(context) {
    if (context?.store) {
      context.store.commit('clearFileData');
    }
  }
}

/**
 * Filter Node: Preprocessing steps.
 */
export class FilterNode extends BaseNode {
  constructor(id, label, icon = 'bi-funnel', filterId = null) {
    super(id, label, icon, 1, 1);
    this.type = 'filter';
    this.initializePorts('Data In', 'Filtered Data');

    // Map filter IDs to their respective components
    const componentMap = {
      clipping: 'DataClipping',
      threshold_mask: 'DataThresholdMask',
      normalization: 'DataNormalization',
    };
    this.editorComponent = componentMap[filterId] || null;
  }

  static canAdd(existingNodes) {
    const sourceNode = existingNodes.find(n => n instanceof DataSourceNode);
    return !!sourceNode && sourceNode.status === 'ready';
  }

  canAcceptInput(sourceNode) {
    if (sourceNode.type === 'compression') return false;
    return super.canAcceptInput(sourceNode);
  }

  onDestroy(context) {
    // Remove this filter's operation from the stack
    if (context?.store) {
      const operations = context.store.state.filterOperations || [];
      const opIndex = operations.findIndex(op => op.nodeId === this.id);

      if (opIndex !== -1) {
        // Remove this filter and all subsequent filters
        context.store.commit('removeFilterOperation', this.id);

        // Remove all filters that came after this one
        const remainingOps = operations.slice(0, opIndex);
        context.store.state.filterOperations = remainingOps;

        // Replay the pipeline from the beginning with remaining filters
        if (context.filterComponents) {
          context.store.dispatch('replayFilterPipeline', {
            filterComponents: context.filterComponents,
          }).catch(error => {
            console.error('Failed to replay filter pipeline:', error);
          });
        }
      }
    }
  }
}

/**
 * Module Node: Processing modules that can accept multiple inputs.
 */
export class ModuleNode extends BaseNode {
  constructor(id, label, icon = 'bi-puzzle', moduleId = null, config = {}) {
    const inputCount = config.inputCount || 1;
    const outputCount = config.outputCount || 1;

    super(id, label, icon, inputCount, outputCount);
    this.type = 'module';
    this.initializePorts('Data In {i}', 'Processed Data {i}');

    // Map module IDs to their respective components
    const componentMap = {
      'testing': 'TestingModule'
    };
    this.editorComponent = componentMap[moduleId] || null;
  }

  static canAdd(existingNodes) {
    const sourceNode = existingNodes.find(n => n instanceof DataSourceNode);
    return !!sourceNode && sourceNode.status === 'ready';
  }

  canAcceptInput(sourceNode) {
    return super.canAcceptInput(sourceNode);
  }
}

/**
 * Compression Node: The main processing module or compressor.
 */
export class CompressorNode extends BaseNode {
  constructor(id, label, icon = 'bi-cpu', compressorId = null, architecture = 'parametric') {
    super(id, label, icon, 1, 1);
    this.type = 'compressor';
    this.compressorId = compressorId;
    this.architecture = architecture;
    this.initializePorts('Data In', 'Compressed Data');

    // Map compressor IDs to their respective components
    const componentMap = {
      'sz3': 'SZ3Pipeline',
      'zfp': 'ZFPConfig',
      'testing': 'TestingPipeline' // Example
    };
    this.editorComponent = componentMap[compressorId] || null;

    // Expansion state for showing internal pipeline modules
    this.expanded = false;
    this.modules = []; // Pipeline modules from the compressor component
    this.selectedModuleIdx = null; // Track which module is selected for detail view
  }

  static canAdd(existingNodes) {
    const sourceNode = existingNodes.find(n => n instanceof DataSourceNode);
    return !!sourceNode && sourceNode.status === 'ready';
  }

  canAcceptInput(sourceNode) {
    return super.canAcceptInput(sourceNode);
  }

  onDestroy(context) {
    // Clean up the stored compression results from the store
    if (context?.store) {
      context.store.commit('removeComparisonData', this.id);
    }
  }
}

/**
 * Correction Node: Post-processing corrections like critical points preservation.
 */
export class CorrectionNode extends BaseNode {
  constructor(id, label, icon = 'bi-gear', correctionId = null) {
    super(id, label, icon, 1, 1);
    this.type = 'correction';

    // Manually initialize ports with descriptive labels
    this.inputs = [
      new Port('in-0', 'Compressed Data', 'input')
    ];
    this.outputs = [
      new Port('out-0', 'Corrected Data', 'output')
    ];

    // Map correction IDs to their respective components
    const componentMap = {
      'critical_points': 'CriticalPointsPreservation',
    };
    this.editorComponent = componentMap[correctionId] || null;
  }

  static canAdd(existingNodes) {
    const sourceNode = existingNodes.find(n => n instanceof DataSourceNode);
    if (!sourceNode || sourceNode.status !== 'ready') return false;

    // Only allow one correction node in the graph
    const existingCorrectionNode = existingNodes.find(n => n instanceof CorrectionNode);
    if (existingCorrectionNode) return false;

    // Require at least one compressor node
    const compressorNode = existingNodes.find(n =>
      n instanceof CompressorNode
    );
    return !!compressorNode;
  }

  canAcceptInput(sourceNode) {
    // Only accept input from compressor for the single input port
    if (sourceNode.type === 'compressor') {
      return this.inputs.length > 0;
    }
    return false;
  }

  onDestroy(context) {
    // Clean up the stored correction results from the store
    if (context?.store) {
      context.store.commit('removeComparisonData', this.id);
    }
  }
}

/**
 * Factory to create nodes based on type.
 */
export class NodeFactory {
  static createNode(type, id, label, icon, defId = null, config = {}) {
    switch (type) {
      case 'source':
        return new DataSourceNode(id, label, icon);
      case 'filter':
        return new FilterNode(id, label, icon, defId);
      case 'module':
        return new ModuleNode(id, label, icon, defId, config);
      case 'compressor':
        return new CompressorNode(id, label, icon, defId, config.architecture);
      case 'correction':
        return new CorrectionNode(id, label, icon, defId);
      default:
        return new BaseNode(id, label, icon);
    }
  }

  static getClassByType(type) {
    switch (type) {
      case 'source': return DataSourceNode;
      case 'filter': return FilterNode;
      case 'module': return ModuleNode;
      case 'compressor': return CompressorNode;
      case 'correction': return CorrectionNode;
      default: return BaseNode;
    }
  }
}
