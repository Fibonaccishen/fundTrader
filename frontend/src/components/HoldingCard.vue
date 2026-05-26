<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createTransaction, getFundNavByDate, updateHolding } from '../api'

const emit = defineEmits(['updated'])
const router = useRouter()
const props = defineProps({ holding: Object })

const pnlClass = computed(() => {
  if (!props.holding.unrealized_pnl) return ''
  return Number(props.holding.unrealized_pnl) >= 0 ? 'pnl-positive' : 'pnl-negative'
})
const pnlSign = computed(() => {
  if (!props.holding.unrealized_pnl) return ''
  return Number(props.holding.unrealized_pnl) >= 0 ? '+' : ''
})

function navLabel(h) {
  if (h.est_nav && h.current_nav && h.est_nav !== h.current_nav) {
    return `估算: ${Number(h.est_nav).toFixed(4)}`
  }
  return h.current_nav ? `净值: ${Number(h.current_nav).toFixed(4)}` : '暂无净值'
}

function goDetail() {
  router.push(`/fund/${props.holding.fund_code}`)
}

async function toggleStrategy(e) {
  e.stopPropagation()
  const newType = props.holding.strategy_type === 'long_term' ? 'short_term' : 'long_term'
  try {
    await updateHolding(props.holding.id, { strategy_type: newType })
    props.holding.strategy_type = newType
    ElMessage.success('已切换为' + (newType === 'long_term' ? '长线' : '短线'))
  } catch { ElMessage.error('切换失败') }
}

// Quick trade dialog
const tradeDialog = ref(false)
const tradeType = ref('buy')
const tradeForm = ref({
  transaction_date: new Date().toISOString().slice(0, 10),
  amount: null,
  nav_at_purchase: null,
  fee: 0,
  strategy_type: props.holding.strategy_type || 'long_term',
})
const tradeSubmitting = ref(false)

async function openTrade(type, e) {
  e.stopPropagation()
  tradeType.value = type
  const today = new Date().toISOString().slice(0, 10)
  tradeForm.value = {
    transaction_date: today,
    amount: null,
    nav_at_purchase: null,
    fee: 0,
    strategy_type: props.holding.strategy_type || 'long_term',
  }
  tradeDialog.value = true
  // Auto-fetch NAV for today
  fetchNavForTrade()
}

async function fetchNavForTrade() {
  try {
    const { data } = await getFundNavByDate(props.holding.fund_code, tradeForm.value.transaction_date)
    if (data.unit_nav) tradeForm.value.nav_at_purchase = Number(Number(data.unit_nav).toFixed(4))
  } catch {}
}

async function submitTrade() {
  if (!tradeForm.value.amount || !tradeForm.value.nav_at_purchase) {
    ElMessage.warning('请填写金额和净值')
    return
  }
  tradeSubmitting.value = true
  try {
    await createTransaction({
      fund_code: props.holding.fund_code,
      transaction_type: tradeType.value,
      transaction_date: tradeForm.value.transaction_date,
      amount: Number(tradeForm.value.amount),
      nav_at_purchase: Number(tradeForm.value.nav_at_purchase),
      fee: Number(tradeForm.value.fee),
      platform: 'alipay',
      strategy_type: tradeForm.value.strategy_type,
    })
    ElMessage.success(tradeType.value === 'buy' ? '加仓成功' : '减仓成功')
    tradeDialog.value = false
    emit('updated')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    tradeSubmitting.value = false
  }
}
</script>

<template>
  <div
    class="holding-card"
    @click="goDetail"
    style="cursor:pointer;background:#fff;border-radius:8px;padding:16px 20px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);display:flex;justify-content:space-between;align-items:center;transition:box-shadow 0.2s"
    onmouseover="this.style.boxShadow='0 2px 8px rgba(0,0,0,0.15)'"
    onmouseout="this.style.boxShadow='0 1px 3px rgba(0,0,0,0.08)'"
  >
    <div style="flex:1">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <span style="font-weight:600;font-size:15px;color:#409EFF">{{ holding.fund_name }}</span>
        <el-tag :type="holding.strategy_type === 'long_term' ? 'success' : 'warning'" size="small">
          {{ holding.strategy_type === 'long_term' ? '长线' : '短线' }}
        </el-tag>
        <el-button size="small" text @click="toggleStrategy($event)">切换</el-button>
      </div>
      <div style="font-size:13px;color:#909399">
        <span>{{ holding.fund_code }}</span>
        <span style="margin-left:12px">{{ navLabel(holding) }}</span>
        <span v-if="holding.daily_change_pct" style="margin-left:12px" :class="Number(holding.daily_change_pct) >= 0 ? 'pnl-positive' : 'pnl-negative'">
          日 {{ Number(holding.daily_change_pct) >= 0 ? '+' : '' }}{{ Number(holding.daily_change_pct).toFixed(2) }}%
        </span>
      </div>
    </div>
    <div style="text-align:right;display:flex;align-items:center;gap:10px">
      <div>
        <div style="font-size:18px;font-weight:600" :class="pnlClass">
          {{ pnlSign }}{{ Number(holding.unrealized_pnl || 0).toFixed(2) }}
        </div>
        <div style="font-size:13px" :class="pnlClass">
          市值 {{ Number(holding.market_value || 0).toFixed(2) }}
        </div>
        <div style="font-size:12px;color:#909399">
          成本 {{ Number(holding.total_cost || 0).toFixed(2) }} →
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:4px">
        <el-button size="small" type="success" @click="openTrade('buy', $event)">加仓</el-button>
        <el-button size="small" type="danger" @click="openTrade('sell', $event)">减仓</el-button>
      </div>
    </div>
  </div>

  <!-- Quick Trade Dialog -->
  <el-dialog v-model="tradeDialog" :title="(tradeType === 'buy' ? '加仓' : '减仓') + ' - ' + holding.fund_name" width="420px" @click.stop>
    <el-form :model="tradeForm" label-position="top">
      <el-form-item label="策略">
        <el-radio-group v-model="tradeForm.strategy_type">
          <el-radio value="long_term">长线</el-radio>
          <el-radio value="short_term">短线</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="日期">
        <div style="display:flex;gap:8px">
          <el-date-picker v-model="tradeForm.transaction_date" type="date" value-format="YYYY-MM-DD" style="flex:1" />
          <el-button @click="fetchNavForTrade" :loading="tradeSubmitting">查净值</el-button>
        </div>
      </el-form-item>
      <el-form-item label="金额（元）">
        <el-input-number v-model="tradeForm.amount" :min="0" :precision="2" style="width:100%" />
      </el-form-item>
      <el-form-item label="净值">
        <el-input-number v-model="tradeForm.nav_at_purchase" :min="0" :precision="6" style="width:100%" />
      </el-form-item>
      <el-form-item label="手续费">
        <el-input-number v-model="tradeForm.fee" :min="0" :precision="2" style="width:100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="tradeDialog = false">取消</el-button>
      <el-button :type="tradeType === 'buy' ? 'success' : 'danger'" @click="submitTrade" :loading="tradeSubmitting">
        {{ tradeType === 'buy' ? '确认加仓' : '确认减仓' }}
      </el-button>
    </template>
  </el-dialog>
</template>
