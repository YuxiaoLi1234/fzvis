import { createApp } from 'vue'
import App from './App.vue'
import store from './store'
import 'bootstrap/dist/js/bootstrap.bundle.min.js';
import { maskDisplayPath } from './utils/pathDisplay';

// CSS files
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import 'splitpanes/dist/splitpanes.css';

import bootstrapDirectives from './directives/bootstrapDirectives';

const app = createApp(App);
app.config.globalProperties.$maskDisplayPath = maskDisplayPath;
app.use(store);
app.use(bootstrapDirectives);
app.mount('#app');
