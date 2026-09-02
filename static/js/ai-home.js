document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('aiAskForm');
    const input = document.getElementById('aiQuestion');
    const button = document.getElementById('aiAskButton');
    const result = document.getElementById('aiAnswer');
    if (!form || !input || !button || !result) return;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question) return;

        button.disabled = true;
        button.textContent = 'Thinking…';
        result.hidden = false;
        result.className = 'ai-answer ai-answer-loading';
        result.textContent = 'Preparing an answer…';

        try {
            const response = await fetch('/ai/ask', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({question})
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'AI Assistant is unavailable.');
            result.className = 'ai-answer';
            result.textContent = data.answer;
        } catch (error) {
            result.className = 'ai-answer ai-answer-error';
            result.textContent = error.message || 'AI Assistant is unavailable right now.';
        } finally {
            button.disabled = false;
            button.textContent = 'Ask AI';
        }
    });

    document.querySelectorAll('[data-ai-question]').forEach(chip => {
        chip.addEventListener('click', () => {
            input.value = chip.dataset.aiQuestion || chip.textContent.trim();
            input.focus();
        });
    });
});
