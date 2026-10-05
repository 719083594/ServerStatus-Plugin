// Framework-independent API. Select an integration explicitly at install time.
import fs from 'node:fs'
let adapter
try{adapter=JSON.parse(fs.readFileSync(new URL('./config/integration.json',import.meta.url),'utf8')).adapter}
catch(err){if(err.code!=='ENOENT')throw new Error('Invalid integration configuration')}
// Yunzai loaders read apps; default is empty and imports no framework modules.
export const apps=adapter==='yunzai'?(await import('./integrations/yunzai/index.js')):{}
if(adapter&&adapter!=='yunzai')throw new Error('Unsupported integration: '+adapter)
export {commands,commandKind,handleStatus,createDashboard,runtimeFrom,collectSnapshot} from './lib/api.mjs'
