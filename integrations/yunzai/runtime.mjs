import fs from 'node:fs'
import {runtimeFrom} from '../../lib/runtime.mjs'
let loader
try{loader=(await import('../../../../lib/plugins/loader.js')).default}catch{}
export function collectRuntime(){
  let files=[]
  try{files=fs.readdirSync('plugins',{withFileTypes:true}).filter(i=>i.isDirectory()).map(i=>i.name)}catch{}
  return runtimeFrom({loader,bot:globalThis.Bot||{},files})
}
