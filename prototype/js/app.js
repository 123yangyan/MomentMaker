/**
 * MomentMaker 原型 - 通用交互脚本
 */

// 保存草稿并跳转至「我的」
function saveDraftAndRedirect(step, extra = {}) {
  const draft = {
    step,
    ...extra,
    savedAt: new Date().toISOString()
  };
  try {
    localStorage.setItem('momentmaker_draft', JSON.stringify(draft));
  } catch (e) {
    // 原型环境 localStorage 不可用时仍给出反馈
  }
  showToast('草稿已保存');
  setTimeout(() => {
    window.location.href = 'mine.html#draft';
  }, 800);
}

function bindSaveDraftBtn(btn, step, getExtra) {
  btn?.addEventListener('click', () => {
    const extra = getExtra ? getExtra() : {};
    saveDraftAndRedirect(step, extra);
  });
}

const DEFAULT_WORK_NAME = '用户ABCD';
const WORK_NAME_KEY = 'momentmaker_work_name';
const TEMPLATE_NAMES = { comic: '连环画', map: '故事地图', album: '记录册' };
const MATERIAL_NAMES = { keychain: '钥匙扣', badge: '吧唧', postcard: '明信片' };
const STYLE_NAMES = { anime: '二次元', cyber: '赛博', realistic: '写实' };

function getWorkName() {
  try {
    const stored = sessionStorage.getItem(WORK_NAME_KEY);
    if (stored && stored.trim()) return stored.trim();
  } catch (e) {
    // ignore
  }
  return '';
}

function setWorkName(name) {
  const finalName = (name || '').trim();
  try {
    sessionStorage.setItem(WORK_NAME_KEY, finalName);
  } catch (e) {
    // ignore
  }
  return finalName;
}

// 作品名称输入（创作流程 3-4 步，点击输入框直接编辑）
function initWorkNameEditor() {
  const input = document.getElementById('workNameInput');
  if (!input) return;

  const syncInputFromStorage = () => {
    const name = getWorkName();
    input.value = name;
  };

  syncInputFromStorage();

  input.addEventListener('blur', () => {
    setWorkName(input.value);
    syncInputFromStorage();
  });
}

function showToast(message, duration = 2500) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// 伪进度条动画
function runProgressBar(fillEl, duration = 2000, onComplete) {
  let progress = 0;
  const interval = 50;
  const step = (100 / duration) * interval;

  if (fillEl) fillEl.style.width = '0%';

  const timer = setInterval(() => {
    progress += step;
    if (progress >= 100) {
      clearInterval(timer);
      if (fillEl) fillEl.style.width = '100%';
      if (onComplete) setTimeout(onComplete, 300);
    } else if (fillEl) {
      fillEl.style.width = progress + '%';
    }
  }, interval);

  // 无进度条元素时也保证回调执行
  if (!fillEl && onComplete) {
    setTimeout(onComplete, duration + 300);
  }
}

// 真实联调后广场作品由 loadWorksFromApi 渲染
function renderLatestCreatedWork() {}

async function loadWorksFromApi() {
  const worksGrid = document.getElementById('worksGrid');
  if (!worksGrid || !window.MomentMakerApi) return;

  worksGrid.innerHTML = '<p class="works-empty">正在加载广场作品...</p>';
  try {
    const data = await window.MomentMakerApi.fetchWorks(1);
    const items = data.items || [];
    if (!items.length) {
      worksGrid.innerHTML = '<p class="works-empty">广场还没有作品，快去创作第一张吧</p>';
      return;
    }

    worksGrid.innerHTML = items.map((work) => `
      <div class="work-card" data-work-id="${work.work_id}">
        <div class="work-card-img wf-photo ratio-medium">
          <img src="${window.MomentMakerApi.fileUrl(work.cover_url)}" alt="${work.title}" loading="lazy">
        </div>
        <div class="work-card-info">
          <div class="work-card-name">${work.title}</div>
          <div class="work-card-author-row">
            <span class="work-card-author">${work.nickname || '匿名用户'}</span>
            <span class="work-card-meta">♡ ${work.likes || 0}</span>
          </div>
        </div>
      </div>
    `).join('');
  } catch (error) {
    worksGrid.innerHTML = `<p class="works-empty">${error.message || '加载广场失败'}</p>`;
  }
}

