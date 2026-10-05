import path from 'node:path'
import {fileURLToPath} from 'node:url'

const directory = path.dirname(fileURLToPath(import.meta.url))

// Metadata only; configuration is managed by the plugin's own files.
export function supportGuoba() {
  return {
    pluginInfo: {
      name: path.basename(directory).toLowerCase(),
      title: 'YunzaiServerStatus',
      author: '@719083594',
      authorLink: 'https://github.com/719083594',
      link: 'https://github.com/719083594/yunzai-server-status',
      description: '主人专用服务器状态看板，展示 CPU、内存、存储、插件和服务状态。',
      isV3: true,
      isV2: false,
      icon: 'mdi:server-network',
      iconColor: '#6254ed',
      iconPath: path.join(directory, 'resources/icon.png'),
      showInMenu: false,
    },
  }
}
