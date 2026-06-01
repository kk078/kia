import { createApp } from 'vue'
import App from './App.vue'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './style.css'
import router from './router'

const app = createApp(App)
app.use(router)
app.mount('#app')