// Lightbox 控制（P1 广场页）— 事件委托，支持动态卡片
function initLightbox() {
  const lightbox = document.getElementById('lightbox');
  const worksGrid = document.getElementById('worksGrid');
  if (!lightbox || !worksGrid) return;

  const closeBtn = lightbox.querySelector('.lightbox-close');
  const mainImg = document.getElementById('lightboxImg') || lightbox.querySelector('.lightbox-main img');
  const titleEl = lightbox.querySelector('.lightbox-title');
  const likeBtn = document.getElementById('lightboxLikeBtn');
  const likeIcon = likeBtn?.querySelector('.lightbox-like-icon');
  const likeCountEl = likeBtn?.querySelector('.lightbox-like-count');

  let liked = false;
  let likeCount = 0;
  let currentWorkId = null;

  const updateLikeUI = () => {
    if (likeCountEl) likeCountEl.textContent = String(likeCount);
    if (likeBtn) likeBtn.classList.toggle('liked', liked);
    if (likeIcon) likeIcon.textContent = liked ? '♥' : '♡';
  };

  const showWork = (work) => {
    currentWorkId = work.work_id || null;
    likeCount = work.likes || 0;
    liked = false;

    if (mainImg) {
      const imageUrl = work.cover_url
        ? window.MomentMakerApi.fileUrl(work.cover_url)
        : '';
      if (imageUrl) {
        mainImg.src = imageUrl;
        mainImg.style.display = 'block';
      } else {
        mainImg.removeAttribute('src');
        mainImg.style.display = 'none';
      }
    }

    if (titleEl) titleEl.textContent = work.title || '未命名作品';
    updateLikeUI();
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
  };

  worksGrid.addEventListener('click', (event) => {
    const card = event.target.closest('.work-card');
    if (!card) return;

    const img = card.querySelector('.work-card-img img');
    const meta = card.querySelector('.work-card-meta')?.textContent || '';
    const likeMatch = meta.match(/(\d+)/);
    showWork({
      work_id: card.dataset.workId,
      title: card.querySelector('.work-card-name')?.textContent,
      cover_url: img?.src,
      likes: likeMatch ? parseInt(likeMatch[1], 10) : 0
    });
  });

  // “我的”页面会带 work 参数跳回广场，进入后直接打开对应成品。
  const sharedWorkId = new URLSearchParams(window.location.search).get('work');
  if (sharedWorkId && window.MomentMakerApi) {
    window.MomentMakerApi.fetchWorkDetail(sharedWorkId)
      .then(showWork)
      .catch((error) => showToast(error.message || '作品加载失败'));
  }

  likeBtn?.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!currentWorkId || !window.MomentMakerApi) {
      liked = !liked;
      likeCount += liked ? 1 : -1;
      updateLikeUI();
      return;
    }
    try {
      const result = await window.MomentMakerApi.likeWork(currentWorkId);
      likeCount = result.likes;
      liked = true;
      updateLikeUI();
      const card = worksGrid.querySelector(`.work-card[data-work-id="${currentWorkId}"]`);
      const metaEl = card?.querySelector('.work-card-meta');
      if (metaEl) metaEl.textContent = `♡ ${likeCount}`;
    } catch (error) {
      showToast(error.message || '点赞失败');
    }
  });

  const close = () => {
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
  };

  closeBtn?.addEventListener('click', close);
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) close();
  });
}

