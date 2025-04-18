import { createApp } from 'vue'
import App from './App.vue';
import bootstrap from 'bootstrap/dist/js/bootstrap.bundle.min.js'
// import axios from 'axios'

import 'bootstrap/dist/css/bootstrap.min.css';

createApp(App).mount('#app')


// axios.defaults.headers.common['Content-Type'] = 'application/x-www-form-urlencoded'
// axios.defaults.headers.common['Access-Control-Allow-Origin'] = '*';

// // Initialize all tooltips
document.querySelectorAll('[data-bs-toggle="tooltip"]')
.forEach(tooltip => {
  new bootstrap.Tooltip(tooltip)
})

// // Initialize all popovers
// document.querySelectorAll('[data-bs-toggle="popover"]')
//   .forEach(popover => {
//     new Popover(popover)
// })

// // Initialize all dropdowns
// document.querySelectorAll('[data-bs-toggle="dropdown"]')
//   .forEach(dropdown => {
//     new Dropdown(dropdown)
// })
