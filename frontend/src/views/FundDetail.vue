<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getFundDetail, getFundNavHistory, getTransactions, updateTransaction, deleteTransaction } from '../api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent])

const route = useRoute()
const router = useRouter()

const code = route.params.code
const fund = ref(null)
const transactions = ref([])
const navHistory = ref([])
const loading = ref(true)
const chartKey = ref(0)

const editDialog = ref(false)
const editingTxn = ref(null)
const editForm = ref({
  transaction_type: 'buy',
  transaction_date: '',
  amount: null,
  nav_at_purchase: null,
  fee: 0,
})

const chartOption = computed(() => {
  const dates = navHistory.value.map(n => n.nav_date)
  const navs = navHistory.value.map(n => n.unit_nav ? Number(n.unit_nav) : null)

  // Build buy/sell markers from transaction data
  const buyMarks = []
  const sellMarks = []
  const dateSet = new Map(dates.map((d, i) => [d, i]))
  for (const t of transactions.value) {
    const idx = dateSet.get(t.transaction_date)
    if (idx === undefined) continue
    const nav = navs[idx]
    if (nav === null || nav === undefined) continue
    const mark = {
      name: t.transaction_type === 'buy' ? '买入' : '卖出',
      coord: [t.transaction_date, nav],
      value: '¥' + Number(t.amount).toFixed(0),
      symbol: 'pin',
      symbolSize: 40,
    }
    if (t.transaction_type === 'buy') {
      mark.itemStyle = { color: '#e53935' }
      buyMarks.push(mark)
    } else {
      mark.itemStyle = { color: '#4caf50' }
      sellMarks.push(mark)
    }
  }

  return {
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        let html = params[0].axisValue + '<br/>'
        for (const p of params) {
          if (p.seriesType === 'line') {
            html += `净值: ${p.value}<br/>`
          }
        }
        return html
      }
    },
    grid: { left: 60, right: 30, top: 30, bottom: 60 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '净值', scale: true },
    dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 0 }],
    series: [
      {
        name: '单位净值',
        type: 'line',
        data: navs,
        smooth: true,
        itemStyle: { color: '#e53935' },
        areaStyle: { color: 'rgba(229,57,53,0.08)' },
        markPoint: {
          data: [...buyMarks, ...sellMarks],
        },
      },
    ],
  }
})

async function load() {
  loading.value = true
  try {
    const [fundRes, txnRes, navRes] = await Promise.all([
      getFundDetail(code),
      getTransactions({ fund_id: null, limit: 200 }),
      getFundNavHistory(code, 180),
    ])
    fund.value = fundRes.data
    transactions.value = txnRes.data.filter(t => t.fund_code === code)
    navHistory.value = navRes.data
    chartKey.value++
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function openEdit(txn) {
  editingTxn.value = txn
  editForm.value = {
    transaction_type: txn.transaction_type,
    transaction_date: txn.transaction_date,
    amount: Number(txn.amount),
    nav_at_purchase: Number(txn.nav_at_purchase),
    fee: Number(txn.fee || 0),
  }
  editDialog.value = true
}

async function saveEdit() {
  try {
    await updateTransaction(editingTxn.value.id, editForm.value)
    ElMessage.success('已更新')
    editDialog.value = false
    await load()
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

async function removeTxn(txn) {
  try {
    await ElMessageBox.confirm(`删除 ${txn.transaction_date} 的${txn.transaction_type === 'buy' ? '买入' : '卖出'}记录 ${txn.amount}元？`, '确认删除', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await deleteTransaction(txn.id)
    ElMessage.success('已删除')
    await load()
  } catch {}
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
      <el-button @click="router.back()">← 返回</el-button>
      <h2 style="margin:0">{{ fund?.name || code }}</h2>
      <el-tag>{{ fund?.fund_type }}</el-tag>
      <span style="color:#909399;font-size:14px">{{ code }}</span>
    </div>

    <!-- NAV Chart -->
    <div style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:20px">
      <h3 style="margin:0 0 12px">净值走势（近180天）</h3>
      <v-chart :option="chartOption" :key="chartKey" style="height:350px" autoresize />
    </div>

    <!-- Transaction History -->
    <div style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
      <h3 style="margin:0 0 12px">交易记录</h3>
      <el-table :data="transactions" stripe>
        <el-table-column prop="transaction_date" label="日期" width="120" />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.transaction_type === 'buy' ? 'success' : 'danger'" size="small">
              {{ row.transaction_type === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="120">
          <template #default="{ row }">¥{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="净值" width="100">
          <template #default="{ row }">{{ Number(row.nav_at_purchase).toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="份额" width="100">
          <template #default="{ row }">{{ Number(row.shares).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="手续费" width="80">
          <template #default="{ row }">¥{{ Number(row.fee || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="备注">
          <template #default="{ row }">{{ row.notes || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeTxn(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!transactions.length" description="暂无交易记录" />
    </div>

    <!-- Edit Dialog -->
    <el-dialog v-model="editDialog" title="编辑交易" width="450px">
      <el-form :model="editForm" label-position="top" v-if="editingTxn">
        <el-form-item label="交易类型">
          <el-radio-group v-model="editForm.transaction_type">
            <el-radio value="buy">买入</el-radio>
            <el-radio value="sell">卖出</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="editForm.transaction_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="editForm.amount" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="净值">
          <el-input-number v-model="editForm.nav_at_purchase" :min="0" :precision="6" style="width:100%" />
        </el-form-item>
        <el-form-item label="手续费">
          <el-input-number v-model="editForm.fee" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