// 上传页交互（P2）— 上传图片、创建后台任务，成功后倒计时回广场
function initUploadPage() {
  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('fileInput');
  const workNameInput = document.getElementById('workNameInput');
  const previewGrid = document.getElementById('previewGrid');
  const nextBtn = document.getElementById('nextBtn');
  const saveDraftBtn = document.getElementById('saveDraftBtn');
  const loadingOverlay = document.getElementById('uploadLoading');
  const loadingPanel = document.getElementById('loadingPanel');
  const successPanel = document.getElementById('successPanel');
  const loadingSpinner = document.getElementById('loadingSpinner');
  const loadingText = document.getElementById('loadingText');
  const loadingSub = document.getElementById('loadingSub');
  const progressFill = document.getElementById('progressFill');
  const successSub = document.getElementById('successSub');
  const successCountdown = document.getElementById('successCountdown');
  const goSquareBtn = document.getElementById('goSquareBtn');
  const templateChoices = document.querySelectorAll('#uploadTemplateList .square-template-item');
  const materialChoices = document.querySelectorAll('#materialChoiceList .material-choice-card');

  if (!zone || !window.MomentMakerApi) return;

  const MIN_UPLOAD_MS = 1200;
  const COUNTDOWN_SECONDS = 3;

  let files = [];
  let isSubmitting = false;
  let progressTimer = null;
  let redirectTimer = null;

  const templateFromSquare = new URLSearchParams(window.location.search).get('template');
  const availableTemplates = ['comic', 'map', 'album'];
  let selectedTemplate = availableTemplates.includes(templateFromSquare)
    ? templateFromSquare
    : 'comic';
  let selectedMaterial = 'keychain';

  templateChoices.forEach((choice) => {
    choice.classList.toggle('selected', choice.dataset.template === selectedTemplate);
  });

  const saveCreationChoices = () => {
    try {
      sessionStorage.setItem('momentmaker_creation_choices', JSON.stringify({
        template: selectedTemplate,
        material: selectedMaterial
      }));
    } catch (error) {
      // ignore
    }
  };

  templateChoices.forEach((choice) => {
    choice.addEventListener('click', () => {
      templateChoices.forEach((item) => item.classList.remove('selected'));
      choice.classList.add('selected');
      selectedTemplate = choice.dataset.template;
      saveCreationChoices();
    });
  });

  materialChoices.forEach((choice) => {
    choice.addEventListener('click', () => {
      materialChoices.forEach((item) => item.classList.remove('selected'));
      choice.classList.add('selected');
      selectedMaterial = choice.dataset.material;
      saveCreationChoices();
    });
  });

  const updateNextBtn = () => {
    if (nextBtn) nextBtn.disabled = files.length === 0 || !workNameInput?.value.trim() || isSubmitting;
  };

  const clearUploadTimers = () => {
    if (progressTimer) clearInterval(progressTimer);
    if (redirectTimer) clearInterval(redirectTimer);
    progressTimer = null;
    redirectTimer = null;
  };

  const goToSquare = () => {
    clearUploadTimers();
    window.location.href = 'index.html';
  };

  const showUploadProgress = () => {
    loadingOverlay?.classList.remove('hidden');
    loadingPanel?.classList.remove('hidden');
    successPanel?.classList.add('hidden');
    if (loadingSpinner) loadingSpinner.style.display = '';
    if (loadingText) loadingText.textContent = '正在上传图片';
    if (loadingSub) loadingSub.textContent = '请稍候，不要关闭页面';
    if (progressFill) progressFill.style.width = '8%';
  };

  const animateUploadProgress = (startedAt) => {
    if (progressTimer) clearInterval(progressTimer);
    progressTimer = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const ratio = Math.min(elapsed / MIN_UPLOAD_MS, 1);
      const progress = 8 + Math.round(ratio * 82);
      if (progressFill) progressFill.style.width = `${progress}%`;
    }, 50);
  };

  const showUploadSuccess = () => {
    if (progressTimer) clearInterval(progressTimer);
    progressTimer = null;
    if (progressFill) progressFill.style.width = '100%';
    if (loadingSpinner) loadingSpinner.style.display = 'none';
    loadingPanel?.classList.add('hidden');
    successPanel?.classList.remove('hidden');

    let remaining = COUNTDOWN_SECONDS;
    const refreshCountdown = () => {
      if (successCountdown) successCountdown.textContent = String(remaining);
      if (successSub) {
        successSub.textContent = `海报正在后台生成，${remaining} 秒后返回广场查看`;
      }
    };
    refreshCountdown();

    redirectTimer = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        goToSquare();
        return;
      }
      refreshCountdown();
    }, 1000);
  };

  const renderPreviews = () => {
    if (!previewGrid) return;
    const visibleFiles = files.slice(0, 4);
    previewGrid.innerHTML = visibleFiles.map((f, i) => `
      <div class="upload-preview-item">
        <img src="${f.url}" alt="预览">
        ${i === 3 && files.length > 4 ? `
          <div class="upload-preview-more" aria-label="共上传 ${files.length} 个素材">
            <span class="upload-preview-more-icon" aria-hidden="true">•••</span>
            <span class="upload-preview-more-count">+${files.length}</span>
          </div>
        ` : ''}
        <button type="button" class="upload-preview-remove" data-index="${i}" aria-label="移除此素材">×</button>
      </div>
    `).join('');

    previewGrid.querySelectorAll('.upload-preview-remove').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.index, 10);
        if (files[idx]?.file) URL.revokeObjectURL(files[idx].url);
        files.splice(idx, 1);
        renderPreviews();
        updateNextBtn();
      });
    });
  };

  zone.addEventListener('click', () => input?.click());
  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
  });
  input?.addEventListener('change', (e) => handleFiles(e.target.files));

  function handleFiles(fileList) {
    Array.from(fileList).slice(0, 20 - files.length).forEach((file) => {
      if (file.type.startsWith('image/')) {
        files.push({ file, url: URL.createObjectURL(file), name: file.name });
      } else {
        showToast(`仅支持图片：${file.name}`);
      }
    });
    renderPreviews();
    updateNextBtn();
  }

  workNameInput?.addEventListener('input', updateNextBtn);

  goSquareBtn?.addEventListener('click', goToSquare);

  nextBtn?.addEventListener('click', async () => {
    if (files.length === 0 || isSubmitting) return;
    const workTitle = workNameInput?.value.trim();
    if (!workTitle) {
      showToast('请填写作品名称');
      return;
    }

    isSubmitting = true;
    updateNextBtn();
    const originalText = nextBtn.textContent;
    nextBtn.textContent = '正在上传...';

    const startedAt = Date.now();
    showUploadProgress();
    animateUploadProgress(startedAt);

    try {
      const uploadData = await window.MomentMakerApi.uploadFiles(files.map((item) => item.file));
      if (loadingSub) loadingSub.textContent = '正在提交创作任务...';

      const taskData = await window.MomentMakerApi.startTask({
        file_ids: uploadData.file_ids,
        template: selectedTemplate,
        style: 'anime',
        material: selectedMaterial,
        work_title: workTitle
      });

      const elapsed = Date.now() - startedAt;
      if (elapsed < MIN_UPLOAD_MS) {
        await new Promise((resolve) => setTimeout(resolve, MIN_UPLOAD_MS - elapsed));
      }

      sessionStorage.setItem('momentmaker_active_task_id', taskData.task_id);
      setWorkName(workTitle);
      saveCreationChoices();
      showUploadSuccess();
    } catch (error) {
      clearUploadTimers();
      loadingOverlay?.classList.add('hidden');
      showToast(error.message || '上传失败，请重试');
    } finally {
      isSubmitting = false;
      nextBtn.textContent = originalText;
      updateNextBtn();
    }
  });

  saveDraftBtn?.addEventListener('click', () => {
    if (files.length === 0) {
      showToast('请先上传素材');
      return;
    }
    if (!workNameInput?.value.trim()) {
      showToast('请填写作品名称');
      workNameInput?.focus();
      return;
    }
    saveDraftAndRedirect(1, {
      workName: setWorkName(workNameInput.value),
      fileCount: files.length,
      template: selectedTemplate,
      material: selectedMaterial
    });
  });

  window.addEventListener('pagehide', clearUploadTimers);

  saveCreationChoices();
  initWorkNameEditor();
  updateNextBtn();
}

