import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AdminLayout from '@/layout/AdminLayout.vue'
import type { Role } from '@/types'
const ADMIN_TEACHER: Role[] = ['ADMIN','TEACHER']
const router=createRouter({history:createWebHistory(),routes:[
 {path:'/login',component:()=>import('@/views/LoginView.vue'),meta:{public:true,title:'登录'}},
 {path:'/student',component:()=>import('@/views/student/StudentCenterView.vue'),meta:{public:true,title:'学生中心'}},
 {path:'/student/certificates',component:()=>import('@/views/student/MyCertificatesView.vue'),meta:{public:true,title:'我的证书'}},
 {path:'/student/certificates/:certificateNo',component:()=>import('@/views/student/StudentCertificateDetailView.vue'),meta:{public:true,title:'证书详情'}},
 {path:'/public/verify',component:()=>import('@/views/public/PublicVerifyView.vue'),meta:{public:true,title:'证书验真'}},
 {path:'/public/verify/:certificateNo',component:()=>import('@/views/public/PublicVerifyView.vue'),meta:{public:true,title:'证书验真'}},
 {path:'/',component:AdminLayout,redirect:'/dashboard',children:[
  {path:'dashboard',component:()=>import('@/views/DashboardView.vue'),meta:{title:'后台首页',roles:['ADMIN']}},
  {path:'projects',component:()=>import('@/views/ProjectsView.vue'),meta:{title:'实训项目管理',roles:ADMIN_TEACHER}},
  {path:'students',component:()=>import('@/views/StudentsView.vue'),meta:{title:'学生管理',roles:ADMIN_TEACHER}},
  {path:'templates',component:()=>import('@/views/TemplatesView.vue'),meta:{title:'证书模板',roles:ADMIN_TEACHER}},
  {path:'batches',component:()=>import('@/views/BatchesView.vue'),meta:{title:'证书批次',roles:ADMIN_TEACHER}},
  {path:'certificates',component:()=>import('@/views/CertificatesView.vue'),meta:{title:'证书管理',roles:ADMIN_TEACHER}},
  {path:'chain',component:()=>import('@/views/ChainView.vue'),meta:{title:'存证回执',roles:['ADMIN','TEACHER','AUDITOR']}},
  {path:'audit',component:()=>import('@/views/AuditView.vue'),meta:{title:'操作日志',roles:['ADMIN','AUDITOR'],readOnlyRoles:['AUDITOR']}}
 ]},
 {path:'/403',component:()=>import('@/views/ErrorView.vue'),props:{code:'403',text:'无权访问此页面'},meta:{public:true}},
 {path:'/:pathMatch(.*)*',component:()=>import('@/views/ErrorView.vue'),props:{code:'404',text:'页面不存在'},meta:{public:true}}
]})
router.beforeEach(to=>{const auth=useAuthStore();document.title=`${String(to.meta.title||'管理后台')} - 可信证书平台`;if(!to.meta.public&&!auth.isLoggedIn)return `/login?redirect=${encodeURIComponent(to.fullPath)}`;if(to.path==='/login'&&auth.isLoggedIn)return auth.user?.role==='AUDITOR'?'/chain':auth.user?.role==='TEACHER'?'/projects':'/dashboard';const roles=to.meta.roles as Role[]|undefined;if(roles&&(!auth.user||!roles.includes(auth.user.role)))return'/403'})
export default router
