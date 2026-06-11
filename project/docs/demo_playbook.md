# Logos-Log Demo Playbook

This playbook is a short script for portfolio reviews, class demos, and project presentations. It focuses on showing the RAG workflow honestly: Logos-Log retrieves research excerpts and nearby context, then turns them into reflective guidance with visible citations.

## Positioning

Logos-Log is an evidence-based journaling tool that connects a user's concern or diary entry with psychology research excerpts and surrounding context, then offers grounded reflection questions rather than unsupported advice.

## Demo Prerequisites

- Backend and frontend are both running.
- The backend environment has `MONGODB_URI`, `OPENAI_API_KEY`, `JWT_SECRET`, and `ENCRYPTION_KEY`.
- MongoDB Atlas has the `documents` collection populated with English research chunks and the `vector_index` search index.
- Production search is vector-only. `$text` hybrid search is kept for evaluation experiments, not the default app path.

For a Tailscale desktop demo, run the heavier backend process on the desktop machine:

```bash
cd C:\Users\LeeMinGeon\Projects\Logos-Log\backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then run the frontend on the Mac against the desktop backend:

```bash
cd frontend
VITE_API_BASE_URL=http://100.71.35.78:8000 npm run dev -- --host 127.0.0.1 --port 5173
```

Use the direct Tailscale IP for long streaming responses. It has been more reliable than an SSH tunnel for Server-Sent Events.

## Primary Demo Path

1. Open the chat screen.
2. Ask: `성과가 없으면 제가 가치 없는 사람처럼 느껴져요.`
3. Wait for the streaming answer and point out the inline citation badge.
4. Open the citation popover and show that the cited sentence is tied to a source.
5. Expand `근거 발췌` and show the source cards.
6. Open a source modal and point out the title, author/year, section, page range, chunk id, excerpt summary, and disclaimer.
7. Explain that the UI says `근거 발췌` because the app is not claiming to summarize the full paper.

## Good Demo Questions

- `성과가 없으면 제가 가치 없는 사람처럼 느껴져요.`
- `번아웃이 와서 무기력한데 어떻게 회복할 수 있을까요?`
- `사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.`
- `지나간 실수를 계속 곱씹으며 잠을 못 자요.`
- `병 때문에 더 이상 예전처럼 일할 수 없게 됐어요. 제 존재가 쓸모없게 느껴집니다.`

## Talking Points

- The app uses MongoDB Atlas Vector Search with `BAAI/bge-m3` embeddings.
- Vector-only production search was kept because `$text` hybrid/RRF underperformed in evaluation.
- The accepted evaluation run passed the retrieval targets once: Context Precision `0.813`, Context Recall `0.767`.
- Faithfulness is the next bottleneck: accepted run `0.828`, target `0.90`.
- The UI separates retrieved excerpts from full-paper summaries to avoid overstating what the system has read.
- Verifier, claim-checker, and sentence-citation template experiments are available behind flags, but remain off by default because they did not improve the accepted full-run result.

## Honest Limitations

- Logos-Log is not therapy, medical care, or crisis support.
- The answer is grounded in retrieved excerpts and adjacent chunks, not a full manual reading of every paper.
- Some answer wording can still over-generalize. Faithfulness improvement is the next quality target.
- The evaluation set and qrels should continue to grow with more expert review.

## Troubleshooting

- If the frontend cannot reach the backend, check `VITE_API_BASE_URL` and the backend CORS settings.
- If the remote stream stalls through an SSH tunnel, use the direct Tailscale IP.
- The first request may be slow because local embedding or reranking models can warm up.
- If source cards do not appear, inspect the chat SSE `sources` event and the auth token.
- If a source modal lacks metadata, check whether the MongoDB document has `title`, `section`, `page_start`, `page_end`, `chunk_id`, and `chunk_index`.

## Verification Checklist

Run these before a recorded demo or final presentation:

```bash
python -m unittest discover -s backend/tests
cd frontend && npm run lint
cd frontend && npm run build
```

Run large RAG evaluation jobs on the Tailscale desktop:

```bash
python C:\Users\LeeMinGeon\Projects\Logos-Log\backend\eval\evaluate_rag.py --case-timeout 120 --judge-timeout 120
```