// 模板选择页（P3）
function initTemplatePage() {
  const templateCards = document.querySelectorAll('.template-card');
  const styleTags = document.querySelectorAll('.style-tag');
  const materialBtns = document.querySelectorAll('.material-icon-btn');
  const previewImg = document.getElementById('templatePreview');
  const generateBtn = document.getElementById('generateBtn');
  const saveDraftBtn = document.getElementById('saveDraftBtn');

  const previews = {
    comic: {
      anime: 'https://picsum.photos/seed/comic-anime/400/560',
      cyber: 'https://picsum.photos/seed/comic-cyber/400/560',
      realistic: 'https://picsum.photos/seed/comic-real/400/560'
    },
    map: {
      anime: 'https://picsum.photos/seed/map-anime/400/560',
      cyber: 'https://picsum.photos/seed/map-cyber/400/560',
      realistic: 'https://picsum.photos/seed/map-real/400/560'
    },
    album: {
      anime: 'https://picsum.photos/seed/album-anime/400/560',
      cyber: 'https://picsum.photos/seed/album-cyber/400/560',
      realistic: 'https://picsum.photos/seed/album-real/400/560'
    }
  };

  let selectedTemplate = 'comic';
  let selectedStyle = 'anime';

  const updatePreview = () => {
    if (previewImg && previews[selectedTemplate]?.[selectedStyle]) {
      previewImg.src = previews[selectedTemplate][selectedStyle];
    }
  };

  templateCards.forEach(card => {
    card.addEventListener('click', () => {
      templateCards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      selectedTemplate = card.dataset.template;
      updatePreview();
    });
  });

  styleTags.forEach(tag => {
    tag.addEventListener('click', () => {
      styleTags.forEach(t => t.classList.remove('selected'));
      tag.classList.add('selected');
      selectedStyle = tag.dataset.style;
      updatePreview();
    });
  });

  materialBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      btn.classList.toggle('selected');
    });
  });

  generateBtn?.addEventListener('click', () => {
    generateBtn.disabled = true;
    generateBtn.textContent = '生成中...';
    setTimeout(() => {
      window.location.href = 'index.html';
    }, 1200);
  });

  bindSaveDraftBtn(saveDraftBtn, 2, () => ({
    template: selectedTemplate,
    style: selectedStyle,
    materials: Array.from(materialBtns)
      .filter(btn => btn.classList.contains('selected'))
      .map(btn => btn.textContent.trim())
  }));

  updatePreview();
}

