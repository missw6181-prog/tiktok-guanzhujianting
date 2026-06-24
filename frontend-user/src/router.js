import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Layout from './views/Layout.vue'
import Bots from './views/Bots.vue'
import Groups from './views/Groups.vue'
import SignKeys from './views/SignKeys.vue'
import Tasks from './views/Tasks.vue'
import Events from './views/Events.vue'
import Overview from './views/Overview.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    {
      path: '/',
      component: Layout,
      redirect: '/overview',
      children: [
        { path: 'overview', name: 'overview', component: Overview },
        { path: 'bots', name: 'bots', component: Bots },
        { path: 'groups', name: 'groups', component: Groups },
        { path: 'tasks', name: 'tasks', component: Tasks },
        { path: 'sign-keys', name: 'sign-keys', component: SignKeys },
        { path: 'events', name: 'events', component: Events },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'login' && !token) return '/login'
  if (to.name === 'login' && token) return '/overview'
})

export default router
