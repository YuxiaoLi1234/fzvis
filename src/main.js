import { createApp } from 'vue'
import App from './App.vue'
import store from './store'
import bootstrap from 'bootstrap/dist/js/bootstrap.bundle.min.js'

// CSS files
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import 'splitpanes/dist/splitpanes.css';

const app = createApp(App);
app.use(store);
app.mount('#app');

// Initialize all tooltips
document.querySelectorAll('[data-bs-toggle="tooltip"]')
.forEach(tooltip => {
  new bootstrap.Tooltip(tooltip);
});

// Initialize all popovers
document.querySelectorAll('[data-bs-toggle="popover"]')
.forEach(popover => {
  new bootstrap.Popover(popover);
});
