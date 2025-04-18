import { createApp } from 'vue'
import TDesign from 'tdesign-vue-next';
import App from './App.vue'
import store from './store'; // import the store
// import axios from 'axios'

import 'tdesign-vue-next/es/style/index.css';

const app = createApp(App)
app.use(TDesign)
app.use(store); // use the store
app.mount('#app')

// axios.defaults.headers.common['Content-Type'] = 'application/x-www-form-urlencoded'
// axios.defaults.headers.common['Access-Control-Allow-Origin'] = '*';
