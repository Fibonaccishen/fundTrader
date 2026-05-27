<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboardSummary, getPnlTrend, getAgentSettings, updateAgentSettings, getDailyAnalysis, triggerJob, getRiskAnalysis, getMarketValuation } from '../api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const summary = ref(null)
const holdings = ref([])
const trendDays = ref(30)
const chartKey = ref(0)
const risk = ref(null)
const valuation = ref([])

// Settings
const settingsDialog = ref(false)
const settings = ref({
  total_capital: null,
  remaining_cash: null,
  monthly_contribution: null,
  risk_tolerance: 'medium',
  investment_goal: '',
  notes: '',
})
const settingsSaving = ref(false)

// Analysis
const analysisDialog = ref(false)
const analysis = ref(null)
const analysisLoading = ref(false)

async function fetchRisk() {
  try { const { data } = await getRiskAnalysis(); risk.value = data } catch {}
}
async function fetchValuation() {
  try { const { data } = await getMarketValuation(); valuation.value = data } catch {}
}

async function fetchData() {
  try {
    const [sRes] = await Promise.all([getDashboardSummary(), fetchPnlTrend(), fetchRisk(), fetchValuation()])
    summary.value = sRes.data
    updateChart()
  } catch (e) { console.error(e) }
}

async function fetchPnlTrend() {
  try {
    const { data } = await getPnlTrend(trendDays.value)
    holdings.value = data
  } catch {}
}

const pnlChartOption = ref({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 20, top: 20, bottom: 30 },
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value', axisLabel: { formatter: '{value}元' } },
  series: [
    { name: '市值', type: 'line', data: [], smooth: true, itemStyle: { color: '#409EFF' } },
    { name: '成本', type: 'line', data: [], smooth: true, itemStyle: { color: '#909399' }, lineStyle: { type: 'dashed' } },
  ],
})

const strategyPieOption = ref({})
const fundPieOption = ref({})

function updateChart() {
  const dates = [], values = [], costs = []
  for (const item of holdings.value) {
    dates.push(item.date); values.push(item.total_market_value); costs.push(item.total_cost)
  }
  pnlChartOption.value.xAxis.data = dates
  pnlChartOption.value.series[0].data = values
  pnlChartOption.value.series[1].data = costs
  chartKey.value++

  // Pie charts
  if (summary.value) {
    const sa = summary.value.strategy_allocation || {}
    strategyPieOption.value = {
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
        data: [
          { value: sa.long_term || 0, name: '长线', itemStyle: { color: '#67c23a' } },
          { value: sa.short_term || 0, name: '短线', itemStyle: { color: '#e6a23c' } },
        ],
        label: { formatter: '{b}\n{d}%' },
      }],
    }
    const fa = summary.value.fund_allocation || []
    fundPieOption.value = {
      tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      series: [{
        type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
        data: fa.map(f => ({ value: f.market_value, name: f.name.length > 10 ? f.name.slice(0,10)+'...' : f.name })),
        label: { formatter: '{b}\n{d}%', fontSize: 10 },
      }],
    }
  }
}

async function refreshTrend() { await fetchPnlTrend(); updateChart() }

// Settings
async function openSettings() {
  try {
    const { data } = await getAgentSettings()
    settings.value = {
      total_capital: data.total_capital || null,
      remaining_cash: data.remaining_cash || 0,
      monthly_contribution: data.monthly_contribution || null,
      stop_profit_pct: data.stop_profit_pct ?? null,
      stop_loss_pct: data.stop_loss_pct ?? null,
      risk_tolerance: data.risk_tolerance || 'medium',
      investment_goal: data.investment_goal || '',
      personal_opinion: data.personal_opinion || '',
      notes: data.notes || '',
    }
  } catch {}
  settingsDialog.value = true
}

async function saveSettings() {
  settingsSaving.value = true
  try {
    await updateAgentSettings({
      total_capital: settings.value.total_capital,
      monthly_contribution: settings.value.monthly_contribution,
      stop_profit_pct: settings.value.stop_profit_pct,
      stop_loss_pct: settings.value.stop_loss_pct,
      risk_tolerance: settings.value.risk_tolerance,
      investment_goal: settings.value.investment_goal,
      personal_opinion: settings.value.personal_opinion,
      notes: settings.value.notes,
    })
    ElMessage.success('设置已保存')
    settingsDialog.value = false
  } catch { ElMessage.error('保存失败') }
  finally { settingsSaving.value = false }
}

function copyPrompt() {
  navigator.clipboard.writeText(analysis.value.analysis_prompt)
  ElMessage.success('已复制')
}

