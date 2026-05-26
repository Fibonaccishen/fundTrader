<script setup>
import { onMounted, ref } from 'vue'
import { getMarketIndices, getSectors } from '../api'
import { ElMessage } from 'element-plus'

const indices = ref([])
const sectors = ref([])
const loading = ref(false)

async function fetchMarketData() {
  loading.value = true
  try {
    const [iRes, sRes] = await Promise.all([getMarketIndices(), getSectors()])
    indices.value = iRes.data
    sectors.value = sRes.data
  } catch {
    ElMessage.error('加载行情数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchMarketData)
</script>

<template>
  <div v-loading="loading">
    <h2>市场行情</h2>

    <h3 style="margin-top:20px;margin-bottom:12px">主要指数</h3>
    <el-table :data="indices" stripe style="width:100%">
      <el-table-column prop="index_name" label="指数" />
      <el-table-column label="收盘价">
        <template #default="{ row }">
          {{ row.close_price ? Number(row.close_price).toFixed(2) : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="涨跌幅">
        <template #default="{ row }">
          <span :class="Number(row.change_pct) >= 0 ? 'pnl-positive' : 'pnl-negative'">
            {{ row.change_pct ? (Number(row.change_pct) >= 0 ? '+' : '') + Number(row.change_pct).toFixed(2) + '%' : '-' }}
          </span>
        </template>
      </el-table-column>
    </el-table>

    <h3 style="margin-top:24px;margin-bottom:12px">热门板块</h3>
    <el-table :data="sectors" stripe style="width:100%">
      <el-table-column prop="sector_name" label="板块" />
      <el-table-column label="涨跌幅" width="200">
        <template #default="{ row }">
          <span :class="Number(row.change_pct) >= 0 ? 'pnl-positive' : 'pnl-negative'">
            {{ row.change_pct ? (Number(row.change_pct) >= 0 ? '+' : '') + Number(row.change_pct).toFixed(2) + '%' : '-' }}
          </span>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!indices.length && !sectors.length" description="暂无行情数据，等待定时任务采集..." />
  </div>
</template>
