interface Env { DB: D1Database; VECTORIZE: VectorizeIndex; GEMINI_API_KEY: string; INGEST_TOKEN: string; CORS_ORIGIN?: string; GEMINI_EMBEDDING_MODEL?: string; GEMINI_GENERATION_MODEL?: string; }
type Input = { question?: string; match_count?: number; match_threshold?: number };
function corsHeaders(request: Request, env: Env): HeadersInit {
  const requestOrigin = request.headers.get("Origin");
  const allowedOrigin = env.CORS_ORIGIN?.trim();
  const origin = allowedOrigin ? (requestOrigin === allowedOrigin ? allowedOrigin : undefined) : "*";
  return { ...(origin ? {"Access-Control-Allow-Origin": origin} : {}), "Access-Control-Allow-Headers":"Content-Type, X-Ingest-Token", "Access-Control-Allow-Methods":"GET,POST,OPTIONS", "Vary":"Origin" };
}
const json = (body: unknown, status=200, headers: HeadersInit={}) => new Response(JSON.stringify(body), { status, headers:{"content-type":"application/json; charset=utf-8", ...headers} });
const error = (message:string, status=400, headers?:HeadersInit) => json({error:{message}}, status, headers);
async function embedding(text:string, env:Env):Promise<number[]> {
  const model=env.GEMINI_EMBEDDING_MODEL||"gemini-embedding-001";
  const r=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:embedContent`,{method:"POST",headers:{"content-type":"application/json","x-goog-api-key":env.GEMINI_API_KEY},body:JSON.stringify({model:`models/${model}`,content:{parts:[{text}]},outputDimensionality:768})});
  if(!r.ok) throw new Error(`Gemini embedding error (${r.status}): ${await r.text()}`);
  const d=await r.json() as {embedding?:{values?:number[]}}; const v=d.embedding?.values;
  if(!v || v.length!==768 || v.some((value) => typeof value !== "number" || !Number.isFinite(value))) throw new Error("Gemini embedding must contain 768 finite numbers"); return v;
}
async function search(input:Input, env:Env) {
  if(!input.question?.trim()) throw new Error("question is required");
  const count=Math.min(Math.max(input.match_count??5,1),50), vector=await embedding(input.question,env);
  const q=await env.VECTORIZE.query(vector,{topK:count,returnMetadata:"all"});
  const matches=(q.matches||[]).filter(m=>input.match_threshold===undefined || m.score>=input.match_threshold);
  const results=await Promise.all(matches.map(async m=>{const id=String(m.id); const row=await env.DB.prepare("SELECT id,file_name,page_number,chunk_index,content FROM document_chunks WHERE content_hash = ?").bind(id).first<{id:string,file_name:string,page_number:number,chunk_index:number,content:string}>(); return row?{...row,similarity:m.score}:null;}));
  return results.filter((x):x is NonNullable<typeof x>=>x!==null);
}
async function generate(question:string, results:Awaited<ReturnType<typeof search>>, env:Env) {
  const model=env.GEMINI_GENERATION_MODEL||"gemini-3.6-flash"; const context=results.map((r,i)=>`[${i+1}] ${r.file_name} p.${r.page_number}\n${r.content}`).join("\n\n");
  const r=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,{method:"POST",headers:{"content-type":"application/json","x-goog-api-key":env.GEMINI_API_KEY},body:JSON.stringify({contents:[{role:"user",parts:[{text:`社内文書の内容だけを根拠に日本語で回答してください。不明なら不明と答えてください。\n\n質問: ${question}\n\n文書:\n${context}`}]}]})});
  if(!r.ok) throw new Error(`Gemini generation error (${r.status}): ${await r.text()}`); const d=await r.json() as any; return d.candidates?.[0]?.content?.parts?.map((p:any)=>p.text||"").join("")||"回答を生成できませんでした。";
}
export default { async fetch(request:Request,env:Env):Promise<Response> { const headers=corsHeaders(request,env); if(request.method==="OPTIONS") return new Response(null,{headers}); const url=new URL(request.url); try {
  if(request.method==="GET"&&url.pathname==="/health") return json({ok:true},200,headers);
  if(request.method!=="POST") return error("Method not allowed",405,headers);
  if(url.pathname==="/api/v1/ingest") { if(request.headers.get("X-Ingest-Token")!==env.INGEST_TOKEN) return error("Invalid ingest token",401,headers); const b=await request.json() as any; if(!b.source||!Number.isInteger(b.page_number)||!Number.isInteger(b.chunk_index)||!b.content||!b.content_hash||!Array.isArray(b.embedding)) return error("source, page_number, chunk_index, content, content_hash, embedding are required",400,headers); if(b.embedding.length!==768 || b.embedding.some((value: unknown) => typeof value !== "number" || !Number.isFinite(value))) return error("embedding must contain 768 finite numbers",400,headers); await env.DB.prepare("INSERT INTO document_chunks (id,file_name,page_number,chunk_index,content,content_hash) VALUES (?,?,?,?,?,?) ON CONFLICT(content_hash) DO UPDATE SET file_name=excluded.file_name,page_number=excluded.page_number,chunk_index=excluded.chunk_index,content=excluded.content").bind(b.content_hash,b.source,b.page_number,b.chunk_index,b.content,b.content_hash).run(); await env.VECTORIZE.upsert([{id:b.content_hash,values:b.embedding,metadata:{file_name:b.source,page_number:b.page_number,chunk_index:b.chunk_index}}]); return json({ok:true,id:b.content_hash},200,headers); }
  const b=await request.json() as Input; if(url.pathname==="/api/v1/search") return json({results:await search(b,env)},200,headers); if(url.pathname==="/api/v1/ask") { const results=await search(b,env); if(!results.length) return json({answer:"該当する文書が見つかりませんでした。",sources:[],found:false},200,headers); return json({answer:await generate(b.question!,results,env),sources:results.map(r=>({file_name:r.file_name,page_number:r.page_number})),found:true},200,headers); } return error("Not found",404,headers);
 } catch(e) { console.error("Request failed", e); return error("処理に失敗しました",500,headers); } } };
