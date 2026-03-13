const statusEl = document.getElementById('status');
const articleEl = document.getElementById('article');
const metaEl = document.getElementById('meta');
const refreshBtn = document.getElementById('refreshBtn');
const copyBtn = document.getElementById('copyBtn');

function buildQuery() {
  const params = new URLSearchParams();
  [
    'foreigner_amount',
    'foreigner_flow',
    'individual_amount',
    'individual_flow',
    'institution_amount',
    'institution_flow',
  ].forEach((id) => {
    const el = document.getElementById(id);
    if (el && el.value.trim()) {
      params.set(id, el.value.trim());
    }
  });
  return params.toString();
}

async function loadArticle() {
  statusEl.textContent = '문안을 생성하는 중입니다...';
  articleEl.value = '';

  try {
    const query = buildQuery();
    const url = query ? `/api/article?${query}` : '/api/article';
    const response = await fetch(url, { cache: 'no-store' });
    const data = await response.json();

    if (!response.ok || !data.ok) {
      throw new Error(data.error || '문안 생성에 실패했습니다.');
    }

    articleEl.value = data.article;
    metaEl.textContent = JSON.stringify(
      {
        generated_at: data.generated_at,
        bok_reference: data.bok_reference,
        notes: data.data_notes,
      },
      null,
      2,
    );
    statusEl.textContent = '최신 문안을 불러왔습니다.';
  } catch (error) {
    statusEl.textContent = error.message;
    metaEl.textContent = '';
  }
}

refreshBtn.addEventListener('click', loadArticle);
copyBtn.addEventListener('click', async () => {
  const text = articleEl.value;
  if (!text) {
    statusEl.textContent = '복사할 문안이 없습니다.';
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    statusEl.textContent = '기사 문안을 클립보드에 복사했습니다.';
  } catch (error) {
    statusEl.textContent = '복사에 실패했습니다. 브라우저 권한을 확인해 주세요.';
  }
});

loadArticle();
