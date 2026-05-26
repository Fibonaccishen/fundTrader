<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { searchFunds, getFundNavByDate } from '../api'
import axios from 'axios'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, GridComponent])

const router = useRouter()
const api = axios.create({ baseURL: '/api', timeout: 15000 })
const items = ref([])
const loading = ref(false)
const addDialog = ref(false)
const addForm = ref({ fund_code: '', notes: '' })
const fundOptions = ref([])
const fundSearchLoading = ref(false)
const addSubmitting = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/watchlist')
    items.value = data
  } catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

async function searchFundsLocal(query) {
  if (!query || query.length < 2) { fundOptions.value = []; return }
  fundSearchLoading.value = true
  try {
    const { data } = await searchFunds(query)
    fundOptions.value = data.map(f => ({
      value: f.code, label: `${f.code} - ${f.name} (${f.fund_type || ''})`,
    }))
  } catch { fundOptions.value = [] }
  finally { fundSearchLoading.value = false }
}

async function addItem() {
  if (!addForm.value.fund_code) { ElMessage.warning('请选择基金'); return }
  addSubmitting.value = true
  try {
    await api.post('/watchlist', addForm.value)
    ElMessage.success('已添加')
    addDialog.value = false
    addForm.value = { fund_code: '', notes: '' }
    await load()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') }
  finally { addSubmitting.value = false }
}

async function removeItem(item) {
  try {
    await ElMessageBox.confirm(`移除 ${item.fund_name}？`, '确认', { type: 'warning' })
    await api.delete(`/watchlist/${item.id}`)
    ElMessage.success('已移除')
    await load()
  } catch {}
}

function buyNow(item) {
  router.push({ path: '/add-transaction', query: { code: item.fund_code } })
}

function miniChartOption(item) {
  const dates = item.nav_trend.map(n => n.date)
  const navs = item.nav_trend.map(n => n.nav)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 0, right: 0, top: 4, bottom: 4 },
    xAxis: { type: 'category', data: dates, show: false },
    yAxis: { type: 'value', show: false, scale: true },
    series: [{
      type: 'line', data: navs, smooth: true,
      showSymbol: false, lineStyle: { width: 1.5 },
      itemStyle: { color: navs.length > 0 && navs[navs.length-1] >= navs[0] ? '#e53935' : '#4caf50' },
      areaStyle: { color: navs.length > 0 && navs[navs.length-1] >= navs[0] ? 'rgba(229,57,53,0.05)' : 'rgba(76,175,80,0.05)' },
    }],
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>关注列表</h2>
      <el-button type="primary" @click="addDialog = true">+ 添加关注</el-button>
    </div>

    <div v-loading="loading">
      <div v-for="item in items" :key="item.id"
        style="background:#fff;border-radius:8px;padding:16px 20px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);display:flex;align-items:center;gap:16px">
        <!-- Mini chart -->
        <div v-if="item.nav_trend.length" style="width:120px;height:50px;flex-shrink:0">
          <v-chart :option="miniChartOption(item)" style="height:50px" autoresize />
        </div>
        <div v-else style="width:120px;height:50px;flex-shrink:0;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:12px">
          暂无数据
        </div>
        <!-- Info -->
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:15px">{{ item.fund_name }}</div>
          <div style="font-size:13px;color:#909399">
            {{ item.fund_code }}
            <span v-if="item.fund_type" style="margin-left:8px">{{ item.fund_type }}</span>
            <span v-if="item.latest_nav" style="margin-left:8px;color:#409EFF">净值 {{ item.latest_nav.toFixed(4) }}</span>
          </div>
          <div v-if="item.notes" style="font-size:12px;color:#909399;margin-top:4px">{{ item.notes }}</div>
        </div>
        <!-- Actions -->
        <div style="display:flex;gap:8px;flex-shrink:0">
          <el-button size="small" type="success" @click="buyNow(item)">买入</el-button>
          <el-button size="small" type="danger" @click="removeItem(item)">移除</el-button>
        </div>
      </div>
      <el-empty v-if="!items.length" description="暂无关注基金，点击上方按钮添加" />
    </div>

    <!-- Add Dialog -->
    <el-dialog v-model="addDialog" title="添加关注基金" width="420px">
      <el-form label-position="top">
        <el-form-item label="搜索基金">
          <el-select v-model="addForm.fund_code" filterable remote reserve-keyword
            placeholder="输入代码或名称搜索..." :remote-method="searchFundsLocal"
            :loading="fundSearchLoading" style="width:100%">
            <el-option v-for="f in fundOptions" :key="f.value" :label="f.label" :value="f.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注（可选）">
          <el-input v-model="addForm.notes" placeholder="如：观察中，等回调再买" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialog = false">取消</el-button>
        <el-button type="primary" @click="addItem" :loading="addSubmitting">确认添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>
