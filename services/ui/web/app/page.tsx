'use client';
import { FormEvent, useState } from 'react';
type Source = { file_name: string; page_number: number };
type Result = { answer: string; sources: Source[]; found: boolean };
const API_URL = process.env.NEXT_PUBLIC_SEARCH_API_URL ?? 'http://localhost:8787';
export default function Home() {
  const [question, setQuestion] = useState(''); const [result, setResult] = useState<Result | null>(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  async function submit(e: FormEvent) { e.preventDefault(); const trimmedQuestion = question.trim(); if (loading) return; if (!trimmedQuestion) { setError('質問を入力してください。'); return; } setLoading(true); setError(''); setResult(null);
    try { const response = await fetch(`${API_URL}/api/v1/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: trimmedQuestion }) });
      if (!response.ok) throw new Error(`検索APIに接続できませんでした（HTTP ${response.status}）。APIが起動しているか確認してください。`); const data: Result = await response.json(); setResult(data);
    } catch (err) { setError(err instanceof Error ? err.message : '検索に失敗しました。APIの起動状態を確認してください。'); } finally { setLoading(false); }
  }
  return <main><section className="card"><p className="eyebrow">INTERNAL DOCUMENT SEARCH</p><h1>社内文書検索AI</h1><p className="lead">社内の資料について質問してください。</p><form onSubmit={submit}><label htmlFor="question">質問</label><textarea id="question" value={question} onChange={e => setQuestion(e.target.value)} placeholder="例：有給休暇の申請方法を教えてください" rows={4} /><button disabled={loading}>{loading ? '検索中…' : '回答を検索'}</button></form>
    {loading && <p className="status">文書を検索して回答を作成しています…</p>}{error && <p className="error" role="alert">{error}</p>}{result && <article className="answer"><h2>回答</h2>{result.found ? <p>{result.answer}</p> : <p className="muted">該当する文書が見つかりませんでした。質問を変えて、もう一度お試しください。</p>}{result.found && result.sources.length ? <><h3>出典</h3><ul>{result.sources.map((source, i) => <li key={i}>{source.file_name}（{source.page_number}ページ）</li>)}</ul></> : null}</article>}</section></main>;
}