// Refresh all data then analyze
const refreshing = ref(false)
async function refreshAndAnalyze() {
  refreshing.value = true
  try {
    // Trigger all data collection jobs in parallel
    await Promise.all([
      triggerJob('update_nav'),
      triggerJob('market_indices'),
      triggerJob('sector_data'),
      triggerJob('news'),
    ])
    ElMessage.success('数据刷新完成')
    await runAnalysis()
  } catch { ElMessage.error('数据刷新失败') }
  finally { refreshing.value = false }
}

// Analysis
async function runAnalysis() {
  analysisLoading.value = true
  try {
    const { data } = await getDailyAnalysis()
    analysis.value = data
    analysisDialog.value = true
  } catch { ElMessage.error('分析失败，请先设置本金信息') }
  finally { analysisLoading.value = false }
}

// Also refresh dashboard summary
async function refreshDashboard() {
  await fetchData()
  ElMessage.success('概览已刷新')
}

onMounted(async () => { await fetchData() })
</script>

<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>投资概览</h2>
      <div style="display:flex;gap:8px">
        <el-button @click="refreshDashboard">刷新概览</el-button>
        <el-button @click="openSettings">资金设置</el-button>
        <el-button type="warning" @click="refreshAndAnalyze" :loading="refreshing">刷新数据+分析</el-button>
        <el-button type="primary" @click="runAnalysis" :loading="analysisLoading">一键分析</el-button>
      </div>
    </div>

    <!-- Summary Cards -->
    <div v-if="summary" class="summary-cards">
      <div class="summary-card">
        <div class="label">持仓成本</div>
        <div class="value">{{ Number(summary.total_cost).toLocaleString() }}</div>
      </div>
      <div class="summary-card">
        <div class="label">当前市值</div>
        <div class="value">{{ Number(summary.total_market_value).toLocaleString() }}</div>
      </div>
      <div class="summary-card">
        <div class="label">累计盈亏（实时）</div>
        <div class="value" :class="Number(summary.total_unrealized_pnl) >= 0 ? 'pnl-positive' : 'pnl-negative'">
          {{ Number(summary.total_unrealized_pnl) >= 0 ? '+' : '' }}{{ Number(summary.total_unrealized_pnl).toFixed(2) }}
        </div>
      </div>
      <div class="summary-card">
        <div class="label">昨日收盘盈亏</div>
        <div class="value" :class="Number(summary.yesterday_unrealized_pnl) >= 0 ? 'pnl-positive' : 'pnl-negative'" style="font-size:20px">
          {{ Number(summary.yesterday_unrealized_pnl) >= 0 ? '+' : '' }}{{ Number(summary.yesterday_unrealized_pnl).toFixed(2) }}
        </div>
        <div style="font-size:11px;color:#c0c4cc">支付宝同款</div>
      </div>
      <div class="summary-card">
        <div class="label">收益率</div>
        <div class="value" :class="Number(summary.total_pnl_pct) >= 0 ? 'pnl-positive' : 'pnl-negative'">
          {{ Number(summary.total_pnl_pct) >= 0 ? '+' : '' }}{{ Number(summary.total_pnl_pct).toFixed(2) }}%
        </div>
      </div>
      <div class="summary-card">
        <div class="label">今日盈亏（估）</div>
        <div class="value" :class="Number(summary.today_pnl) >= 0 ? 'pnl-positive' : 'pnl-negative'">
          {{ Number(summary.today_pnl) >= 0 ? '+' : '' }}{{ Number(summary.today_pnl).toFixed(2) }}
        </div>
      </div>
      <div class="summary-card">
        <div class="label">持仓数量</div>
        <div class="value">{{ summary.holding_count }} 只</div>
      </div>
      <div class="summary-card">
        <div class="label">剩余可用资金</div>
        <div class="value" style="color:#409EFF">{{ Number(summary.remaining_cash || 0).toLocaleString() }}</div>
      </div>
    </div>

    <!-- Pie Charts -->
    <div v-if="summary" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px">
      <div style="background:#fff;border-radius:8px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
        <div style="font-weight:600;margin-bottom:8px;text-align:center">策略分布</div>
        <v-chart :option="strategyPieOption" style="height:220px" autoresize />
      </div>
      <div style="background:#fff;border-radius:8px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
        <div style="font-weight:600;margin-bottom:8px;text-align:center">基金持仓占比</div>
        <v-chart :option="fundPieOption" style="height:220px" autoresize />
      </div>
    </div>

    <!-- P&L Chart -->
    <div style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:24px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <span style="font-weight:600">市值走势</span>
        <el-radio-group v-model="trendDays" size="small" @change="refreshTrend">
          <el-radio-button :value="7">近7天</el-radio-button>
          <el-radio-button :value="30">近30天</el-radio-button>
          <el-radio-button :value="90">近90天</el-radio-button>
        </el-radio-group>
      </div>
      <v-chart :option="pnlChartOption" :key="chartKey" style="height:300px" autoresize />
    </div>

    <!-- Risk Analysis -->
    <div v-if="risk" style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:24px">
      <div style="font-weight:600;margin-bottom:12px">风险分析</div>
      <div v-for="w in risk.warnings" :key="w.msg" style="margin-bottom:8px">
        <el-alert :title="w.msg" :type="w.level" :closable="false" show-icon />
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
        <div v-for="c in risk.concentration" :key="c.sector"
          style="background:#f5f7fa;border-radius:4px;padding:8px 12px;font-size:13px">
          <span style="font-weight:600">{{ c.sector }}</span>
          <span style="margin-left:8px;color:#909399">{{ c.pct }}%</span>
        </div>
      </div>
    </div>

    <!-- Market Valuation -->
    <div v-if="valuation.length" style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:24px">
      <div style="font-weight:600;margin-bottom:12px">市场估值（PE 分位）</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px">
        <div v-for="v in valuation" :key="v.index_code"
          style="border:1px solid #eee;border-radius:8px;padding:16px;text-align:center">
          <div style="font-weight:600;margin-bottom:8px">{{ v.index_name }}</div>
          <div style="font-size:24px;font-weight:600;margin-bottom:4px">
            {{ v.pe ? v.pe.toFixed(1) : '-' }}
          </div>
          <div style="font-size:12px;color:#909399">当前 PE</div>
          <el-tag :type="v.status === 'undervalued' ? 'success' : v.status === 'overvalued' ? 'danger' : 'warning'" size="small" style="margin-top:8px">
            {{ v.status === 'undervalued' ? '低估' : v.status === 'overvalued' ? '高估' : '正常' }}
            ({{ v.pe_percentile ? v.pe_percentile.toFixed(0) + '%分位' : '-' }})
          </el-tag>
          <div style="font-size:11px;color:#c0c4cc;margin-top:4px">数据截至 {{ v.val_date }}</div>
        </div>
      </div>
    </div>

    <!-- Settings Dialog -->
    <el-dialog v-model="settingsDialog" title="资金设置" width="450px">
      <el-form :model="settings" label-position="top">
        <el-form-item label="总本金（元）">
          <el-input-number v-model="settings.total_capital" :min="0" :precision="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="剩余可用资金（自动计算）">
          <el-input :model-value="'¥' + (settings.remaining_cash || 0).toLocaleString()" disabled style="width:100%" />
          <div style="font-size:12px;color:#909399;margin-top:4px">= 总本金 - 所有持仓成本之和，交易时自动更新</div>
        </el-form-item>
        <el-form-item label="每月定投金额（元）">
          <el-input-number v-model="settings.monthly_contribution" :min="0" :precision="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="风险偏好">
          <el-radio-group v-model="settings.risk_tolerance">
            <el-radio value="low">保守</el-radio>
            <el-radio value="medium">稳健</el-radio>
            <el-radio value="high">激进</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="止盈线（%）">
          <el-input-number v-model="settings.stop_profit_pct" :min="0" :max="50" :precision="1" style="width:100%" placeholder="如 10.0" />
          <div style="font-size:12px;color:#909399;margin-top:2px">盈利超过此线时建议分批止盈，默认根据风险偏好自动设置</div>
        </el-form-item>
        <el-form-item label="止损线（%）">
          <el-input-number v-model="settings.stop_loss_pct" :min="-50" :max="0" :precision="1" style="width:100%" placeholder="如 -8.0" />
          <div style="font-size:12px;color:#909399;margin-top:2px">亏损超过此线时建议减仓止损，输入负值如 -8</div>
        </el-form-item>
        <el-form-item label="个人意见/想法">
          <el-input v-model="settings.personal_opinion" type="textarea" :rows="3" placeholder="如：近期看好AI板块，想加仓芯片基金；担心美股回调影响A股..." />
          <div style="font-size:12px;color:#909399;margin-top:2px">这些内容会包含在给AI Agent的分析提示词中</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="settingsDialog = false">取消</el-button>
        <el-button type="primary" @click="saveSettings" :loading="settingsSaving">保存</el-button>
      </template>
    </el-dialog>

    <!-- Analysis Dialog -->
    <el-dialog v-model="analysisDialog" title="每日投资分析" width="800px" top="5vh">
      <div v-if="analysis" style="max-height:70vh;overflow-y:auto">
        <!-- Finance summary -->
        <div style="background:#f0f9ff;border-radius:8px;padding:16px;margin-bottom:16px">
          <h4 style="margin:0 0 8px">资金概览</h4>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;font-size:14px">
            <div>总本金: <b>{{ analysis.user_financials.total_capital }}</b> 元</div>
            <div>已投入: <b>{{ analysis.user_financials.invested }}</b> 元 ({{ analysis.user_financials.positions_used_pct }}%)</div>
            <div>剩余可用: <b>{{ analysis.user_financials.remaining_cash }}</b> 元</div>
            <div>当前市值: <b>{{ analysis.user_financials.total_market_value }}</b> 元</div>
            <div>总盈亏: <b :class="analysis.user_financials.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'">
              {{ analysis.user_financials.total_pnl >= 0 ? '+' : '' }}{{ analysis.user_financials.total_pnl }}
            </b> 元</div>
            <div>收益率: <b>{{ analysis.user_financials.total_pnl_pct }}%</b></div>
            <div>风险偏好: <b>{{ analysis.risk_description }}</b></div>
          </div>
        </div>

        <!-- Portfolio -->
        <h4>当前持仓</h4>
        <el-table :data="analysis.portfolio" size="small" stripe style="margin-bottom:16px">
          <el-table-column prop="fund_name" label="基金" width="180" />
          <el-table-column label="策略" width="70">
            <template #default="{ row }">
              <el-tag :type="row.strategy_type === 'long_term' ? 'success' : 'warning'" size="small">
                {{ row.strategy_type === 'long_term' ? '长线' : '短线' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="成本" width="90">
            <template #default="{ row }">{{ row.total_cost.toFixed(0) }}</template>
          </el-table-column>
          <el-table-column label="市值" width="90">
            <template #default="{ row }">{{ row.market_value.toFixed(0) }}</template>
          </el-table-column>
          <el-table-column label="盈亏" width="90">
            <template #default="{ row }">
              <span :class="row.unrealized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'">
                {{ row.unrealized_pnl >= 0 ? '+' : '' }}{{ row.unrealized_pnl.toFixed(0) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="盈亏%" width="80">
            <template #default="{ row }">{{ row.pnl_pct }}%</template>
          </el-table-column>
        </el-table>

        <!-- Market -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
          <div>
            <h4>大盘指数</h4>
            <div v-for="m in analysis.market_indices" :key="m.name" style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #eee;font-size:14px">
              <span>{{ m.name }}</span>
              <span :class="(m.change_pct||0) >= 0 ? 'pnl-positive' : 'pnl-negative'">
                {{ m.close?.toFixed(0) }} ({{ (m.change_pct||0) >= 0 ? '+' : '' }}{{ m.change_pct?.toFixed(2) }}%)
              </span>
            </div>
          </div>
          <div>
            <h4>热门板块</h4>
            <div v-for="s in analysis.hot_sectors" :key="s.name" style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #eee;font-size:14px">
              <span>{{ s.name }}</span>
              <span :class="(s.change_pct||0) >= 0 ? 'pnl-positive' : 'pnl-negative'">
                {{ (s.change_pct||0) >= 0 ? '+' : '' }}{{ s.change_pct?.toFixed(2) }}%
              </span>
            </div>
          </div>
        </div>

        <!-- News -->
        <h4>近期财经新闻</h4>
        <div v-for="n in analysis.recent_news.slice(0, 10)" :key="n.title" style="font-size:13px;padding:6px 0;border-bottom:1px solid #f0f0f0">
          <div>
            <span v-if="n.tags" style="margin-right:4px">
              <el-tag v-for="t in (()=>{try{return JSON.parse(n.tags||'[]')}catch{return[]}})()" :key="t" size="small" style="margin-right:2px">{{ t }}</el-tag>
            </span>
            <a v-if="n.url" :href="n.url" target="_blank" style="color:#409EFF;text-decoration:none">{{ n.title }}</a>
            <span v-else>{{ n.title }}</span>
          </div>
          <div v-if="n.summary" style="color:#909399;margin-top:2px;font-size:12px">{{ n.summary.slice(0, 100) }}</div>
        </div>

        <!-- Analysis Prompt -->
        <div style="background:#fff9e6;border-radius:8px;padding:16px;margin-top:16px">
          <h4 style="margin:0 0 8px;color:#e6a23c">分析提示词（可复制给AI Agent）</h4>
          <pre style="white-space:pre-wrap;font-size:13px;line-height:1.6;background:#fafafa;padding:12px;border-radius:4px;max-height:400px;overflow-y:auto">{{ analysis.analysis_prompt }}</pre>
          <el-button type="primary" size="small" style="margin-top:8px" @click="copyPrompt">复制提示词</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
