import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 15000 })

export function searchFunds(keyword) {
  return api.get('/funds/search', { params: { keyword } })
}
export function getFundDetail(code) {
  return api.get(`/funds/${code}`)
}
export function getFundNavHistory(code, days = 30) {
  return api.get(`/funds/${code}/nav-history`, { params: { days } })
}
export function getFundNavByDate(code, query_date) {
  return api.get(`/funds/${code}/nav-by-date`, { params: { query_date } })
}
export function getHoldings(status = 'active') {
  return api.get('/holdings', { params: { status } })
}
export function updateHolding(id, data) {
  return api.patch(`/holdings/${id}`, data)
}
export function getTransactions(params) {
  return api.get('/transactions', { params })
}
export function createTransaction(data) {
  return api.post('/transactions', data)
}
export function deleteTransaction(id) {
  return api.delete(`/transactions/${id}`)
}
export function updateTransaction(id, data) {
  return api.patch(`/transactions/${id}`, data)
}
export function getDashboardSummary() {
  return api.get('/dashboard/summary')
}
export function getPnlTrend(days = 30) {
  return api.get('/dashboard/pnl-trend', { params: { days } })
}
export function getMarketIndices() {
  return api.get('/dashboard/market-indices')
}
export function getSectors() {
  return api.get('/dashboard/sectors')
}
export function getRiskAnalysis() {
  return api.get('/dashboard/risk-analysis')
}
export function getMarketValuation() {
  return api.get('/dashboard/market-valuation')
}
export function getDailyPnlCalendar(year, month) {
  return api.get('/dashboard/daily-pnl-calendar', { params: { year, month } })
}
export function getAgentSettings() {
  return api.get('/agent/settings')
}
export function updateAgentSettings(data) {
  return api.put('/agent/settings', data)
}
export function getDailyAnalysis() {
  return api.get('/agent/analysis')
}
export function triggerJob(name) {
  return api.post(`/scheduler/trigger/${name}`)
}
export default api
