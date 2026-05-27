import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Holdings from '../views/Holdings.vue'
import AddTransaction from '../views/AddTransaction.vue'
import MarketData from '../views/MarketData.vue'
import FundDetail from '../views/FundDetail.vue'
import Watchlist from '../views/Watchlist.vue'
import PnlCalendar from '../views/PnlCalendar.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/holdings', name: 'Holdings', component: Holdings },
  { path: '/add-transaction', name: 'AddTransaction', component: AddTransaction },
  { path: '/watchlist', name: 'Watchlist', component: Watchlist },
  { path: '/calendar', name: 'PnlCalendar', component: PnlCalendar },
  { path: '/market', name: 'MarketData', component: MarketData },
  { path: '/fund/:code', name: 'FundDetail', component: FundDetail },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
