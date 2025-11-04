🪶 PaperWhisperer

“Listen to what papers are whispering to you.”
PaperWhisperer is your personal AI companion for understanding research papers.
Upload a PDF or paste a paper link — it reads, analyzes, and lets you chat with the paper itself.

🚀 Features

📄 Smart PDF Parsing — Extracts title, abstract, sections, references, and figures automatically

🧠 AI Understanding — Summarizes methods, contributions, and key insights in human-readable form

💬 Chat with the Paper — Ask natural questions and get contextual answers

🌐 Support for PDF / arXiv / DOI Links

🗣️ Multilingual Output — English / 中文 / 学术摘要 / 通俗解读

🪞 Memory-Aware Conversation — Keeps context so you can explore ideas naturally

🏗️ Tech Stack

Python 3.10+

FastAPI — lightweight backend API

LangChain + Qwen / OpenAI API — for semantic understanding and conversation

PyMuPDF / pdfminer.six — PDF text and structure extraction

Qdrant / FAISS — vector storage for semantic retrieval

🧭 Example Usage
# Analyze a paper from a PDF
paperwhisperer analyze ./papers/attention-is-all-you-need.pdf

# Or from an online source
paperwhisperer analyze https://arxiv.org/abs/1706.03762


Then start chatting:

> What problem does this paper solve?
> How does their attention mechanism differ from RNNs?

🔮 Roadmap

 Add citation network visualization

 Support extracting equations and tables

 Personalized “Research Memory” — store what you’ve read

 Export summaries to Markdown

💡 Vision

Academic papers often whisper complex ideas in a language only experts understand.
PaperWhisperer translates those whispers into clear insights — making research more accessible, one paper at a time.

📜 License

MIT License © 2025