// 我的页面（P6）— 从后端加载本机会话的任务与作品
async function initProfilePage() {
  const tabs = document.querySelectorAll('.profile-tab');
  const panelPublished = document.getElementById('panel-published');
  const panelDraft = document.getElementById('panel-draft');
  const demoEntry = document.getElementById('demoEntry');
  const statPublished = document.querySelector('.profile-stat:nth-child(1) .profile-stat-num');
  const statDraft = document.querySelector('.profile-stat:nth-child(2) .profile-stat-num');
  const statLikes = document.querySelector('.profile-stat:nth-child(3) .profile-stat-num');

  const switchPanel = (panel) => {
    tabs.forEach((t) => t.classList.toggle('active', t.dataset.panel === panel));
    if (panelPublished) panelPublished.style.display = panel === 'published' ? 'block' : 'none';
    if (panelDraft) panelDraft.style.display = panel === 'draft' ? 'block' : 'none';
  };

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => switchPanel(tab.dataset.panel));
  });

  if (window.location.hash === '#draft') {
    switchPanel('draft');
  }

  demoEntry?.addEventListener('click', () => {
    window.location.href = 'upload.html';
  });

  const renderDrafts = () => {
    if (!panelDraft) return;
    let draft;
    try {
      draft = JSON.parse(localStorage.getItem('momentmaker_draft'));
    } catch (error) {
      draft = null;
    }
    if (!draft) {
      panelDraft.innerHTML = '<p class="works-empty">暂无草稿</p>';
      if (statDraft) statDraft.textContent = '0';
      return;
    }
    if (statDraft) statDraft.textContent = '1';
    panelDraft.innerHTML = `
      <div class="profile-work-item">
        <div class="profile-work-thumb">草稿</div>
        <div class="profile-work-info">
          <div class="profile-work-title">${draft.workName || '未命名草稿'}</div>
          <div class="profile-work-meta">${TEMPLATE_NAMES[draft.template] || draft.template} · ${MATERIAL_NAMES[draft.material] || draft.material}</div>
        </div>
        <a href="upload.html" class="btn btn-sm">继续</a>
      </div>
    `;
  };

  const renderPublished = async () => {
    if (!panelPublished || !window.MomentMakerApi) return;
    panelPublished.innerHTML = '<p class="works-empty">正在加载已发布作品...</p>';
    try {
      const works = await window.MomentMakerApi.fetchMyWorks();
      const tasks = await window.MomentMakerApi.fetchMyTasks();
      const totalLikes = works.reduce((sum, item) => sum + (item.likes || 0), 0);
      if (statPublished) statPublished.textContent = String(works.length);
      if (statLikes) statLikes.textContent = String(totalLikes);

      const unpublished = tasks.filter(
        (task) => task.status === 'succeeded' && !works.some((work) => work.task_id === task.task_id)
      );
      const processing = tasks.filter(
        (task) => !['succeeded', 'failed'].includes(task.status)
      );
      const failed = tasks.filter((task) => task.status === 'failed');

      if (!works.length && !unpublished.length && !processing.length && !failed.length) {
        panelPublished.innerHTML = '<p class="works-empty">还没有作品，去上传页开始创作吧</p>';
        return;
      }

      const workItems = works.map((work) => `
        <a class="profile-work-item" href="index.html?work=${encodeURIComponent(work.work_id)}">
          <div class="profile-work-thumb">
            <img src="${window.MomentMakerApi.fileUrl(work.cover_url)}" alt="${work.title}">
          </div>
          <div class="profile-work-info">
            <div class="profile-work-title">${work.title}</div>
            <div class="profile-work-meta">${TEMPLATE_NAMES[work.template] || work.template} · 赞 ${work.likes || 0}</div>
          </div>
          <span class="profile-chevron">›</span>
        </a>
      `).join('');

      const processingItems = processing.map((task) => `
        <div class="profile-work-item">
          <div class="profile-work-thumb">生成中</div>
          <div class="profile-work-info">
            <div class="profile-work-title">${task.work_title || '未命名作品'}</div>
            <div class="profile-work-meta">${window.MomentMakerApi.STATUS_LABELS[task.status] || '正在生成'} · ${task.progress || 0}%</div>
          </div>
        </div>
      `).join('');

      const unpublishedItems = unpublished.map((task) => `
        <a class="profile-work-item" href="${window.MomentMakerApi.fileUrl(task.result_url)}" target="_blank" rel="noopener">
          <div class="profile-work-thumb">
            <img src="${window.MomentMakerApi.fileUrl(task.result_url)}" alt="${task.work_title}">
          </div>
          <div class="profile-work-info">
            <div class="profile-work-title">${task.work_title}</div>
            <div class="profile-work-meta">已生成，正在补发到广场</div>
          </div>
          <span class="profile-chevron">›</span>
        </a>
      `).join('');

      const failedItems = failed.map((task) => `
        <div class="profile-work-item">
          <div class="profile-work-thumb">失败</div>
          <div class="profile-work-info">
            <div class="profile-work-title">${task.work_title || '未命名作品'}</div>
            <div class="profile-work-meta">${task.error_message || '生成失败，请换图重试'}</div>
          </div>
        </div>
      `).join('');

      panelPublished.innerHTML = processingItems + workItems + unpublishedItems + failedItems;
    } catch (error) {
      panelPublished.innerHTML = `<p class="works-empty">${error.message || '加载失败'}</p>`;
    }
  };

  renderDrafts();
  await renderPublished();
}

