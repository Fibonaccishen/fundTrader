<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { searchFunds, getFundNavByDate, createTransaction } from '../api'

const router = useRouter()

const form = ref({
  fund_code: '',
  transaction_type: 'buy',
  transaction_date: new Date().toISOString().slice(0, 10),
  amount: null,
  nav_at_purchase: null,
  fee: 0,
  platform: 'alipay',
  notes: '',
  strategy_type: 'long_term',
})

const fundOptions = ref([])
const fundLoading = ref(false)
const selectedFund = ref(null)
const submitting = ref(false)

async function handleFundSearch(query) {
  if (!query || query.length < 2) { fundOptions.value = []; return }
  fundLoading.value = true
  try {
    const { data } = await searchFunds(query)
    fundOptions.value = data.map(f => ({
      value: f.code,
      label: `${f.code} - ${f.name} (${f.fund_type || '未知'})`,
      name: f.name, fund_type: f.fund_type,
    }))
  } catch { fundOptions.value = [] }
  finally { fundLoading.value = false }
}

function onFundSelect(val) {
  const item = fundOptions.value.find(f => f.value === val)
  if (item) { selectedFund.value = item; form.value.fund_code = item.value }
}

async function fetchNav() {
  if (!form.value.fund_code) return
  try {
    const date = form.value.transaction_date || new Date().toISOString().slice(0, 10)
    const { data } = await getFundNavByDate(form.value.fund_code, date)
    if (data.unit_nav) form.value.nav_at_purchase = Number(Number(data.unit_nav).toFixed(4))
  } catch { ElMessage.warning('未找到该日期的净值数据，请手动输入') }
}

async function handleSubmit() {
  if (!form.value.fund_code || !form.value.amount || !form.value.nav_at_purchase) {
    ElMessage.warning('请填写完整信息'); return
  }
  submitting.value = true
  try {
    await createTransaction({
      fund_code: form.value.fund_code,
      transaction_type: form.value.transaction_type,
      transaction_date: form.value.transaction_date,
      amount: Number(form.value.amount),
      nav_at_purchase: Number(form.value.nav_at_purchase),
      fee: Number(form.value.fee),
      platform: form.value.platform,
      notes: form.value.notes,
      strategy_type: form.value.strategy_type,
    })
    ElMessage.success('交易录入成功')
    router.push('/holdings')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '录入失败')
  } finally { submitting.value = false }
}
</script>

<template>
  <div style="max-width:560px;margin:0 auto">
    <h2 style="margin-bottom:20px">录入交易</h2>
    <el-form :model="form" label-position="top">
      <el-form-item label="基金搜索">
        <el-select v-model="form.fund_code" filterable remote reserve-keyword
          placeholder="输入基金代码或名称搜索..." :remote-method="handleFundSearch"
          :loading="fundLoading" @change="onFundSelect" style="width:100%">
          <el-option v-for="item in fundOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <div v-if="selectedFund" style="margin-top:8px">
          <el-tag type="success">{{ selectedFund.value }} - {{ selectedFund.name }}</el-tag>
          <el-button size="small" style="margin-left:8px" @click="fetchNav">自动填入净值</el-button>
        </div>
      </el-form-item>

      <el-form-item label="投资策略">
        <el-radio-group v-model="form.strategy_type">
          <el-radio value="long_term">长线定投</el-radio>
          <el-radio value="short_term">短线操作</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="交易类型">
        <el-radio-group v-model="form.transaction_type">
          <el-radio value="buy">买入</el-radio>
          <el-radio value="sell">卖出</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="交易日期">
        <el-date-picker v-model="form.transaction_date" type="date" style="width:100%" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="交易金额（元）">
        <el-input-number v-model="form.amount" :min="0" :precision="2" style="width:100%" placeholder="如 1000.00" />
      </el-form-item>
      <el-form-item label="买入净值">
        <el-input-number v-model="form.nav_at_purchase" :min="0" :precision="6" style="width:100%" placeholder="申购确认时的单位净值" />
      </el-form-item>
      <el-form-item label="手续费（元）">
        <el-input-number v-model="form.fee" :min="0" :precision="2" style="width:100%" />
      </el-form-item>
      <el-form-item label="平台">
        <el-select v-model="form.platform" style="width:100%">
          <el-option label="支付宝" value="alipay" />
          <el-option label="天天基金" value="tiantian" />
          <el-option label="其他" value="other" />
        </el-select>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.notes" placeholder="如：定投第2期" />
      </el-form-item>
      <el-button type="primary" @click="handleSubmit" :loading="submitting" style="width:100%">确认录入</el-button>
    </el-form>
  </div>
</template>
