<script setup>
import { ref, onMounted, computed } from 'vue'
import { getDailyPnlCalendar } from '../api'
import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 15000 })

const today = new Date()
const year = ref(today.getFullYear())
const month = ref(today.getMonth() + 1)
const data = ref(null)
const loading = ref(false)

// Detail dialog
const detailDialog = ref(false)
const detailData = ref(null)
const detailLoading = ref(false)

async function load() {
  loading.value = true
  try { const { data: d } = await getDailyPnlCalendar(year.value, month.value); data.value = d }
  catch {} finally { loading.value = false }
}

async function showDetail(date) {
  detailLoading.value = true
  detailDialog.value = true
  detailData.value = null
  try {
    const { data: d } = await api.get('/dashboard/daily-pnl-detail', { params: { query_date: date } })
    detailData.value = d
  } catch {
    detailData.value = { date, total_daily_pnl: 0, details: [], error: true }
  } finally { detailLoading.value = false }
}

function prevMonth() {
  if (month.value === 1) { month.value = 12; year.value-- }
  else month.value--
  load()
}
function nextMonth() {
  if (month.value === 12) { month.value = 1; year.value++ }
  else month.value++
  load()
}

function pnlColor(pnl) {
  if (pnl === null || pnl === undefined) return '#f5f5f5'
  if (pnl > 80) return '#c6e48b'
  if (pnl > 30) return '#d4f0a5'
  if (pnl > 0) return '#e8f5d0'
  if (pnl === 0) return '#f5f5f5'
  if (pnl > -30) return '#ffe0e0'
  if (pnl > -80) return '#ffb8b8'
  return '#ff9090'
}

function pnlTextColor(pnl) {
  if (pnl === null || pnl === undefined) return '#ccc'
  return pnl >= 0 ? '#e53935' : '#4caf50'
}

// Build calendar grid
const calendarGrid = computed(() => {
  if (!data.value) return []
  const days = data.value.days
  const firstDay = new Date(year.value, month.value - 1, 1).getDay()
  const cells = []
  // Empty cells before first day
  for (let i = 0; i < firstDay; i++) cells.push(null)
  // Day cells
  for (const d of days) {
    const day = parseInt(d.date.split('-')[2])
    cells.push({ day, ...d })
  }
  return cells
})

const weekdayLabels = ['日', '一', '二', '三', '四', '五', '六']

