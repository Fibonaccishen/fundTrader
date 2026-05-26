<script setup>
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getHoldings, updateHolding } from '../api'
import HoldingCard from '../components/HoldingCard.vue'

const holdings = ref([])
const loading = ref(false)
const filter = ref('all')

async function fetchHoldings() {
  loading.value = true
  try {
    const { data } = await getHoldings()
    holdings.value = data
  } catch {
    ElMessage.error('加载持仓失败')
  } finally {
    loading.value = false
  }
}

const filteredHoldings = computed(() => {
  if (filter.value === 'all') return holdings.value
  if (filter.value === 'long_term') return holdings.value.filter(h => h.strategy_type === 'long_term')
  if (filter.value === 'short_term') return holdings.value.filter(h => h.strategy_type === 'short_term')
  return holdings.value
})

const totalPnl = computed(() => {
  return filteredHoldings.value.reduce((sum, h) => sum + Number(h.unrealized_pnl || 0), 0).toFixed(2)
})

async function toggleStrategy(holding) {
  const newType = holding.strategy_type === 'long_term' ? 'short_term' : 'long_term'
  try {
    await updateHolding(holding.id, { strategy_type: newType })
    holding.strategy_type = newType
    ElMessage.success('已切换策略')
  } catch {
    ElMessage.error('切换失败')
  }
}

onMounted(fetchHoldings)
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>持仓列表</h2>
      <div>
        <el-radio-group v-model="filter" size="small">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="long_term">长线</el-radio-button>
          <el-radio-button value="short_term">短线</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <div v-if="filteredHoldings.length" style="margin-bottom:12px;color:#606266">
      共 {{ filteredHoldings.length }} 只基金，累计盈亏：
      <span :class="Number(totalPnl) >= 0 ? 'pnl-positive' : 'pnl-negative'" style="font-weight:600">
        {{ Number(totalPnl) >= 0 ? '+' : '' }}{{ totalPnl }}
      </span>
    </div>

    <div v-loading="loading">
      <HoldingCard v-for="h in filteredHoldings" :key="h.id" :holding="h" @updated="fetchHoldings" />
    </div>

    <el-empty v-if="!loading && !filteredHoldings.length" description="暂无持仓记录" />
  </div>
</template>
