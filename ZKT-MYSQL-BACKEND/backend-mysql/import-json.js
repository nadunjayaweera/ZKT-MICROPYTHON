'use strict';
// One-time migration. Stop the JSON backend and ESP32 sync before running.
const fs=require('node:fs');
const readline=require('node:readline');
const {pool,commitBatch,validateBatch}=require('./server');
const source=process.argv[2];
if (!source || !fs.existsSync(source)) { console.error('Usage: node import-json.js /path/to/attendance.jsonl'); process.exit(1); }
(async()=>{
 let batches=0,records=0;
 const stream=fs.createReadStream(source,{encoding:'utf8'});
 const lines=readline.createInterface({input:stream,crlfDelay:Infinity});
 try {
  for await (const line of lines) {
   if (!line.trim()) continue;
   const batch=JSON.parse(line);
   if (!validateBatch(batch)) throw Error('Invalid journal batch on line '+(batches+1));
   const result=await commitBatch(batch);
   if (result.status!==200) throw Error('Cursor mismatch on line '+(batches+1)+' for '+batch.device_id+'. Migration stopped.');
   batches++; records+=result.body.inserted;
   if (batches%100===0) console.log('Imported batches:',batches,'new records:',records);
  }
  console.log('Migration complete:',batches,'batches processed,',records,'records inserted.');
 } finally { lines.close(); stream.destroy(); await pool.end(); }
})().catch(e=>{console.error('Migration failed:',e.message);process.exitCode=1;pool.end();});
