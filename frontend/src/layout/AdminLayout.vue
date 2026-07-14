<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessageBox } from 'element-plus'
import { DataBoard, Folder, User, Tickets, Collection, DocumentChecked, Link, Operation, Fold, Expand } from '@element-plus/icons-vue'
import type { Role } from '@/types'
const collapsed=ref(false),route=useRoute(),router=useRouter(),auth=useAuthStore()
const title=computed(()=>String(route.meta.title||'管理后台'))
const allMenus=[
 {path:'/dashboard',label:'后台首页',icon:DataBoard,roles:['ADMIN']},
 {path:'/projects',label:'实训项目管理',icon:Folder,roles:['ADMIN','TEACHER']},
 {path:'/students',label:'学生管理',icon:User,roles:['ADMIN','TEACHER']},
 {path:'/templates',label:'证书模板',icon:Tickets,roles:['ADMIN','TEACHER']},
 {path:'/batches',label:'证书批次',icon:Collection,roles:['ADMIN','TEACHER']},
 {path:'/certificates',label:'证书管理',icon:DocumentChecked,roles:['ADMIN','TEACHER']},
 {path:'/chain',label:'存证回执',icon:Link,roles:['ADMIN','TEACHER','AUDITOR']},
 {path:'/audit',label:'操作日志',icon:Operation,roles:['ADMIN','AUDITOR']}
] as Array<{path:string;label:string;icon:unknown;roles:Role[]}>
const menus=computed(()=>allMenus.filter(item=>auth.user&&item.roles.includes(auth.user.role)))
async function logout(){await ElMessageBox.confirm('确认退出当前账号吗？','退出登录');auth.logout();router.replace('/login')}
</script>
<template><el-container class="app-shell"><el-aside :width="collapsed?'72px':'232px'" class="sidebar"><div class="brand"><div class="brand-mark">链</div><div v-if="!collapsed"><strong>可信证书</strong><span>管理平台</span></div></div><el-menu :default-active="route.path" router :collapse="collapsed" background-color="transparent" text-color="#cbd5e1" active-text-color="#fff"><el-menu-item v-for="item in menus" :key="item.path" :index="item.path"><el-icon><component :is="item.icon"/></el-icon><template #title>{{item.label}}</template></el-menu-item></el-menu><div class="chain-health" v-if="!collapsed"><span></span><div><b>本地哈希链已启用</b><small>教学版可信存证</small></div></div></el-aside><el-container><el-header class="topbar"><button class="collapse-button" @click="collapsed=!collapsed"><el-icon><component :is="collapsed?Expand:Fold"/></el-icon></button><div><h1>{{title}}</h1><p>区块链实训证书与学业证明存证系统</p></div><div class="account"><div class="avatar">{{auth.user?.displayName.slice(0,1)}}</div><div><b>{{auth.user?.displayName}}</b><span>{{auth.user?.role}}</span></div><el-button text @click="logout">退出</el-button></div></el-header><el-main class="main-content"><router-view/></el-main></el-container></el-container></template>