onMounted(load)
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>盈亏日历</h2>
      <div style="display:flex;align-items:center;gap:12px">
        <el-button @click="prevMonth" size="small">←</el-button>
        <span style="font-weight:600;font-size:16px">{{ year }} 年 {{ month }} 月</span>
        <el-button @click="nextMonth" size="small">→</el-button>
      </div>
    </div>

    <!-- Monthly summary -->
    <div v-if="data" style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px">
      <div style="background:#fff;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
        <div style="font-size:12px;color:#909399">本月盈亏</div>
        <div :class="data.month_summary.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'" style="font-size:20px;font-weight:600">
          {{ data.month_summary.total_pnl >= 0 ? '+' : '' }}{{ data.month_summary.total_pnl.toFixed(2) }}
        </div>
      </div>
      <div style="background:#fff;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
        <div style="font-size:12px;color:#909399">盈利天数</div>
        <div style="font-size:20px;font-weight:600;color:#e53935">{{ data.month_summary.positive_days }}</div>
      </div>
      <div style="background:#fff;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
        <div style="font-size:12px;color:#909399">亏损天数</div>
        <div style="font-size:20px;font-weight:600;color:#4caf50">{{ data.month_summary.negative_days }}</div>
      </div>
      <div style="background:#fff;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
        <div style="font-size:12px;color:#909399">最佳单日</div>
        <div v-if="data.month_summary.best_day" class="pnl-positive" style="font-size:20px;font-weight:600">
          +{{ data.month_summary.best_day.pnl.toFixed(2) }}
        </div>
        <div v-else style="font-size:14px;color:#ccc">-</div>
      </div>
    </div>

    <!-- Calendar Grid -->
    <div v-loading="loading" style="background:#fff;border-radius:8px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
      <!-- Weekday headers -->
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin-bottom:8px">
        <div v-for="w in weekdayLabels" :key="w" style="text-align:center;font-weight:600;font-size:13px;color:#909399;padding:8px">
          {{ w }}
        </div>
      </div>
      <!-- Day cells -->
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">
        <div v-for="(cell, i) in calendarGrid" :key="i"
          :style="{
            background: cell ? pnlColor(cell.pnl) : 'transparent',
            borderRadius: '6px', padding: '8px 4px', minHeight: '70px',
            cursor: cell && cell.pnl !== null ? 'pointer' : 'default',
            textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center',
          }">
          <template v-if="cell">
            <div style="font-size:13px;font-weight:500">{{ cell.day }}</div>
            <div v-if="cell.pnl !== null" @click.stop="showDetail(cell.date)" :style="{ color: pnlTextColor(cell.pnl), fontSize: '12px', fontWeight: '600', marginTop: '2px' }">
              {{ cell.pnl >= 0 ? '+' : '' }}{{ cell.pnl.toFixed(2) }}
            </div>
            <div v-if="cell.pnl_pct !== null && cell.pnl_pct !== 0" :style="{ color: pnlTextColor(cell.pnl), fontSize: '10px', opacity: 0.7 }">
              {{ cell.pnl_pct >= 0 ? '+' : '' }}{{ cell.pnl_pct.toFixed(2) }}%
            </div>
            <div v-if="cell.pnl === null" style="font-size:10px;color:#ccc">休市</div>
          </template>
        </div>
      </div>

      <!-- Legend -->
      <div style="display:flex;align-items:center;gap:8px;margin-top:16px;justify-content:center;font-size:12px">
        <span style="color:#909399">亏</span>
        <span style="display:inline-block;width:18px;height:18px;border-radius:4px;background:#ff9090"></span>
        <span style="display:inline-block;width:18px;height:18px;border-radius:4px;background:#ffb8b8"></span>
        <span style="display:inline-block;width:18px;height:18px;border-radius:4px;background:#ffe0e0"></span>
        <span style="display:inline-block;width:18px;height:18px;border-radius:4px;background:#f5f5f5;border:1px solid #e0e0e0"></span>
        <span style="display:inline-block;width:18px;height:18px;border-radius:4px;background:#e8f5d0"></span>
        <span style="display:inline-block;width:18px;height:18px;border-radius:4px;background:#d4f0a5"></span>
        <span style="display:inline-block;width:18px;height:18px;border-radius:4px;background:#c6e48b"></span>
        <span style="color:#909399">盈</span>
      </div>
    </div>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailDialog" :title="'每日盈亏明细' + (detailData ? ' - ' + detailData.date : '')" width="550px">
      <div v-loading="detailLoading">
        <div v-if="detailData" style="text-align:center;margin-bottom:16px">
          <span :class="detailData.total_daily_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'" style="font-size:22px;font-weight:600">
            {{ detailData.total_daily_pnl >= 0 ? '+' : '' }}{{ detailData.total_daily_pnl.toFixed(2) }}
          </span>
          <span style="font-size:14px;color:#909399;margin-left:4px">当日总盈亏</span>
        </div>
        <el-table :data="detailData?.details || []" stripe size="small" v-if="detailData">
          <el-table-column prop="fund_name" label="基金" />
          <el-table-column label="份额" width="90">
            <template #default="{ row }">{{ row.shares.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="昨收净值" width="100">
            <template #default="{ row }">{{ row.yesterday_nav ? row.yesterday_nav.toFixed(4) : '-' }}</template>
          </el-table-column>
          <el-table-column label="今日净值" width="100">
            <template #default="{ row }">{{ row.today_nav.toFixed(4) }}</template>
          </el-table-column>
          <el-table-column label="当日盈亏" width="110">
            <template #default="{ row }">
              <span :class="row.daily_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'">
                {{ row.daily_pnl >= 0 ? '+' : '' }}{{ row.daily_pnl.toFixed(2) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="detailData && !detailData.details.length" style="text-align:center;color:#909399">该日无持仓记录</div>
      </div>
    </el-dialog>
  </div>
</template>
