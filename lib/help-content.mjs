// Public descriptions; no server readings, owner identities or private config.
export const helpTopics=Object.freeze({
  'system-help':{
    title:'系统状态 · ServerStatus',
    subtitle:'服务器概况与资源看板 · 所有命令仅机器人主人可用',
    groups:[
      {title:'完整总览',items:[
        {command:'#系统 / #服务器',description:'查看宿主机运行状态与完整总览'},
        {command:'#系统帮助',description:'查看这张使用指南'},
        {command:'#系统帮助 文字',description:'查看文字版说明'}
      ]},
      {title:'资源与存储',items:[
        {command:'#资源',description:'CPU、内存、交换内存与运行时间'},
        {command:'#存储',description:'磁盘空间、数据目录与容器存储'}
      ]},
      {title:'插件与服务',items:[
        {command:'#插件',description:'查看已安装插件与实际加载情况'},
        {command:'#服务',description:'查看服务运行状态与资源占用'}
      ]},
      {title:'使用提示',items:[
        {command:'仅机器人主人可查看',description:'帮助图片与状态命令使用同一权限检查',permission:'主人权限由机器人框架判断'},
        {command:'支持 # 和 / 开头，无需 @',description:'直接读取本机采集结果，不调用 AI'}
      ]}
    ],
    footer:'此帮助图仅包含固定指令说明；实时状态仍通过本机采集生成。'
  }
});