// 顶部 Banner 轮播（广场页：海报 + 每位选手各一屏，5 秒自动切换）
function initKingkongCarousel() {
  const track = document.getElementById('kingkongTrack');
  const dots = document.querySelectorAll('.kingkong-dot');
  const viewport = document.querySelector('.kingkong-viewport');
  if (!track || dots.length === 0) return;

  const slides = track.querySelectorAll('.kingkong-slide');
  let current = 0;
  let startX = 0;
  let isDragging = false;
  let autoTimer = null;
  const AUTO_INTERVAL = 5000;

  const goTo = (index) => {
    current = Math.max(0, Math.min(index, slides.length - 1));
    track.style.transform = `translateX(-${current * 100}%)`;
    dots.forEach((dot, i) => dot.classList.toggle('active', i === current));
  };

  const startAutoPlay = () => {
    stopAutoPlay();
    autoTimer = setInterval(() => {
      goTo((current + 1) % slides.length);
    }, AUTO_INTERVAL);
  };

  const stopAutoPlay = () => {
    if (autoTimer) {
      clearInterval(autoTimer);
      autoTimer = null;
    }
  };

  const resetAutoPlay = () => {
    startAutoPlay();
  };

  dots.forEach((dot, i) => {
    dot.addEventListener('click', () => {
      goTo(i);
      resetAutoPlay();
    });
  });

  viewport?.addEventListener('touchstart', (e) => {
    startX = e.touches[0].clientX;
    isDragging = true;
    stopAutoPlay();
  }, { passive: true });

  viewport?.addEventListener('touchend', (e) => {
    if (!isDragging) return;
    const diff = e.changedTouches[0].clientX - startX;
    if (Math.abs(diff) > 40) {
      goTo(diff < 0 ? current + 1 : current - 1);
    }
    isDragging = false;
    resetAutoPlay();
  }, { passive: true });

  goTo(0);
  startAutoPlay();
}

// 页面初始化入口
document.addEventListener('DOMContentLoaded', async () => {
  initKingkongCarousel();
  initLightbox();
  await loadWorksFromApi();
  initUploadPage();
  initTemplatePage();
  await initProfilePage();
});
