Build a minimal web app called OptiBot in Google AI Studio Build mode. Use a small chat interface with one question input, a Send button, an answer area, and a Sources area. This app is only for testing the existing OptiSigns Help Center knowledge base; do not upload any files in the UI.

Use the server-side runtime and the `@google/genai` package. Keep `GEMINI_API_KEY` in server-side Secrets and never send it to the browser. Call Gemini `gemini-3.5-flash` with the File Search tool pointed at this existing store:

`fileSearchStores/optibot-help-center-3aahsbbl6zbm`

Set the system instruction to the following text exactly, including punctuation and bullet symbols:

You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply.

Use `models.generateContent` with `tools: [{ fileSearch: { fileSearchStoreNames: [storeName] } }]`. Do not use Grounding with Google Search or URL Context. Return the answer text plus up to three distinct source URLs from `candidates[0].groundingMetadata.groundingChunks[].retrievedContext.customMetadata`, where the metadata key is `source_url`. Display each as `Article URL: <URL>` and make the URL clickable. Do not fabricate citations. If Gemini returns no source metadata, display a clear message that no cited source was returned.

Start with the sample question `How do I add a YouTube video?` available as a one-click example. Keep the UI simple enough to screenshot the question, answer, and cited URL together. Do not add login, storage, deployment, file-upload controls, or unrelated features.
