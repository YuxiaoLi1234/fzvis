import { Tooltip, Popover } from 'bootstrap';

/**
 * Vue 3 directive for Bootstrap Tooltips (v-tooltip)
 *
 * Usage examples:
 *   v-tooltip="'Tooltip text'"
 *   v-tooltip:bottom="'Tooltip at bottom'"
 *   v-tooltip="{ title: 'Text', placement: 'right' }"
 */
export const tooltipDirective = {
  mounted(el, binding) {
    const options = {};

    if (typeof binding.value === 'string') {
      options.title = binding.value;
    } else if (typeof binding.value === 'object' && binding.value !== null) {
      Object.assign(options, binding.value);
    } else {
      const titleAttr = el.getAttribute('title') || el.getAttribute('data-bs-title');
      if (titleAttr) {
        options.title = titleAttr;
      }
    }

    if (binding.arg) {
      options.placement = binding.arg;
    }

    if (!options.trigger) {
      options.trigger = 'hover focus';
    }

    try {
      new Tooltip(el, options);
    } catch (e) {
      console.warn('Failed to initialize tooltip:', e);
    }
  },

  updated(el, binding) {
    const instance = Tooltip.getInstance(el);
    if (!instance) return;

    let newTitle = '';
    if (typeof binding.value === 'string') {
      newTitle = binding.value;
    } else if (typeof binding.value === 'object' && binding.value?.title) {
      newTitle = binding.value.title;
    }

    if (newTitle && typeof instance.setContent === 'function') {
      instance.setContent({ '.tooltip-inner': newTitle });
    }
  },

  unmounted(el) {
    const instance = Tooltip.getInstance(el);
    if (instance) {
      instance.dispose();
    }
  }
};

/**
 * Vue 3 directive for Bootstrap Popovers (v-popover)
 *
 * Usage examples:
 *   v-popover="{ title: 'Title', content: 'Content' }"
 *   v-popover="'Popover body text'"
 */
export const popoverDirective = {
  mounted(el, binding) {
    const options = {
      trigger: 'focus',
    };

    if (typeof binding.value === 'string') {
      options.content = binding.value;
    } else if (typeof binding.value === 'object' && binding.value !== null) {
      Object.assign(options, binding.value);
    }

    if (binding.arg) {
      options.placement = binding.arg;
    }

    try {
      new Popover(el, options);
    } catch (e) {
      console.warn('Failed to initialize popover:', e);
    }
  },

  unmounted(el) {
    const instance = Popover.getInstance(el);
    if (instance) {
      instance.dispose();
    }
  }
};

export default {
  install(app) {
    app.directive('tooltip', tooltipDirective);
    app.directive('popover', popoverDirective);
  }
};
