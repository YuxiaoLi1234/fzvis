import { createApp } from 'vue'
import App from './App.vue'
import store from './store'
import bootstrap from 'bootstrap/dist/js/bootstrap.bundle.min.js'

// CSS files
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';

createApp(App).use(store).mount('#app')

// Initialize all tooltips
document.querySelectorAll('[data-bs-toggle="tooltip"]')
.forEach(tooltip => {
  new bootstrap.Tooltip(tooltip)
})
