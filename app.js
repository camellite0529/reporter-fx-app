const statusEl = document.getElementById("status");
const articleEl = document.getElementById("article");
const metaEl = document.getElementById("meta");
const refreshBtn = document.getElementById("refreshBtn");
const copyBtn = document.getElementById("copyBtn");

function getSelectedArticleType() {
  const checked = document.querySelector('input[name="article_type"]:checked');
  return checked ? checked.value : "";
}

function buildQuery() {
  const params = new URLSearchParams();
  const articleType = getSelectedArticleType();

  if (articleType) {
    params.set("article_type", articleType);
  }

  [
    "foreigner_amount",
    "foreigner_flow",
    "individual_amount",
    "individual_flow",
    "institution_amount",
    "institution_flow",
  ].forEach((id) => {
    const el = document.getElementById(id);
    if (el && el.value.trim()) {
      params.set(id, el.value.trim());
    }
  });

  return params.toString();
}

function getArticleTypeLabel(value) {
  const labels = {
    intraday: "장중 기사",
    opening: "개장 기사",
    weekly_close: "주간 종가 기사",
  };
  return labels[value] || value;
}

async function loadArticle() {
  const selectedType = getSelectedArticleType();

  if (!selectedType) {
    statusEl.textContent = "기사 유형을 먼저 선택해 주세요.";
    articleEl.value = "";
    metaEl.textContent = "";
    return;
  }

  statusEl.textContent = "문안을 생성하는 중입니다...";
  articleEl.value = "";
  metaEl.textContent = "";

  try {
    const query = buildQuery();
    const url = query ? `/api/article?${query}` : "/api/article";

    const response = await fetch(url, { cache: "no-store" });
    const data = await response.json();

    if (!response.ok || !data.ok) {
      throw new Error(data.error || "문안 생성에 실패했습니다.");
    }

    articleEl.value = data.article;
    metaEl.textContent = JSON.stringify(
      {
        article_type: data.article_type,
        article_type_label: data.article_type_label,
        generated_at: data.generated_at,
        displayed_at: data.displayed_at,
        display_delay_minutes: data.display_delay_minutes,
        bok_reference: data.bok_reference,
        notes: data.data_notes,
      },
      null,
      2
    );

    statusEl.textContent = `${getArticleTypeLabel(data.article_type)} 문안을 생성했습니다.`;
  } catch (error) {
    statusEl.textContent = error.message;
    metaEl.textContent = "";
  }
}

refreshBtn.addEventListener("click", loadArticle);

copyBtn.addEventListener("click", async () => {
  const text = articleEl.value;
  if (!text) {
    statusEl.textContent = "복사할 문안이 없습니다.";
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    statusEl.textContent = "기사 문안을 클립보드에 복사했습니다.";
  } catch (error) {
    statusEl.textContent = "복사에 실패했습니다. 브라우저 권한을 확인해 주세요.";
  }
});
