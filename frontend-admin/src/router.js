import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Layout from './views/Layout.vue'
import Users from './views/Users.vue'
import Stats from './views/Stats.vue'
import Streamers from './views/Streamers.vue'
import SignKeys from './views/SignKeys.vue'
import Bots from './views/Bots.vue'
import Groups from './views/Groups.vue'

const router = createRouter({
  history: createWebHistory('/admin/'),
  routes: [
    { path: '/login', name: 'login', component: Login },
    {
      path: '/',
      component: Layout,
      redirect: '/users',
      children: [
        { path: 'users', name: 'users', component: Users },
        { path: 'streamers', name: 'streamers', component: Streamers },
        { path: 'sign-keys', name: 'sign-keys', component: SignKeys },
        { path: 'bots', name: 'bots', component: Bots },
        { path: 'groups', name: 'groups', component: Groups },
        { path: 'stats', name: 'stats', component: Stats },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('admin_token')
  if (to.name !== 'login' && !token) return '/login'
  if (to.name === 'login' && token) return '/users'
})

export default router
