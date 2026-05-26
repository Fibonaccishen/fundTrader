import { defineStore } from 'pinia'
import { getDashboardSummary, getHoldings } from '../api'

export const usePortfolioStore = defineStore('portfolio', {
  state: () => ({
    summary: null,
    holdings: [],
    loading: false,
  }),
  actions: {
    async fetchSummary() {
      try {
        const { data } = await getDashboardSummary()
        this.summary = data
      } catch (e) {
        console.error('Failed to fetch summary:', e)
      }
    },
    async fetchHoldings() {
      this.loading = true
      try {
        const { data } = await getHoldings()
        this.holdings = data
      } catch (e) {
        console.error('Failed to fetch holdings:', e)
      } finally {
        this.loading = false
      }
    },
  },
})
