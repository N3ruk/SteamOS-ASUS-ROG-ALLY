import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import fs from 'node:fs';
import ts from 'typescript';

const source=fs.readFileSync(new URL('../src/steam-tdp.ts',import.meta.url),'utf8');
function load(available=true){
  const settings={clientSettings:{steamos_tdp_limit_enabled:true}};
  const calls=[];
  function nativeSetter(key,value){
    // SteamClient.Settings.SetSetting
    calls.push([key,value]);settings.clientSettings[key]=value;
  }
  const context={exports:{},setTimeout,
    require:()=>({findModuleChild:fn=>fn({store:settings,change:nativeSetter})})};
  if(available) context.settingsStore=settings;
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  vm.runInNewContext(code,context);
  return {api:context.exports,settings,calls};
}
test('Steam switch really disables and re-enables its native TDP setting',async()=>{
  const {api,calls}=load();
  assert.equal(api.nativeTdpAvailable(),true);
  assert.equal(api.nativeTdpEnabled(),true);
  await api.setNativeTdp(false);
  assert.equal(api.nativeTdpEnabled(),false);
  await api.setNativeTdp(true);
  assert.equal(api.nativeTdpEnabled(),true);
  assert.deepEqual(calls,[['steamos_tdp_limit_enabled',false],['steamos_tdp_limit_enabled',true]]);
});
test('reading capability and setting an unchanged native value do not write',async()=>{
  const {api,calls}=load();
  api.nativeTdpAvailable();api.nativeTdpEnabled();await api.setNativeTdp(true);
  assert.equal(calls.length,0);
});
test('missing Steam API refuses TDP changes explicitly',async()=>{
  const {api,calls}=load(false);
  assert.equal(api.nativeTdpAvailable(),false);assert.equal(api.nativeTdpEnabled(),null);
  await assert.rejects(()=>api.setNativeTdp(false),/CPU siguen disponibles/);
  assert.equal(calls.length,0);
});
