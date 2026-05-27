<script setup>
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const navItems = [
  { path: '/', label: '概览' },
  { path: '/holdings', label: '持仓' },
  { path: '/add-transaction', label: '录入交易' },
  { path: '/watchlist', label: '关注' },
  { path: '/calendar', label: '日历' },
  { path: '/market', label: '行情' },
]
</script>

<template>
  <el-menu
    :default-active="route.path"
    mode="horizontal"
    :ellipsis="false"
    @select="(index) => router.push(index)"
  >
    <div style="display:flex;align-items:center;padding:0 20px">
      <span style="font-size:18px;font-weight:700;color:#303133;margin-right:30px">基金投资管家</span>
    </div>
    <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
      {{ item.label }}
    </el-menu-item>
  </el-menu>
</template>
